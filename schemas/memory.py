from pydantic import BaseModel


class MemoryItemResponse(BaseModel):
    id: str
    memory_type: str
    memory_key: str
    content: str
    confidence: float
    expires_at: str | None = None
    created_at: str
    updated_at: str


class MemoryListResponse(BaseModel):
    user_id: str
    memories: list[MemoryItemResponse]


class MemoryDeleteResponse(BaseModel):
    message: str
    deleted_count: int
