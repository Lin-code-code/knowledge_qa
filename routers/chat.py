from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rag.rag_service import RagService
from schemas.chat import ChatRequest, ChatResponse, ChatDeleteResponse

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 创建 RAG 服务实例
rag_service = RagService()

@router.delete("/{chat_id}", response_model=ChatDeleteResponse)
async def delete_chat(chat_id: str):
    """
    删除指定对话
    
    注意：此接口尚未实现具体逻辑，仅作为接口定义预留。
    后续将实现从数据库/持久化存储中删除对话记录。
    """

    raise HTTPException(
        status_code=501,
        detail="该功能尚未实现：对话删除接口已定义，待后续开发"
    )

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    知识库问答接口
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="消息不能为空")
        
        # 调用 RAG 服务获取答案
        answer = rag_service.rag_summarize(request.message)
        
        # 检索参考文档
        context_docs = rag_service.retriever_docs(request.message)
        
        # 提取来源信息
        sources = []
        for i, doc in enumerate(context_docs, 1):
            source_title = doc.metadata.get('source', f'参考资料{i}')
            sources.append(source_title)
        
        # 生成简单的 chatId（实际项目中应该使用数据库管理会话）
        import uuid
        chat_id = request.chatId or str(uuid.uuid4())
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            chatId=chat_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")
