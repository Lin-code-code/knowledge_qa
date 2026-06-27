import json
import re
from functools import lru_cache
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from rag.model.factory import get_guard_model
from utils.prompt_loader import load_guard_prompts, load_refusal_template, load_scope_check_prompt
from core.logger import logger

_LABELS = ("IN", "OUT", "REFUSE")
_LABEL_RE = re.compile(r'"(?:label|fit|result|classification|category|frame|ab)"\s*:\s*"?(\w+)"?', re.IGNORECASE)
_SCOPE_RE = re.compile(r'"(?:label|fit|result|classification|category)"\s*:\s*"?(\w+)"?', re.IGNORECASE)


@lru_cache(maxsize=1)
def get_guard_service() -> "GuardService":
    return GuardService()


class GuardService:
    """L0 域内预检 + L3 输出后处理：独立分类器检查问题域与回复合规性。"""

    def __init__(self):
        self.model = get_guard_model()
        self.prompt_text = load_guard_prompts()
        self.prompt = PromptTemplate.from_template(self.prompt_text)
        self.chain = self.prompt | self.model | StrOutputParser()
        self._refusal_text = load_refusal_template()
        self._scope_prompt_text = load_scope_check_prompt()
        self._scope_prompt = PromptTemplate.from_template(self._scope_prompt_text)
        self._scope_chain = self._scope_prompt | self.model | StrOutputParser()

    def check_question_scope(self, query: str) -> bool:
        """
        L0 预检：判定用户提问是否属于服装领域。
        返回 True 表示域内（可交给 agent），False 表示越界（直接拒答，不调 agent）。
        解析失败默认 True（域内），避免误拦正常问题。
        """
        if not query or not query.strip():
            return True

        try:
            raw = self._scope_chain.invoke({"query": query})
        except Exception as e:
            logger.error(f"[GuardService] 域内预检调用失败，默认放行: {str(e)}")
            return True

        label = self._parse_scope_label(raw)
        logger.info(f"[GuardService] scope_check query={query!r} label={label}")
        return label == "IN"

    @staticmethod
    def _parse_scope_label(raw: str) -> str:
        """从域内预检 LLM 输出中解析 YES(域内)/NO(越界)，失败默认 IN。"""
        text = raw.strip().upper()
        if "YES" in text:
            return "IN"
        if "NO" in text:
            return "OUT"
        logger.warning(f"[GuardService] scope label 解析失败，默认 IN: {text[:120]}")
        return "IN"

    def check(self, query: str, answer: str) -> tuple[bool, str]:
        """
        L3 判定客服回答是否合规。
        返回 (是否放行, 最终输出文本)：
        - 合规（IN / REFUSE / 解析失败）：放行原回答
        - 越界（OUT）：返回 False，并替换为拒答模板
        """
        if not answer or not answer.strip():
            return True, answer

        try:
            raw = self.chain.invoke({"query": query, "answer": answer})
        except Exception as e:
            logger.error(f"[GuardService] L3 分类器调用失败，默认放行: {str(e)}")
            return True, answer

        label = self._parse_label(raw)
        logger.info(f"[GuardService] L3 query={query!r} label={label}")

        if label == "OUT":
            return False, self._refusal_text
        return True, answer

    @property
    def refusal_text(self) -> str:
        return self._refusal_text

    @staticmethod
    def _parse_label(raw: str) -> str:
        """
        从 LLM 输出中解析标签（IN/OUT/REFUSE）。按优先级依次尝试：
        1. 严格 JSON 解析（字段名兼容 label/fit/result 等）
        2. 正则匹配 "field":"VALUE" 形式，VALUE 模糊匹配
        3. 裸文本模糊查找标签关键词
        全部失败则默认 IN 避免误杀。
        """
        text = raw.strip()

        def _normalize(val: str) -> str:
            """将模型输出模糊归一化为 IN/OUT/REFUSE。"""
            v = val.upper().strip()
            if "REFUS" in v:
                return "REFUSE"
            if "OUT" in v:
                return "OUT"
            if "IN" in v:
                return "IN"
            return ""

        # 1. 尝试 JSON 解析
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                obj = json.loads(text[start:end + 1])
                for key in ("label", "fit", "result", "classification", "category", "frame", "ab"):
                    if key in obj:
                        norm = _normalize(str(obj[key]))
                        if norm:
                            return norm
            except json.JSONDecodeError:
                pass

        # 2. 正则匹配 "field":"VALUE"
        for m in _LABEL_RE.finditer(text):
            norm = _normalize(m.group(1))
            if norm:
                return norm

        # 3. 裸文本模糊查找（优先级 OUT > REFUSE > IN）
        upper = text.upper()
        if "OUT" in upper:
            return "OUT"
        if "REFUS" in upper:
            return "REFUSE"
        if "IN" in upper:
            return "IN"

        logger.warning(f"[GuardService] label 解析失败，默认 IN: {text[:120]}")
        return "IN"


if __name__ == "__main__":
    gs = GuardService()
    print(gs.check("纯棉T恤会缩水吗？", "纯棉织物洗涤后可能缩水，建议冷水手洗。"))
    print(gs.check("今天股票涨了吗？", "上证指数今日上涨1.2%。"))
    print(gs.check("帮我写代码", "抱歉，我是服装行业客服助手，只能为您解答与服饰产品、订单、穿搭、洗护等相关的问题，暂无法回答该问题。"))
