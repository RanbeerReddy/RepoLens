"""Call site extractor for Python AST.

Extracts all function and method calls made within a function body or scope,
resolving identifier names, method attributes, and line numbers.
"""

from __future__ import annotations

import ast
from typing import Optional

from app.parser.models import CallSite


class CallExtractor(ast.NodeVisitor):
    """
    AST visitor that extracts function and method call sites within a function body.

    Prevents recursing into nested function or class definitions, ensuring
    extracted calls belong strictly to the target function's scope.
    """

    def __init__(self, caller_name: str = "") -> None:
        self.caller_name = caller_name
        self.call_sites: list[CallSite] = []
        self._seen_calls: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        callee_name, raw_expr, is_method = self._resolve_call_target(node.func)
        if callee_name:
            site = CallSite(
                callee_name=callee_name,
                raw_expression=raw_expr,
                line_number=getattr(node, "lineno", 0),
                is_method_call=is_method,
            )
            self.call_sites.append(site)
            self._seen_calls.add(callee_name)

        # Continue visiting arguments and keywords (calls could be inside args: foo(bar()))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        # Do not enter nested functions; they will be parsed as independent entities
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        # Do not enter nested async functions
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        # Do not enter nested classes
        return

    @classmethod
    def extract_from_node(
        cls, node: ast.AST, caller_name: str = ""
    ) -> tuple[list[str], list[CallSite]]:
        """
        Extracts distinct call names and detailed call sites from an AST node.

        Returns:
            Tuple of (distinct call names preserving order, list of detailed CallSite objects)
        """
        extractor = cls(caller_name=caller_name)
        # Walk children of the node rather than the node itself to avoid stopping at top FunctionDef
        for child in ast.iter_child_nodes(node):
            extractor.visit(child)

        # Preserve order of distinct calls
        distinct_names: list[str] = []
        seen: set[str] = set()
        for site in extractor.call_sites:
            if site.callee_name not in seen:
                seen.add(site.callee_name)
                distinct_names.append(site.callee_name)

        return distinct_names, extractor.call_sites

    @staticmethod
    def _resolve_call_target(node: ast.AST) -> tuple[Optional[str], str, bool]:
        """
        Resolves an AST node representing the function expression of a call.

        Returns:
            (callee_name, raw_expression, is_method_call)
        """
        if isinstance(node, ast.Name):
            # Direct call: foo() -> 'foo'
            return node.id, node.id, False

        if isinstance(node, ast.Attribute):
            # Method or attribute call: obj.method() -> callee: 'method', raw: 'obj.method'
            raw = CallExtractor._unparse_safe(node)
            return node.attr, raw, True

        if isinstance(node, ast.Call):
            # Chained call: factory().create() -> callee: 'create'
            raw = CallExtractor._unparse_safe(node)
            if isinstance(node.func, ast.Attribute):
                return node.func.attr, raw, True
            return None, raw, False

        # Other call forms (e.g., subscripted function lookup, lambda call)
        raw = CallExtractor._unparse_safe(node)
        return None, raw, False

    @staticmethod
    def _unparse_safe(node: ast.AST) -> str:
        """Safely unparses an AST node back to source text."""
        try:
            return ast.unparse(node)
        except Exception:
            return "<expr>"
