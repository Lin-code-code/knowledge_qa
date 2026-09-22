import inspect

from domain.ports import ChatAgentPort, ConversationRepositoryPort


def test_chat_agent_port_exposes_execute_with_topic_label():
    signature = inspect.signature(ChatAgentPort.execute)
    assert list(signature.parameters) == ["self", "query", "context", "topic_label"]


def test_conversation_port_keeps_turn_signature():
    signature = inspect.signature(ConversationRepositoryPort.add_turn)
    assert "user_content" in signature.parameters
    assert "assistant_content" in signature.parameters
    assert "memory_eligible" in signature.parameters
