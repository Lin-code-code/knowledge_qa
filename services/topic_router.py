"""兼容转发：主题路由已迁移到 agent.topic_router（Task 7 前保留旧导入路径）。"""

from agent.topic_router import TopicRouter, get_topic_router

__all__ = ["TopicRouter", "get_topic_router"]
