"""兼容转发：滚动摘要已迁移到 agent.summary_agent（Task 7 前保留旧导入路径）。"""

from agent.summary_agent import SummaryAgent as SummaryService
from agent.summary_agent import get_summary_agent as get_summary_service

__all__ = ["SummaryService", "get_summary_service"]
