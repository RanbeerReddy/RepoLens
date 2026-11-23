"""Unit tests for PythonASTParser."""

import pytest

from app.parser.ast_parser import PythonASTParser


@pytest.fixture
def parser():
    return PythonASTParser(repo_name="test_repo")


def test_parse_simple_functions(parser):
    code = '''"""Module docstring."""
import os
from typing import Optional, List

def calculate_total(items: List[float], tax_rate: float = 0.05) -> float:
    """Calculate total price with tax."""
    subtotal = sum(items)
    return apply_tax(subtotal, tax_rate)

async def fetch_user(user_id: int) -> Optional[dict]:
    return await api_client.get(user_id)
'''
    parsed = parser.parse_file("app/billing.py", code, file_hash="hash123")

    assert parsed.syntax_valid is True
    assert parsed.docstring == "Module docstring."
    assert parsed.file_path == "app/billing.py"
    assert parsed.file_hash == "hash123"

    # Imports
    assert len(parsed.imports) == 2
    assert parsed.imports[0].names == ["os"]
    assert parsed.imports[1].module == "typing"
    assert "Optional" in parsed.imports[1].names

    # Functions
    assert len(parsed.functions) == 2

    fn1 = parsed.functions[0]
    assert fn1.name == "calculate_total"
    assert fn1.qualified_name == "app.billing.calculate_total"
    assert fn1.start_line == 5
    assert fn1.docstring == "Calculate total price with tax."
    assert fn1.calls == ["sum", "apply_tax"]
    assert "items" in fn1.parameters
    assert "tax_rate" in fn1.parameters
    assert fn1.return_type == "float"
    assert fn1.is_async is False
    assert fn1.id == "func:app/billing.py:global:calculate_total"

    fn2 = parsed.functions[1]
    assert fn2.name == "fetch_user"
    assert fn2.is_async is True
    assert fn2.return_type == "Optional[dict]"


def test_parse_classes_and_methods(parser):
    code = """
class BaseService:
    pass

class UserService(BaseService):
    \"\"\"Service managing user lifecycle.\"\"\"

    def __init__(self, db_session):
        self.db = db_session

    @classmethod
    def get_version(cls) -> str:
        return "1.0"

    def authenticate(self, username, password):
        user = self.get_by_username(username)
        return verify_hash(password, user.password_hash)
"""
    parsed = parser.parse_file("services/user.py", code)
    assert len(parsed.classes) == 2

    user_svc = parsed.classes[1]
    assert user_svc.name == "UserService"
    assert user_svc.qualified_name == "services.user.UserService"
    assert user_svc.bases == ["BaseService"]
    assert user_svc.docstring == "Service managing user lifecycle."
    assert len(user_svc.methods) == 3

    auth_method = user_svc.methods[2]
    assert auth_method.name == "authenticate"
    assert auth_method.is_method is True
    assert auth_method.class_name == "UserService"
    assert auth_method.qualified_name == "services.user.UserService.authenticate"
    assert auth_method.id == "func:services/user.py:UserService:authenticate"
    assert "get_by_username" in auth_method.calls
    assert "verify_hash" in auth_method.calls

    # Test all_functions helper
    all_funcs = parsed.get_all_functions()
    assert len(all_funcs) == 3


def test_syntax_error_resilience(parser):
    invalid_code = "def broken_syntax(x: return x +"
    parsed = parser.parse_file("broken.py", invalid_code)
    assert parsed.syntax_valid is False
    assert parsed.error_message is not None
    assert "SyntaxError" in parsed.error_message
    assert len(parsed.functions) == 0


def test_source_code_slice_extraction(parser):
    code = """# comment
def target_func():
    a = 1
    b = 2
    return a + b
# end comment
"""
    parsed = parser.parse_file("sample.py", code)
    fn = parsed.functions[0]
    assert fn.start_line == 2
    assert fn.end_line == 5
    assert "def target_func():" in fn.source
    assert "return a + b" in fn.source
