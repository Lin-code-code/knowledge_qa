from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rag.rag_service import RagService
from typing import List, Optional

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 请求体模型
class ChatRequest(BaseModel):
    message: str
    chatId: Optional[str] = None

# 响应体模型
class SourceReference(BaseModel):
    title: str
    content: str

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = []
    chatId: Optional[str] = None

# 创建 RAG 服务实例
rag_service = RagService()

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
