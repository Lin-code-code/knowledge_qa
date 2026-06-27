from core.paths import get_abs_path
from core.logger import logger
from core.config import prompts_conf

def load_rag_prompts():
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rag_prompts]在yaml配置中没有rag_summarize_prompt_path配置项")
        raise e

    try:
        with open(rag_prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_rag_prompts]解析RAG提示词出错，{str(e)}")
        raise e


def load_system_prompts():
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_system_prompts]在yaml配置中没有main_prompt_path配置项")
        raise e

    try:
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_system_prompts]解析系统提示词出错，{str(e)}")
        raise e


def load_guard_prompts():
    try:
        guard_prompt_path = get_abs_path(prompts_conf["guard_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_guard_prompts]在yaml配置中没有guard_prompt_path配置项")
        raise e

    try:
        with open(guard_prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_guard_prompts]解析兜底分类器提示词出错，{str(e)}")
        raise e


def load_refusal_template():
    try:
        refusal_path = get_abs_path(prompts_conf["refusal_template_path"])
    except KeyError as e:
        logger.error(f"[load_refusal_template]在yaml配置中没有refusal_template_path配置项")
        raise e

    try:
        with open(refusal_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"[load_refusal_template]解析拒答模板出错，{str(e)}")
        raise e


def load_scope_check_prompt():
    try:
        scope_path = get_abs_path(prompts_conf["scope_check_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_scope_check_prompt]在yaml配置中没有scope_check_prompt_path配置项")
        raise e

    try:
        with open(scope_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"[load_scope_check_prompt]解析域内分类器提示词出错，{str(e)}")
        raise e