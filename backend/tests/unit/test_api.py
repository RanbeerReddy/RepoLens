"""Unit tests for FastAPI endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoints():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_neo4j = client.get("/health/neo4j")
    assert res_neo4j.status_code == 200

    res_llm = client.get("/health/llm")
    assert res_llm.status_code == 200


def test_repository_lifecycle_endpoints(tmp_path: Path):
    # Setup test mock repository
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "auth.py").write_text(
        "def verify_password(p): return True\n"
        "def authenticate_user(u, p):\n"
        "    return verify_password(p)\n",
        encoding="utf-8",
    )

    # 1. Register
    reg_resp = client.post(
        "/api/repositories",
        json={"path": str(tmp_path), "name": "test_api_repo"},
    )
    assert reg_resp.status_code == 201
    repo_data = reg_resp.json()
    repo_id = repo_data["id"]
    assert repo_data["name"] == "test_api_repo"

    # 2. List
    list_resp = client.get("/api/repositories")
    assert list_resp.status_code == 200
    assert any(r["id"] == repo_id for r in list_resp.json())

    # 3. Ingest
    ingest_resp = client.post(f"/api/repositories/{repo_id}/ingest")
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["status"] == "success"
    assert ingest_data["repository"]["total_files"] == 1
    assert ingest_data["repository"]["total_functions"] == 2

    # 4. Files
    files_resp = client.get(f"/api/repositories/{repo_id}/files")
    assert files_resp.status_code == 200
    assert "pkg/auth.py" in files_resp.json()

    # 5. File details
    file_detail = client.get(f"/api/repositories/{repo_id}/files/pkg/auth.py")
    assert file_detail.status_code == 200
    assert len(file_detail.json()["functions"]) == 2
    assert "def verify_password" in file_detail.json()["source"]

    # 6. Symbols
    symbols_resp = client.get(f"/api/repositories/{repo_id}/symbols?query=auth")
    assert symbols_resp.status_code == 200
    assert len(symbols_resp.json()) >= 1
    assert any(s["name"] == "authenticate_user" for s in symbols_resp.json())

    # 7. Graph data
    graph_resp = client.get(f"/api/repositories/{repo_id}/graph")
    assert graph_resp.status_code == 200
    assert "nodes" in graph_resp.json()
    assert "edges" in graph_resp.json()

    # 8. Search
    search_resp = client.post(
        f"/api/repositories/{repo_id}/search",
        json={"query": "verify password", "limit": 2},
    )
    assert search_resp.status_code == 200

    # 9. Chat
    chat_resp = client.post(
        f"/api/repositories/{repo_id}/chat",
        json={"query": "How is authentication handled?"},
    )
    assert chat_resp.status_code == 200
    assert "answer" in chat_resp.json()

    # 10. Impact Analysis
    impact_resp = client.post(
        f"/api/repositories/{repo_id}/impact",
        json={"function_name": "verify_password"},
    )
    assert impact_resp.status_code == 200
    assert impact_resp.json()["target_function"] == "verify_password"

    # 11. Delete
    del_resp = client.delete(f"/api/repositories/{repo_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


def test_register_invalid_directory():
    resp = client.post("/api/repositories", json={"path": "/nonexistent/path/12345"})
    assert resp.status_code == 400
