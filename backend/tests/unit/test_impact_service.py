"""Unit tests for Change Impact Analysis Service."""

from unittest.mock import MagicMock

from app.graph.neo4j_client import Neo4jClient
from app.llm.vllm_client import LLMError, VLLMClient
from app.services.impact_service import ImpactLevel, ImpactService


def test_classify_impact_heuristics():
    # Zero callers -> LOW
    lvl, _ = ImpactService._classify_impact(0, 0, 1)
    assert lvl == ImpactLevel.LOW

    # 1 direct, 1 indirect, 2 files -> LOW
    lvl, _ = ImpactService._classify_impact(1, 1, 2)
    assert lvl == ImpactLevel.LOW

    # 3 direct callers -> MEDIUM
    lvl, _ = ImpactService._classify_impact(3, 1, 2)
    assert lvl == ImpactLevel.MEDIUM

    # >5 direct callers or >3 files -> HIGH
    lvl, _ = ImpactService._classify_impact(6, 2, 2)
    assert lvl == ImpactLevel.HIGH
    lvl, _ = ImpactService._classify_impact(2, 2, 4)
    assert lvl == ImpactLevel.HIGH


def test_analyze_impact_traversal_and_reporting():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_llm = MagicMock(spec=VLLMClient)

    # Mock Target details
    mock_client.execute_read.side_effect = [
        # Call 1: TARGET_DETAILS_QUERY
        [
            {
                "id": "fn:auth:authenticate_user",
                "name": "authenticate_user",
                "qualified_name": "app.auth.authenticate_user",
                "file_path": "app/auth.py",
            }
        ],
        # Call 2: REVERSE_CALLERS_QUERY
        [
            # Depth 1: login() -> authenticate_user()
            {
                "path_nodes": [
                    {
                        "id": "fn:routes:login",
                        "name": "login",
                        "qualified_name": "app.routes.auth.login",
                        "file_path": "app/routes/auth.py",
                        "start_line": 15,
                        "end_line": 30,
                        "is_method": False,
                    },
                    {
                        "id": "fn:auth:authenticate_user",
                        "name": "authenticate_user",
                        "qualified_name": "app.auth.authenticate_user",
                        "file_path": "app/auth.py",
                        "start_line": 20,
                        "end_line": 42,
                        "is_method": False,
                    },
                ],
                "depth": 1,
            },
            # Depth 2: handle_request() -> login() -> authenticate_user()
            {
                "path_nodes": [
                    {
                        "id": "fn:app:handle_request",
                        "name": "handle_request",
                        "qualified_name": "app.main.handle_request",
                        "file_path": "app/main.py",
                        "start_line": 50,
                        "end_line": 65,
                        "is_method": False,
                    },
                    {
                        "id": "fn:routes:login",
                        "name": "login",
                        "qualified_name": "app.routes.auth.login",
                        "file_path": "app/routes/auth.py",
                        "start_line": 15,
                        "end_line": 30,
                        "is_method": False,
                    },
                    {
                        "id": "fn:auth:authenticate_user",
                        "name": "authenticate_user",
                        "qualified_name": "app.auth.authenticate_user",
                        "file_path": "app/auth.py",
                        "start_line": 20,
                        "end_line": 42,
                        "is_method": False,
                    },
                ],
                "depth": 2,
            },
            # Test caller: test_auth() -> authenticate_user()
            {
                "path_nodes": [
                    {
                        "id": "fn:test:test_authenticate",
                        "name": "test_authenticate",
                        "qualified_name": "tests.test_auth.test_authenticate",
                        "file_path": "tests/test_auth.py",
                        "start_line": 5,
                        "end_line": 15,
                        "is_method": False,
                    },
                    {
                        "id": "fn:auth:authenticate_user",
                        "name": "authenticate_user",
                        "qualified_name": "app.auth.authenticate_user",
                        "file_path": "app/auth.py",
                        "start_line": 20,
                        "end_line": 42,
                        "is_method": False,
                    },
                ],
                "depth": 1,
            },
        ],
        # Call 3: CALLEES_QUERY
        [
            {
                "id": "fn:auth:verify_password",
                "name": "verify_password",
                "qualified_name": "app.auth.verify_password",
                "file_path": "app/auth.py",
                "start_line": 5,
                "end_line": 10,
                "is_method": False,
            }
        ],
    ]

    mock_llm.generate.return_value = (
        "Changes to authenticate_user affect login endpoints and test suites. "
        "Review app/routes/auth.py before updating."
    )

    service = ImpactService(neo4j_client=mock_client, llm_client=mock_llm)
    report = service.analyze_impact("authenticate_user")

    assert report.target_function == "authenticate_user"
    assert report.target_file_path == "app/auth.py"

    # Direct callers: login, test_authenticate
    assert len(report.direct_callers) == 2
    direct_names = [c.name for c in report.direct_callers]
    assert "login" in direct_names
    assert "test_authenticate" in direct_names

    # Indirect callers: handle_request
    assert len(report.indirect_callers) == 1
    assert report.indirect_callers[0].name == "handle_request"

    # Callees: verify_password
    assert len(report.callees) == 1
    assert report.callees[0].name == "verify_password"

    # Affected files and tests
    assert "app/auth.py" in report.affected_files
    assert "app/routes/auth.py" in report.affected_files
    assert "tests/test_auth.py" in report.relevant_tests

    # Dependency paths
    assert any("login() -> authenticate_user()" in p for p in report.dependency_paths)

    # LLM summary
    assert report.llm_used is True
    assert "Changes to authenticate_user" in report.analysis_summary
    assert "statically detected" in report.disclaimer


def test_analyze_impact_offline_llm_fallback():
    mock_client = MagicMock(spec=Neo4jClient)
    mock_llm = MagicMock(spec=VLLMClient)
    mock_llm.generate.side_effect = LLMError("vLLM offline")

    mock_client.execute_read.side_effect = [
        [{"name": "helper", "qualified_name": "app.helper", "file_path": "app/utils.py"}],
        [],  # No callers
        [],  # No callees
    ]

    service = ImpactService(neo4j_client=mock_client, llm_client=mock_llm)
    report = service.analyze_impact("helper")

    assert report.impact_level == ImpactLevel.LOW
    assert report.llm_used is False
    assert "Modifying 'helper()'" in report.analysis_summary
