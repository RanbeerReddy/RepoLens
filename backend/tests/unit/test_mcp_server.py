"""Unit tests for RepoLens FastMCP Server tools."""

from unittest.mock import MagicMock

import pytest

from app.graph.neo4j_client import Neo4jClient
from app.mcp.server import create_mcp_server
from app.retrieval.hybrid_search import HybridSearchEngine, HybridSearchResult
from app.services.impact_service import (
    DependentEntity,
    ImpactLevel,
    ImpactReport,
    ImpactService,
)


@pytest.fixture
def mcp_app():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_client.ping.return_value = True

    mock_hybrid = MagicMock(spec=HybridSearchEngine)
    mock_hybrid.search.return_value = [
        HybridSearchResult(
            id="fn:auth:login",
            name="login",
            qualified_name="app.auth.login",
            file_path="app/auth.py",
            start_line=15,
            end_line=30,
            signature="def login(req: Request)",
            docstring="Authenticates user session",
            source="def login(req): return True",
            final_score=0.89,
            reasons=["Semantic match (0.89)"],
        )
    ]

    mock_impact = MagicMock(spec=ImpactService)
    mock_impact.analyze_impact.return_value = ImpactReport(
        target_function="authenticate_user",
        target_qualified_name="app.auth.authenticate_user",
        target_file_path="app/auth.py",
        impact_level=ImpactLevel.MEDIUM,
        heuristic_rationale="Moderate blast radius",
        direct_callers=[
            DependentEntity(
                id="fn:login",
                name="login",
                qualified_name="app.routes.login",
                file_path="app/routes.py",
                start_line=10,
                end_line=20,
            )
        ],
        affected_files=["app/auth.py", "app/routes.py"],
        relevant_tests=["tests/test_auth.py"],
        analysis_summary="Review login flow before changing interface.",
    )

    server = create_mcp_server(
        neo4j_client=mock_client,
        hybrid_engine=mock_hybrid,
        impact_svc=mock_impact,
    )
    return server, mock_client, mock_hybrid, mock_impact


def test_mcp_lists_all_six_tools(mcp_app):
    server, _, _, _ = mcp_app
    tools = [t.name for t in server._tool_manager.list_tools()]
    expected = [
        "list_repositories",
        "search_code",
        "get_symbol",
        "trace_dependencies",
        "impact_analysis",
        "explain_architecture",
    ]
    for exp in expected:
        assert exp in tools


def test_mcp_tool_list_repositories(mcp_app):
    server, mock_client, _, _ = mcp_app
    mock_client.execute_read.return_value = [
        {"id": "repo:repolens", "name": "repolens", "total_files": 12}
    ]
    fn = server._tool_manager.get_tool("list_repositories").fn
    res = fn()
    assert len(res) == 1
    assert res[0]["name"] == "repolens"


def test_mcp_tool_search_code(mcp_app):
    server, _, mock_hybrid, _ = mcp_app
    fn = server._tool_manager.get_tool("search_code").fn
    results = fn(query="user login", limit=3)

    assert len(results) == 1
    hit = results[0]
    assert hit["name"] == "login"
    assert hit["file_path"] == "app/auth.py"
    assert hit["lines"] == "15-30"
    assert hit["relevance_score"] == 0.89
    mock_hybrid.search.assert_called_once()


def test_mcp_tool_get_symbol(mcp_app):
    server, mock_client, _, _ = mcp_app
    mock_client.execute_read.return_value = [
        {
            "name": "login",
            "file_path": "app/auth.py",
            "start_line": 15,
            "end_line": 30,
            "signature": "def login()",
            "callers": ["main"],
            "callees": ["verify_password"],
        }
    ]
    fn = server._tool_manager.get_tool("get_symbol").fn
    res = fn(symbol_name="login")

    assert res["name"] == "login"
    assert "verify_password" in res["callees"]


def test_mcp_tool_trace_dependencies(mcp_app):
    server, mock_client, _, _ = mcp_app
    mock_client.execute_read.side_effect = [
        [{"name": "main"}],  # callers
        [{"name": "validate"}],  # callees
        [{"nodes": [], "depth": 1}],  # paths
    ]
    fn = server._tool_manager.get_tool("trace_dependencies").fn
    res = fn(symbol_name="login", depth=2)

    assert res["symbol"] == "login"
    assert len(res["callers"]) == 1
    assert len(res["callees"]) == 1


def test_mcp_tool_impact_analysis(mcp_app):
    server, _, _, mock_impact = mcp_app
    fn = server._tool_manager.get_tool("impact_analysis").fn
    res = fn(function_name="authenticate_user")

    assert res["target_function"] == "authenticate_user"
    assert res["impact_level"] == "MEDIUM"
    assert len(res["direct_callers"]) == 1
    assert "tests/test_auth.py" in res["relevant_tests"]
    mock_impact.analyze_impact.assert_called_once()


def test_mcp_tool_explain_architecture(mcp_app):
    server, mock_client, _, _ = mcp_app
    mock_client.execute_read.return_value = [
        {"repo_name": "repolens", "file_count": 12, "function_count": 48}
    ]
    fn = server._tool_manager.get_tool("explain_architecture").fn
    res = fn()

    assert res["repo_name"] == "repolens"
    assert res["function_count"] == 48
