from typing import Literal
from pydantic import BaseModel, Field


TopicAction = Literal["CONTINUE", "NEW_TOPIC", "MIXED", "CLARIFY", "OUT_OF_SCOPE"]


class TopicSegment(BaseModel):
    query: str = ""
    scope: Literal["IN", "OUT"] = "IN"
    intent: str = "general"


class TopicDecision(BaseModel):
    action: TopicAction = "CONTINUE"
    topic_label: str = "服装咨询"
    intent: str = "general"
    canonical_query: str = ""
    scope: Literal["IN", "OUT"] = "IN"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarification_question: str = ""
    segments: list[TopicSegment] = Field(default_factory=list)


class TopicListItem(BaseModel):
    topic_id: str
    topic_label: str
    last_intent: str | None = None
    scope_label: str
    confidence: float
    status: str
    created_at: str
    updated_at: str


class TopicListResponse(BaseModel):
    conversation_id: str
    topics: list[TopicListItem]


class TopicDetailResponse(TopicListItem):
    summary: str = ""


class TopicArchiveResponse(BaseModel):
    topic_id: str
    status: str
    message: str
