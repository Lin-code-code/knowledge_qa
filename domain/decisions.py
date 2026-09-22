from dataclasses import dataclass, field

from domain.enums import ScopeLabel, TopicAction


@dataclass(slots=True)
class TopicSegment:
    query: str = ""
    scope: ScopeLabel = ScopeLabel.IN
    intent: str = "general"


@dataclass(slots=True)
class TopicDecision:
    action: TopicAction = TopicAction.CONTINUE
    topic_label: str = "服装咨询"
    intent: str = "general"
    canonical_query: str = ""
    scope: ScopeLabel = ScopeLabel.IN
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    segments: list[TopicSegment] = field(default_factory=list)


@dataclass(slots=True)
class ChatAnswer:
    answer: str
    sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MemoryCandidate:
    memory_key: str
    content: str
    confidence: float
    expires_at: str | None = None
