from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from history.db.engine import get_db
from history.db.message_store import AsyncMessageStore
from agent.react_agent import ReactAgent
from rag.rag_service import RagService
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
    """获取当前用户的会话列表"""
    try:
        store = AsyncMessageStore(db)
        convs = await store.list_conversations(user_id=user_id)
        items = []
        for c in convs:
            msgs = await store.get_messages(c.id, limit=1)
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
    """获取指定会话的消息列表"""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="conversation_id 格式无效")

    try:
        store = AsyncMessageStore(db)
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
    """创建新会话"""
    try:
        store = AsyncMessageStore(db)
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
    """带历史对话的多轮问答接口"""
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="消息不能为空")

        store = AsyncMessageStore(db)

        # 无 chatId 时先创建新会话
        if not request.chatId:
            conv_id = await store.create_conversation(
                user_id="anonymous",
                title=request.message[:30] + ("..." if len(request.message) > 30 else ""),
            )
            conversation_id = str(conv_id)
        else:
            conversation_id = request.chatId

        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="conversation_id 格式无效")

        history = await store.get_recent_messages(conv_uuid)

        agent = ReactAgent()
        answer = await agent.aexecute(request.message, history)

        rag_service = RagService()
        sources = rag_service.get_sources(request.message)

        from langchain_core.messages import HumanMessage, AIMessage
        await store.add_messages(conv_uuid, [
            HumanMessage(content=request.message),
            AIMessage(content=answer),
        ])

        return ChatResponse(
            answer=answer,
            sources=sources,
            chatId=conversation_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")


@router.delete("/chat/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(
    chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除指定对话及其所有消息"""
    try:
        try:
            conv_uuid = uuid.UUID(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="conversation_id 格式无效")

        store = AsyncMessageStore(db)
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
