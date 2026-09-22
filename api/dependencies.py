from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent.chat_agent import get_chat_agent
from agent.guard_agent import get_guard_agent
from agent.memory_agent import get_memory_extractor
from agent.summary_agent import get_summary_agent
from agent.topic_router import get_topic_router
from core.config import db_conf, pg_conf
from db.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyFileRepository,
    SqlAlchemyMemoryRepository,
    SqlAlchemyTopicRepository,
)
from db.session import get_db
from rag.vector_store import VectorStoreService
from services.chat_service import ChatService
from services.context_builder import ContextBuilder
from services.conversation_service import ConversationService
from services.document_service import DocumentService
from services.memory_service import MemoryService
from services.topic_service import TopicService


def _repositories(db: AsyncSession):
    return (
        SqlAlchemyConversationRepository(db),
        SqlAlchemyTopicRepository(db),
        SqlAlchemyMemoryRepository(db),
    )


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    conversations, topics, _ = _repositories(db)
    return ConversationService(conversations, topics)


def get_topic_service(db: AsyncSession = Depends(get_db)) -> TopicService:
    conversations, topics, _ = _repositories(db)
    return TopicService(conversations, topics)


def get_memory_service(db: AsyncSession = Depends(get_db)) -> MemoryService:
    _, _, memories = _repositories(db)
    enabled = bool(db_conf.get("conversation_memory_enabled", True)) and bool(
        db_conf.get("long_term_memory_enabled", True)
    )
    extractor = get_memory_extractor() if enabled else None
    return MemoryService(memories, extractor)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    conversations, topics, memories = _repositories(db)
    memory_enabled = bool(db_conf.get("conversation_memory_enabled", True))
    long_term_enabled = bool(db_conf.get("long_term_memory_enabled", True))
    memory_service = (
        MemoryService(memories, get_memory_extractor())
        if memory_enabled and long_term_enabled
        else None
    )
    return ChatService(
        conversations=conversations,
        topics=topics,
        memory_service=memory_service,
        context_builder=ContextBuilder(),
        topic_router=get_topic_router() if db_conf.get("topic_router_enabled", True) else None,
        guard=get_guard_agent(),
        chat_agent=get_chat_agent(),
        summary_agent=get_summary_agent() if db_conf.get("summary_enabled", True) else None,
    )


def get_document_service(
    db: AsyncSession = Depends(get_db),
    chunk_size: int = pg_conf["chunk_size"],
    chunk_overlap: int = pg_conf["chunk_overlap"],
) -> DocumentService:
    # chunk_size / chunk_overlap 声明在依赖上，FastAPI 会将其扁平化为上传路由的查询参数，
    # 保证与旧 api/documents.py 的对外契约逐字一致（调用方可覆盖默认分片参数）。
    return DocumentService(
        SqlAlchemyFileRepository(db),
        VectorStoreService(chunk_size, chunk_overlap),
    )
