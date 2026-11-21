"""Core Python AST parser – extracts functions, classes, imports, and call sites."""

from __future__ import annotations

import ast
import hashlib
import logging
from pathlib import Path

from .models import (
    ParsedClass,
    ParsedFunction,
    ParsedFunctionCall,
    ParsedImport,
    ParsedModule,
)

logger = logging.getLogger(__name__)


class PythonASTParser:
    """Parse a single Python file into structured :class:`ParsedModule` data."""

    def __init__(self, repo_id: str, repo_root: str) -> None:
        self.repo_id = repo_id
        self.repo_root = Path(repo_root).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: str) -> ParsedModule:
        """Read *file_path*, parse its AST, and return a :class:`ParsedModule`.

        Syntax errors and encoding errors are handled gracefully: the returned
        ``ParsedModule`` will have its ``error`` field populated instead of
        raising an exception.
        """
        abs_path = Path(file_path).resolve()
        try:
            rel_path = str(abs_path.relative_to(self.repo_root))
        except ValueError:
            rel_path = str(abs_path)

        # Attempt to read the file ------------------------------------------------
        try:
            source = abs_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError) as exc:
            return self._error_module(rel_path, 0, f"Could not read file: {exc}")

        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        size_bytes = abs_path.stat().st_size

        # Attempt to parse --------------------------------------------------------
        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as exc:
            return self._error_module(
                rel_path,
                size_bytes,
                f"SyntaxError: {exc.msg} (line {exc.lineno})",
                source_hash=source_hash,
            )

        module_docstring = ast.get_docstring(tree)
        imports = self._extract_imports(tree)
        functions = self._extract_functions(tree, source, rel_path, parent_class=None)
        classes = self._extract_classes(tree, source, rel_path)

        entity_id = self._make_entity_id(rel_path, "module", rel_path)

        return ParsedModule(
            file_path=rel_path,
            entity_id=entity_id,
            repo_id=self.repo_id,
            source_hash=source_hash,
            size_bytes=size_bytes,
            imports=imports,
            functions=functions,
            classes=classes,
            module_docstring=module_docstring,
            error=None,
        )

    # ------------------------------------------------------------------
    # Import extraction
    # ------------------------------------------------------------------

    def _extract_imports(self, tree: ast.Module) -> list[ParsedImport]:
        imports: list[ParsedImport] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ParsedImport(
                            module=alias.name,
                            names=[alias.name],
                            alias=alias.asname,
                            is_from=False,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                names = [a.name for a in node.names]
                imports.append(
                    ParsedImport(
                        module=module_name,
                        names=names,
                        alias=None,
                        is_from=True,
                        line_number=node.lineno,
                    )
                )
        return imports

    # ------------------------------------------------------------------
    # Function extraction
    # ------------------------------------------------------------------

    def _extract_functions(
        self,
        node: ast.AST,
        source: str,
        file_path: str,
        parent_class: str | None = None,
    ) -> list[ParsedFunction]:
        functions: list[ParsedFunction] = []
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._build_parsed_function(child, source, file_path, parent_class)
                functions.append(func)
        return functions

    def _build_parsed_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
        file_path: str,
        parent_class: str | None,
    ) -> ParsedFunction:
        name = func_node.name
        qualified_name = f"{parent_class}.{name}" if parent_class else name
        is_async = isinstance(func_node, ast.AsyncFunctionDef)
        is_method = parent_class is not None

        line_start = func_node.lineno
        line_end = func_node.end_lineno or func_node.lineno
        func_source = self._get_source_segment(source, func_node)
        signature = self._build_signature(func_node)
        docstring = ast.get_docstring(func_node)
        decorators = self._extract_decorators(func_node)
        calls = self._extract_function_calls(func_node, context=qualified_name)
        args = self._extract_args(func_node)

        entity_id = self._make_entity_id(file_path, "function", qualified_name)

        return ParsedFunction(
            name=name,
            qualified_name=qualified_name,
            entity_id=entity_id,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            source=func_source,
            signature=signature,
            docstring=docstring,
            decorators=decorators,
            is_method=is_method,
            is_async=is_async,
            calls=calls,
            args=args,
        )

    # ------------------------------------------------------------------
    # Class extraction
    # ------------------------------------------------------------------

    def _extract_classes(
        self,
        node: ast.AST,
        source: str,
        file_path: str,
    ) -> list[ParsedClass]:
        classes: list[ParsedClass] = []
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                cls = self._build_parsed_class(child, source, file_path)
                classes.append(cls)
        return classes

    def _build_parsed_class(
        self,
        class_node: ast.ClassDef,
        source: str,
        file_path: str,
    ) -> ParsedClass:
        name = class_node.name
        qualified_name = name
        line_start = class_node.lineno
        line_end = class_node.end_lineno or class_node.lineno
        class_source = self._get_source_segment(source, class_node)
        docstring = ast.get_docstring(class_node)
        decorators = self._extract_decorators(class_node)
        bases = self._extract_bases(class_node)
        methods = self._extract_functions(class_node, source, file_path, parent_class=name)

        entity_id = self._make_entity_id(file_path, "class", qualified_name)

        return ParsedClass(
            name=name,
            qualified_name=qualified_name,
            entity_id=entity_id,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            source=class_source,
            docstring=docstring,
            decorators=decorators,
            bases=bases,
            methods=methods,
        )

    # ------------------------------------------------------------------
    # Function-call extraction
    # ------------------------------------------------------------------

    def _extract_function_calls(
        self,
        node: ast.AST,
        context: str | None = None,
    ) -> list[ParsedFunctionCall]:
        calls: list[ParsedFunctionCall] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            name, qualified = self._resolve_call_name(child.func)
            if name is None:
                continue
            calls.append(
                ParsedFunctionCall(
                    name=name,
                    qualified_name=qualified,
                    line_number=getattr(child, "lineno", 0),
                    context=context,
                )
            )
        return calls

    @staticmethod
    def _resolve_call_name(func_node: ast.expr) -> tuple[str | None, str | None]:
        """Return ``(simple_name, qualified_name | None)`` for a call target.

        Handles:
        - ``func()``           → ("func", None)
        - ``obj.method()``     → ("method", "obj.method")
        - ``a.b.c()``          → ("c", "a.b.c")
        """
        if isinstance(func_node, ast.Name):
            return func_node.id, None
        if isinstance(func_node, ast.Attribute):
            parts: list[str] = [func_node.attr]
            value = func_node.value
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
            parts.reverse()
            qualified = ".".join(parts)
            return func_node.attr, qualified
        return None, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_source_segment(source: str, node: ast.AST) -> str:
        """Extract the source text for *node*, falling back to line slicing."""
        try:
            segment = ast.get_source_segment(source, node)
            if segment is not None:
                return segment
        except (TypeError, AttributeError):
            pass

        # Fallback: slice by line range
        lines = source.splitlines()
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", start + 1)
        return "\n".join(lines[start:end])

    @staticmethod
    def _build_signature(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build a human-readable signature string such as ``(self, x: int, y='hello')``."""
        args = func_node.args
        parts: list[str] = []

        # Positional-only / regular positional args --------------------------------
        all_positional = args.posonlyargs + args.args
        defaults_offset = len(all_positional) - len(args.defaults)

        for idx, arg in enumerate(all_positional):
            part = arg.arg
            if arg.annotation:
                part += f": {ast.unparse(arg.annotation)}"
            default_idx = idx - defaults_offset
            if default_idx >= 0:
                part += f"={ast.unparse(args.defaults[default_idx])}"
            parts.append(part)
            # Mark end of positional-only section
            if arg in args.posonlyargs and arg is args.posonlyargs[-1]:
                parts.append("/")

        # *args -------------------------------------------------------------------
        if args.vararg:
            va = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                va += f": {ast.unparse(args.vararg.annotation)}"
            parts.append(va)
        elif args.kwonlyargs:
            parts.append("*")

        # Keyword-only args -------------------------------------------------------
        for idx, arg in enumerate(args.kwonlyargs):
            part = arg.arg
            if arg.annotation:
                part += f": {ast.unparse(arg.annotation)}"
            default = args.kw_defaults[idx]
            if default is not None:
                part += f"={ast.unparse(default)}"
            parts.append(part)

        # **kwargs ----------------------------------------------------------------
        if args.kwarg:
            kw = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kw += f": {ast.unparse(args.kwarg.annotation)}"
            parts.append(kw)

        sig = f"({', '.join(parts)})"

        # Return annotation -------------------------------------------------------
        if func_node.returns:
            sig += f" -> {ast.unparse(func_node.returns)}"

        return sig

    @staticmethod
    def _extract_decorators(
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> list[str]:
        return [ast.unparse(d) for d in node.decorator_list]

    @staticmethod
    def _extract_bases(class_node: ast.ClassDef) -> list[str]:
        return [ast.unparse(b) for b in class_node.bases]

    @staticmethod
    def _extract_args(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Return a flat list of argument names (positional, keyword, *args, **kwargs)."""
        names: list[str] = []
        for a in func_node.args.posonlyargs:
            names.append(a.arg)
        for a in func_node.args.args:
            names.append(a.arg)
        if func_node.args.vararg:
            names.append(f"*{func_node.args.vararg.arg}")
        for a in func_node.args.kwonlyargs:
            names.append(a.arg)
        if func_node.args.kwarg:
            names.append(f"**{func_node.args.kwarg.arg}")
        return names

    def _make_entity_id(self, file_path: str, entity_type: str, qualified_name: str) -> str:
        return f"{self.repo_id}:{file_path}:{entity_type}:{qualified_name}"

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _error_module(
        self,
        rel_path: str,
        size_bytes: int,
        error_msg: str,
        source_hash: str = "",
    ) -> ParsedModule:
        logger.warning("Parse error for %s: %s", rel_path, error_msg)
        return ParsedModule(
            file_path=rel_path,
            entity_id=self._make_entity_id(rel_path, "module", rel_path),
            repo_id=self.repo_id,
            source_hash=source_hash,
            size_bytes=size_bytes,
            imports=[],
            functions=[],
            classes=[],
            module_docstring=None,
            error=error_msg,
        )
