from fastapi import APIRouter, HTTPException, Depends
from api.dependencies import (
    get_chat_service,
    get_conversation_service,
    get_memory_service,
    get_topic_service,
)
from core.config import db_conf
from core.security import require_api_key
from domain.entities import ConversationTopic, MemoryItem
from domain.errors import ConversationNotFoundError, TopicNotFoundError
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.topic_service import TopicService
from schemas.chat import (
    ChatRequest, ChatResponse, ChatDeleteResponse,
    ConversationCreateRequest, ConversationCreateResponse,
    ConversationListItem, ConversationListResponse, MessageListResponse
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
    service: ConversationService = Depends(get_conversation_service),
):
    conversations = await service.list(user_id)
    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                conversation_id=str(item.id),
                title=item.title,
                created_at=item.created_at.isoformat(),
                updated_at=item.updated_at.isoformat(),
                message_count=0,
            )
            for item in conversations
        ]
    )


@router.get("/chat/{conversation_id}/messages", response_model=MessageListResponse)
async def get_chat_messages(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    msgs = await service.get_messages(conv_uuid)
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
    service: ConversationService = Depends(get_conversation_service),
):
    conversation = await service.create(
        request.user_id or "anonymous",
        request.title or "新对话",
        create_topic=db_conf.get("conversation_memory_enabled", True),
    )
    return ConversationCreateResponse(
        conversation_id=str(conversation.id),
        title=request.title or "新对话",
    )


@router.post("/chat/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service=Depends(get_chat_service),
):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    conv_uuid = None
    if request.chatId:
        try:
            conv_uuid = uuid.UUID(request.chatId)
        except ValueError:
            raise HTTPException(status_code=400, detail="chatId 格式无效")

    try:
        result = await service.process_message(
            request.message,
            conv_uuid,
            request.user_id or "anonymous",
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="对话不存在")

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        chatId=result.chat_id or None,
        topicId=result.topic_id,
        topicAction=result.topic_action,
    )


@router.get(
    "/chat/{conversation_id}/topics",
    response_model=TopicListResponse,
)
async def list_topics(
    conversation_id: str,
    service: TopicService = Depends(get_topic_service),
):
    conv_uuid = _parse_uuid(conversation_id, "conversation_id")
    try:
        topics = await service.list(conv_uuid)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="对话不存在")
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
    service: TopicService = Depends(get_topic_service),
):
    conv_uuid = _parse_uuid(conversation_id, "conversation_id")
    topic_uuid = _parse_uuid(topic_id, "topic_id")
    try:
        topic = await service.get(conv_uuid, topic_uuid)
    except TopicNotFoundError:
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
    service: TopicService = Depends(get_topic_service),
):
    conv_uuid = _parse_uuid(conversation_id, "conversation_id")
    topic_uuid = _parse_uuid(topic_id, "topic_id")
    try:
        await service.archive(conv_uuid, topic_uuid)
    except TopicNotFoundError:
        raise HTTPException(status_code=404, detail="主题不存在")
    return TopicArchiveResponse(
        topic_id=topic_id,
        status="archived",
        message="主题已归档",
    )


@router.get("/memory", response_model=MemoryListResponse)
async def list_memory(
    user_id: str = "anonymous",
    service: MemoryService = Depends(get_memory_service),
):
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    memories = await service.list_active(user_id)
    return MemoryListResponse(
        user_id=user_id,
        memories=[_memory_item(item) for item in memories],
    )


@router.delete("/memory/{memory_id}", response_model=MemoryDeleteResponse)
async def delete_memory(
    memory_id: str,
    user_id: str = "anonymous",
    service: MemoryService = Depends(get_memory_service),
):
    memory_uuid = _parse_uuid(memory_id, "memory_id")
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    deleted = await service.delete_one(user_id, memory_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="长期记忆不存在")
    return MemoryDeleteResponse(message="长期记忆已删除", deleted_count=1)


@router.delete("/memory", response_model=MemoryDeleteResponse)
async def delete_all_memory(
    user_id: str = "anonymous",
    service: MemoryService = Depends(get_memory_service),
):
    user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
    deleted_count = await service.delete_all(user_id)
    return MemoryDeleteResponse(
        message="长期记忆已清除",
        deleted_count=deleted_count,
    )


@router.delete("/chat/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(
    chat_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    try:
        conv_uuid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    deleted = await service.delete(conv_uuid)

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


def _topic_item(topic: ConversationTopic) -> TopicListItem:
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


def _memory_item(item: MemoryItem) -> MemoryItemResponse:
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
