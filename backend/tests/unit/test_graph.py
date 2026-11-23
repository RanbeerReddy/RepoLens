"""Unit tests for Neo4j schema, client, ingester, and query execution."""

from unittest.mock import MagicMock

import pytest

from app.graph.ingester import GraphIngester
from app.graph.neo4j_client import Neo4jClient
from app.graph.queries import GraphQueries
from app.graph.schema import SCHEMA_STATEMENTS, init_schema
from app.parser.ast_parser import PythonASTParser
from app.parser.models import ParsedRepository


@pytest.fixture
def mock_client():
    client = MagicMock(spec=Neo4jClient)
    client.execute_write.return_value = []
    client.execute_read.return_value = []
    return client


def test_init_schema_executes_all_ddl(mock_client):
    init_schema(mock_client)
    assert mock_client.execute_write.call_count == len(SCHEMA_STATEMENTS)


def test_ingester_batches_repository_nodes_and_edges(mock_client):
    parser = PythonASTParser()
    code = """
class BaseService:
    pass

class AuthService(BaseService):
    def verify(self, pw):
        return check(pw)

def main():
    srv = AuthService()
    srv.verify('secret')
"""
    parsed_file = parser.parse_file("app/auth.py", code)
    parsed_repo = ParsedRepository(
        root_path="/mock/repo",
        repo_name="demo_repo",
        files=[parsed_file],
        total_files=1,
        total_functions=len(parsed_file.get_all_functions()),
        total_classes=len(parsed_file.classes),
        total_lines=15,
    )

    ingester = GraphIngester(mock_client)
    stats = ingester.ingest_repository(parsed_repo)

    assert stats["files"] == 1
    assert stats["classes"] == 2
    assert stats["functions"] == 2  # verify (method) + main (function)
    assert stats["inherits"] == 1  # AuthService -> BaseService
    assert stats["calls"] >= 2  # verify -> check, main -> AuthService/verify

    # Verify write transactions executed: Repo + Files + Classes + Functions + Inherits + Calls
    assert mock_client.execute_write.call_count == 6


def test_query_callers(mock_client):
    mock_client.execute_read.return_value = [
        {"name": "login", "file_path": "app/auth.py", "start_line": 10}
    ]
    queries = GraphQueries(mock_client)
    callers = queries.get_callers("authenticate_user", repo_id="repo:demo")

    assert len(callers) == 1
    assert callers[0]["name"] == "login"
    mock_client.execute_read.assert_called_once()
    args, kwargs = mock_client.execute_read.call_args
    assert args[1]["function_name"] == "authenticate_user"
    assert args[1]["repo_id"] == "repo:demo"


def test_query_trace_dependencies_depth_bounded(mock_client):
    queries = GraphQueries(mock_client)
    queries.trace_dependencies("func:auth:1", max_depth=10)  # should clamp to 5

    mock_client.execute_read.assert_called_once()
    query_str = mock_client.execute_read.call_args[0][0]
    assert "CALLS*1..5" in query_str


def test_client_ping_offline():
    client = Neo4jClient(uri="bolt://127.0.0.1:9999")  # Unused port
    assert client.ping() is False
