"""架构边界守卫：冻结 domain/service/db/api 的依赖方向，防止兼容层复活。"""

import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".")[0])
    return result


def test_services_do_not_import_infrastructure_or_api():
    forbidden = {"api", "db", "fastapi", "sqlalchemy", "agent", "rag"}
    root = Path(__file__).resolve().parents[1] / "services"
    for path in root.glob("*.py"):
        assert not (_imports(path) & forbidden), path.name


def test_api_does_not_import_repositories_or_orm():
    root = Path(__file__).resolve().parents[1] / "api"
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "db.repositories" not in source or path.name == "dependencies.py"
        assert "db.models" not in source


def test_old_repository_modules_are_removed():
    root = Path(__file__).resolve().parents[1] / "db"
    assert not (root / "conversation_repo.py").exists()
    assert not (root / "topic_repo.py").exists()
    assert not (root / "memory_repo.py").exists()
    assert not (root / "file_repo.py").exists()


def test_document_service_factory_does_not_build_vector_store():
    """列表/删除路由不涉及向量库：组合根在该路径上不得构造向量库客户端。

    Task 8 曾因 get_document_service 构造 VectorStoreService() 导致
    GET /api/files/list 与 DELETE /api/files/{file_id} 在缺 SILICONFLOW_API_KEY 时
    从 200/404 变成 500，并每请求多付 ~1.2s 与数条 SQL。此断言冻结该修复。
    """
    from api.dependencies import get_document_service

    assert get_document_service(object()).index is None
