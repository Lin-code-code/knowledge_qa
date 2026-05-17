from pydantic import BaseModel
from typing import List, Optional

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