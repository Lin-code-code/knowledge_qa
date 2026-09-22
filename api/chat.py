from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from db.conversation_repo import ConversationRepository
from services.chat_service import ChatService, ConversationNotFoundError
from core.security import require_api_key
from schemas.chat import (
    ChatRequest, ChatResponse, ChatDeleteResponse,
    ConversationCreateRequest, ConversationCreateResponse,
    ConversationListResponse, MessageListResponse
)
from schemas.memory import MemoryDeleteResponse, MemoryListResponse, MemoryItemResponse
from schemas.topic import (
    TopicArchiveResponse,
    TopicDetailResponse,
    TopicListItem,
    TopicListResponse,
)
import uuid

router = APIRouter(prefix="/api", tags=["Chat"], dependencies=[Depends(require_api_key)])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    store = ConversationRepository(db)
    convs = await store.list_conversations(user_id=user_id)
    items = []
    for c in convs:
        items.append({
            "conversation_id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "message_count": 0,
        })
    return ConversationListResponse(conversations=items)


@router.get("/chat/{conversation_id}/messages", response_model=MessageListResponse)
async def get_chat_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    store = ConversationRepository(db)
    msgs = await store.get_messages(conv_uuid)
    return MessageListResponse(
        messages=[{
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        } for m in msgs],
        conversation_id=conversation_id,
    )


@router.post("/conversations", response_model=ConversationCreateResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    store = ConversationRepository(db)
    conv_id = await store.create_conversation(
        user_id=request.user_id or "anonymous",
        title=request.title or "新对话",
    )
    return ConversationCreateResponse(
        conversation_id=str(conv_id),
        title=request.title or "新对话",
    )


@router.post("/chat/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    conv_uuid = None
    if request.chatId:
        try:
            conv_uuid = uuid.UUID(request.chatId)
        except ValueError:
            raise HTTPException(status_code=400, detail="chatId 格式无效")

    service = ChatService(db)
    try:
        result = await service.process_message(
            request.message,
            conv_uuid,
            request.user_id or "anonymous",
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="对话不存在")
    # 兼容上一版本的三元组 mock/调用方，正式实现返回 ChatResult。
    if hasattr(result, "answer"):
        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            chatId=result.chat_id or None,
            topicId=result.topic_id,
            topicAction=result.topic_action,
        )

    if len(result) == 3:
        answer, sources, chat_id = result
        return ChatResponse(answer=answer, sources=sources, chatId=chat_id)
    answer, sources, chat_id, topic_id, topic_action = result
    return ChatResponse(
        answer=answer,
        sources=sources,
        chatId=chat_id or None,
        topicId=topic_id,
        topicAction=topic_action,
    )


@router.get(
    "/chat/{conversation_id}/topics",
    response_model=TopicListResponse,
)
async def list_topics(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    store = ConversationRepository(db)
    if await store.get_conversation(conv_uuid) is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    topics = await store.topics.list(conv_uuid)
    return TopicListResponse(
        conversation_id=conversation_id,
        topics=[_topic_item(topic) for topic in topics],
    )


@router.get(
    "/chat/{conversation_id}/topics/{topic_id}",
    response_model=TopicDetailResponse,
)
async def get_topic(
    conversation_id: str,
    topic_id: str,
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = _parse_uuid(conversation_id, "conversation_id")
    topic_uuid = _parse_uuid(topic_id, "topic_id")
    store = ConversationRepository(db)
    topic = await store.topics.get(conv_uuid, topic_uuid)
    if topic is None:
        raise HTTPException(status_code=404, detail="主题不存在")
    return TopicDetailResponse(
        **_topic_item(topic).model_dump(),
        summary=topic.summary or "",
    )


@router.post(
    "/chat/{conversation_id}/topics/{topic_id}/archive",
    response_model=TopicArchiveResponse,
)
async def archive_topic(
    conversation_id: str,
    topic_id: str,
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = _parse_uuid(conversation_id, "conversation_id")
    topic_uuid = _parse_uuid(topic_id, "topic_id")
    store = ConversationRepository(db)
    topic = await store.topics.get(conv_uuid, topic_uuid)
    if topic is None:
        raise HTTPException(status_code=404, detail="主题不存在")
    await store.topics.archive(topic_uuid)
    return TopicArchiveResponse(
        topic_id=topic_id,
        status="archived",
        message="主题已归档",
    )


@router.get("/memory", response_model=MemoryListResponse)
async def list_memory(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    store = ConversationRepository(db)
    memories = await store.memories.list_active(user_id)
    return MemoryListResponse(
        user_id=user_id,
        memories=[_memory_item(item) for item in memories],
    )


@router.delete("/memory/{memory_id}", response_model=MemoryDeleteResponse)
async def delete_memory(
    memory_id: str,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    memory_uuid = _parse_uuid(memory_id, "memory_id")
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    store = ConversationRepository(db)
    deleted = await store.memories.delete_one(user_id, memory_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="长期记忆不存在")
    return MemoryDeleteResponse(message="长期记忆已删除", deleted_count=1)


@router.delete("/memory", response_model=MemoryDeleteResponse)
async def delete_all_memory(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    store = ConversationRepository(db)
    deleted_count = await store.memories.delete_all(user_id)
    return MemoryDeleteResponse(
        message="长期记忆已清除",
        deleted_count=deleted_count,
    )


@router.delete("/chat/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    store = ConversationRepository(db)
    deleted = await store.delete_conversation(conv_uuid)

    if not deleted:
        raise HTTPException(status_code=404, detail="对话不存在")

    return ChatDeleteResponse(
        message="删除成功",
        chatId=chat_id,
    )


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} 格式无效")


def _topic_item(topic) -> TopicListItem:
    return TopicListItem(
        topic_id=str(topic.id),
        topic_label=topic.topic_label,
        last_intent=topic.last_intent,
        scope_label=topic.scope_label,
        confidence=topic.confidence,
        status=topic.status,
        created_at=topic.created_at.isoformat(),
        updated_at=topic.updated_at.isoformat(),
    )


def _memory_item(item) -> MemoryItemResponse:
    return MemoryItemResponse(
        id=str(item.id),
        memory_type=item.memory_type,
        memory_key=item.memory_key,
        content=item.content,
        confidence=item.confidence,
        expires_at=item.expires_at.isoformat() if item.expires_at else None,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )
