"""兼容转发：L0/L3 护栏已迁移到 agent.guard_agent（Task 7 前保留旧导入路径）。"""

from agent.guard_agent import GuardAgent, GuardAgent as GuardService
from agent.guard_agent import get_guard_agent, get_guard_agent as get_guard_service

__all__ = ["GuardAgent", "GuardService", "get_guard_agent", "get_guard_service"]
