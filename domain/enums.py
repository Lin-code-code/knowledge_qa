from enum import Enum


class Role(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


class ScopeLabel(str, Enum):
    IN = "IN"
    OUT = "OUT"


class TopicAction(str, Enum):
    CONTINUE = "CONTINUE"
    NEW_TOPIC = "NEW_TOPIC"
    MIXED = "MIXED"
    CLARIFY = "CLARIFY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class TopicStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
