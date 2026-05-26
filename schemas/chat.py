from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    message: str
    chatId: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = []
    chatId: Optional[str] = None

class ChatDeleteResponse(BaseModel):
    message: str
    chatId: str

class ConversationCreateRequest(BaseModel):
    user_id: Optional[str] = "anonymous"
    title: Optional[str] = "新对话"

class ConversationCreateResponse(BaseModel):
    conversation_id: str
    title: str

class ConversationListItem(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

class ConversationListResponse(BaseModel):
    conversations: list

class MessageItem(BaseModel):
    role: str
    content: str
    created_at: str

class MessageListResponse(BaseModel):
    messages: list
    conversation_id: str