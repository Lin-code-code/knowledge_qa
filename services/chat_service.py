from functools import lru_cache
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from db.conversation_repo import ConversationRepository
from agent.tool.agent_tools import get_rag_service
from services.guard_service import get_guard_service
from core.config import db_conf

_REFUSAL_MARKER = "暂无法回答该问题"
# 传给 agent 的历史轮数（每轮=H+AI=2 条）。0=不传历史，每轮独立问答。
# 解决历史污染：agent 看到上一轮 AI 回答内容会复用旧话题的工具调用，prompt 软约束不可靠。
_AGENT_HISTORY_TURNS = db_conf.get("agent_history_turns", 0)


@lru_cache(maxsize=1)
def _get_react_agent():
    from agent.react_agent import ReactAgent
    return ReactAgent()


def _filter_refusal_history(history: list[BaseMessage]) -> list[BaseMessage]:
    """
    从历史中过滤掉已被拒答的问答对（越界问题 + 拒答回答），
    避免 agent 回头处理历史中已被拒答的无关问题。
    """
    result: list[BaseMessage] = []
    for msg in history:
        if isinstance(msg, AIMessage) and _REFUSAL_MARKER in (msg.content or ""):
            if result:
                result.pop()
            continue
        result.append(msg)
    return result


def _limit_history_turns(history: list[BaseMessage], turns: int) -> list[BaseMessage]:
    """
    按轮数截断传给 agent 的历史（1 轮 = 1 个 HumanMessage + 1 个 AIMessage = 2 条消息）。
    turns <= 0 时返回空列表，即每轮独立问答、不传任何历史。
    解决历史污染：agent 看到上一轮 AI 回答的具体内容后会复用旧话题的工具调用
    （如洗护问题调尺码工具），prompt 软约束对 qwen3.7-max 不可靠，需代码级根治。
    """
    if turns <= 0:
        return []
    max_msgs = turns * 2
    if len(history) > max_msgs:
        return history[-max_msgs:]
    return history


class ChatService:
    def __init__(self, db: AsyncSession):
        self.store = ConversationRepository(db)

    async def process_message(
        self, message: str, chat_id: str | None
    ) -> tuple[str, list[str], str]:
        # L0 预检：越界问题直接拒答，不创建会话，不落库
        guard_service = get_guard_service()
        in_scope = guard_service.check_question_scope(message)
        if not in_scope:
            return guard_service.refusal_text, [], chat_id or ""

        if not chat_id:
            conv_id = await self.store.create_conversation(
                user_id="anonymous",
                title=message[:15] + ("..." if len(message) > 15 else ""),
            )
            chat_id = str(conv_id)

        conv_uuid = UUID(chat_id)

        history = await self.store.get_recent_messages(conv_uuid)
        history = _filter_refusal_history(history)
        history = _limit_history_turns(history, _AGENT_HISTORY_TURNS)

        agent = _get_react_agent()
        answer = await agent.aexecute(message, history)

        # L3 兜底：独立分类器检查回复合规性，越界则替换为拒答模板
        ok, guarded_answer = guard_service.check(message, answer)
        if not ok:
            answer = guarded_answer

        rag_service = get_rag_service()
        sources = rag_service.get_sources()

        await self.store.add_messages(conv_uuid, [
            HumanMessage(content=message),
            AIMessage(content=answer),
        ])

        return answer, sources, chat_id
