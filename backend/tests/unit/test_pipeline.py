"""Unit tests for IngestionPipeline and Phase 1 deliverable format."""

import json
from pathlib import Path

from app.ingestion.pipeline import IngestionPipeline


def test_pipeline_parses_sample_repository(tmp_path: Path):
    # Construct a sample mini-repository simulating auth and billing
    auth_dir = tmp_path / "app"
    auth_dir.mkdir(parents=True)

    auth_code = '''"""Authentication module."""
def verify_password(plain: str, hashed: str) -> bool:
    return check_hash(plain, hashed)

def get_user_by_email(email: str):
    return db.query(email)

def authenticate_user(email: str, password: str):
    user = get_user_by_email(email)
    if user and verify_password(password, user.password):
        return user
    return None
'''
    (auth_dir / "auth.py").write_text(auth_code, encoding="utf-8")

    billing_code = """class PaymentGateway:
    def charge(self, amount: float):
        validate_card()
        return send_transaction(amount)
"""
    (auth_dir / "billing.py").write_text(billing_code, encoding="utf-8")

    pipeline = IngestionPipeline()
    parsed_repo = pipeline.parse_repository(tmp_path, repo_name="demo_repo")

    assert parsed_repo.repo_name == "demo_repo"
    assert parsed_repo.total_files == 2
    assert parsed_repo.total_classes == 1
    # 3 auth functions + 1 class method
    assert parsed_repo.total_functions == 4

    # Test deliverable dictionary output
    summary = parsed_repo.to_summary_dict()
    assert len(summary) == 2

    auth_summary = next(item for item in summary if item["file"] == "app/auth.py")
    funcs_by_name = {fn["name"]: fn for fn in auth_summary["functions"]}

    assert "authenticate_user" in funcs_by_name
    auth_fn = funcs_by_name["authenticate_user"]
    assert "get_user_by_email" in auth_fn["calls"]
    assert "verify_password" in auth_fn["calls"]
    assert auth_fn["start_line"] > 0
    assert auth_fn["end_line"] >= auth_fn["start_line"]

    # Test JSON serialization produces valid JSON
    json_output = parsed_repo.to_summary_json()
    loaded = json.loads(json_output)
    assert isinstance(loaded, list)
    assert len(loaded) == 2


def test_pipeline_convenience_methods(tmp_path: Path):
    (tmp_path / "simple.py").write_text("def hello(): pass", encoding="utf-8")

    dict_output = IngestionPipeline.parse_to_dict(tmp_path)
    assert len(dict_output) == 1
    assert dict_output[0]["file"] == "simple.py"
    assert dict_output[0]["functions"][0]["name"] == "hello"

    json_output = IngestionPipeline.parse_to_json(tmp_path)
    assert '"name": "hello"' in json_output
