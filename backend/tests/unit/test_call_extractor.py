"""Unit tests for CallExtractor."""

import ast

from app.parser.call_extractor import CallExtractor


def test_direct_calls():
    code = """
def process():
    init()
    step1()
    step2()
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    distinct_calls, sites = CallExtractor.extract_from_node(func_node, caller_name="process")
    assert distinct_calls == ["init", "step1", "step2"]
    assert len(sites) == 3
    assert sites[0].callee_name == "init"
    assert sites[0].line_number == 3
    assert not sites[0].is_method_call


def test_method_and_chained_calls():
    code = """
def handle(user, db):
    user.validate()
    db.session.query().filter().first()
    self.send_email(user.email)
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    distinct_calls, sites = CallExtractor.extract_from_node(func_node, caller_name="handle")
    assert "validate" in distinct_calls
    assert "send_email" in distinct_calls
    assert "first" in distinct_calls
    # Verify is_method_call flag
    method_sites = [s for s in sites if s.callee_name == "validate"]
    assert len(method_sites) == 1
    assert method_sites[0].is_method_call is True


def test_calls_inside_arguments():
    code = """
def compute():
    return format_result(calculate_sum(get_items()))
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    distinct_calls, sites = CallExtractor.extract_from_node(func_node)
    # Both outer and inner calls should be captured
    assert "format_result" in distinct_calls
    assert "calculate_sum" in distinct_calls
    assert "get_items" in distinct_calls


def test_does_not_enter_nested_functions():
    code = """
def outer():
    start()
    def inner():
        inner_only_call()
    finish()
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    distinct_calls, sites = CallExtractor.extract_from_node(func_node)
    assert distinct_calls == ["start", "finish"]
    assert "inner_only_call" not in distinct_calls
