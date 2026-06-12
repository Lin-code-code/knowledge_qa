from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from db.conversation_repo import ConversationRepository
from services.chat_service import ChatService
from schemas.chat import (
    ChatRequest, ChatResponse, ChatDeleteResponse,
    ConversationCreateRequest, ConversationCreateResponse,
    ConversationListResponse, MessageListResponse
)
import uuid

router = APIRouter(prefix="/api", tags=["Chat"])


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db),
):
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/chat/{conversation_id}/messages", response_model=MessageListResponse)
async def get_chat_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息列表失败: {str(e)}")


@router.post("/conversations", response_model=ConversationCreateResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        store = ConversationRepository(db)
        conv_id = await store.create_conversation(
            user_id=request.user_id or "anonymous",
            title=request.title or "新对话",
        )
        return ConversationCreateResponse(
            conversation_id=str(conv_id),
            title=request.title or "新对话",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.post("/chat/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    try:
        service = ChatService(db)
        answer, sources, chat_id = await service.process_message(
            request.message, request.chatId
        )
        return ChatResponse(answer=answer, sources=sources, chatId=chat_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")


@router.delete("/chat/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
