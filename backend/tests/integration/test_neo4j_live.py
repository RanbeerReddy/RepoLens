"""Integration test for live Neo4j database."""

import pytest

from app.graph.ingester import GraphIngester
from app.graph.neo4j_client import Neo4jClient
from app.graph.queries import GraphQueries
from app.graph.schema import init_schema
from app.parser.ast_parser import PythonASTParser
from app.parser.models import ParsedRepository


@pytest.mark.integration
def test_live_neo4j_ingestion_and_queries():
    client = Neo4jClient()
    if not client.ping():
        pytest.skip("Neo4j database is offline. Skipping live integration test.")

    test_repo_id = "repo:test_integration"
    queries = GraphQueries(client)

    try:
        # 1. Clean previous state if any
        queries.delete_repository(test_repo_id)

        # 2. Init Schema
        init_schema(client)

        # 3. Parse and Ingest
        parser = PythonASTParser()
        code = """
def helper():
    return 42

def caller_func():
    return helper()
"""
        pf = parser.parse_file("pkg/mod.py", code)
        repo = ParsedRepository(
            root_path="/tmp/test",
            repo_name="test_integration",
            files=[pf],
            total_files=1,
            total_functions=2,
            total_classes=0,
            total_lines=10,
        )

        ingester = GraphIngester(client)
        ingester.ingest_repository(repo, repo_id=test_repo_id)

        # 4. Query Callers
        callers = queries.get_callers("helper", repo_id=test_repo_id)
        caller_names = [c["name"] for c in callers]
        assert "caller_func" in caller_names

        # 5. Repo Overview
        overview = queries.get_repository_overview(test_repo_id)
        assert overview is not None
        assert overview["function_count"] == 2

    finally:
        # Cleanup
        queries.delete_repository(test_repo_id)
        client.close()
