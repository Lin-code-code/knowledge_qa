import ast
from pathlib import Path

from domain.decisions import TopicDecision
from domain.entities import ConversationTopic, FileSummary
from domain.enums import Role, ScopeLabel, TopicAction


def test_domain_layer_imports_stdlib_only():
    forbidden = {"fastapi", "sqlalchemy", "langchain", "db", "services", "api", "agent", "rag"}
    root = Path(__file__).resolve().parents[1] / "domain"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        assert not (imports & forbidden), f"{path.name} 包含禁止依赖: {imports & forbidden}"


def test_domain_enums_and_defaults_are_stable():
    assert Role.HUMAN == "human"
    assert ScopeLabel.OUT == "OUT"
    assert TopicAction.OUT_OF_SCOPE == "OUT_OF_SCOPE"
    decision = TopicDecision(canonical_query="T恤怎么洗")
    assert decision.action == TopicAction.CONTINUE
    assert decision.scope == ScopeLabel.IN
    assert decision.segments == []


def test_file_summary_is_a_slots_dataclass():
    item = FileSummary(id="f-1", filename="a.txt", size=1, chunks=2)
    assert item.filename == "a.txt"
    assert not hasattr(item, "__dict__")
