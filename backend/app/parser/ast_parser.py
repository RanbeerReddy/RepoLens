"""Python AST Parser for RepoLens.

Parses Python source files into structured code entities:
- Module docstrings
- Imports and alias maps
- Classes and inheritance bases
- Functions, signatures, docstrings, line numbers, and call sites
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath
from typing import Optional

from app.parser.call_extractor import CallExtractor
from app.parser.models import (
    ClassEntity,
    FunctionEntity,
    ImportEntity,
    ParsedFile,
)


class PythonASTParser:
    """Deterministic AST parser for Python source files."""

    def __init__(self, repo_name: str = "") -> None:
        self.repo_name = repo_name

    def parse_file(
        self,
        file_path: str,
        source_code: str,
        file_hash: str = "",
    ) -> ParsedFile:
        """
        Parses a single Python file into a ParsedFile entity.

        Args:
            file_path: Normalized relative POSIX path, e.g. 'app/core/auth.py'
            source_code: Full string content of the Python file
            file_hash: SHA-256 hash of the file content

        Returns:
            ParsedFile containing all extracted code entities
        """
        normalized_path = self._normalize_path(file_path)
        file_id = f"file:{normalized_path}"
        lines = source_code.splitlines(keepends=True)
        total_lines = len(lines)
        size_bytes = len(source_code.encode("utf-8", errors="replace"))

        try:
            tree = ast.parse(source_code, filename=normalized_path)
        except SyntaxError as err:
            return ParsedFile(
                id=file_id,
                file_path=normalized_path,
                file_hash=file_hash,
                size_bytes=size_bytes,
                total_lines=total_lines,
                syntax_valid=False,
                error_message=f"SyntaxError at line {err.lineno}: {err.msg}",
            )
        except Exception as err:
            return ParsedFile(
                id=file_id,
                file_path=normalized_path,
                file_hash=file_hash,
                size_bytes=size_bytes,
                total_lines=total_lines,
                syntax_valid=False,
                error_message=f"Parse failure: {type(err).__name__}: {str(err)}",
            )

        module_docstring = ast.get_docstring(tree)
        module_qual_path = self._module_path_from_file(normalized_path)

        imports: list[ImportEntity] = []
        classes: list[ClassEntity] = []
        functions: list[FunctionEntity] = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_ent = self._parse_import(node)
                if import_ent:
                    imports.append(import_ent)

            elif isinstance(node, ast.ClassDef):
                cls_ent = self._parse_class(
                    node=node,
                    file_path=normalized_path,
                    module_qual_path=module_qual_path,
                    lines=lines,
                )
                classes.append(cls_ent)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_ent = self._parse_function(
                    node=node,
                    file_path=normalized_path,
                    module_qual_path=module_qual_path,
                    lines=lines,
                    is_method=False,
                    class_name=None,
                )
                functions.append(func_ent)

        return ParsedFile(
            id=file_id,
            file_path=normalized_path,
            file_hash=file_hash,
            size_bytes=size_bytes,
            total_lines=total_lines,
            docstring=module_docstring,
            imports=imports,
            classes=classes,
            functions=functions,
            syntax_valid=True,
            error_message=None,
        )

    def _parse_import(self, node: ast.Import | ast.ImportFrom) -> Optional[ImportEntity]:
        """Extracts import details and alias mappings."""
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            alias_map = {alias.asname: alias.name for alias in node.names if alias.asname}
            return ImportEntity(
                module=None,
                names=names,
                alias_map=alias_map,
                is_relative=False,
                level=0,
                start_line=node.lineno,
            )

        if isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            alias_map = {alias.asname: alias.name for alias in node.names if alias.asname}
            is_relative = (node.level or 0) > 0
            return ImportEntity(
                module=node.module,
                names=names,
                alias_map=alias_map,
                is_relative=is_relative,
                level=node.level or 0,
                start_line=node.lineno,
            )

        return None

    def _parse_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        module_qual_path: str,
        lines: list[str],
    ) -> ClassEntity:
        """Extracts a class definition, inheritance bases, and methods."""
        class_name = node.name
        qualified_name = f"{module_qual_path}.{class_name}" if module_qual_path else class_name
        class_id = f"class:{file_path}:{class_name}"

        docstring = ast.get_docstring(node)
        bases = [self._unparse_safe(b) for b in node.bases]
        decorators = [self._unparse_safe(d) for d in node.decorator_list]

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        methods: list[FunctionEntity] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_ent = self._parse_function(
                    node=child,
                    file_path=file_path,
                    module_qual_path=module_qual_path,
                    lines=lines,
                    is_method=True,
                    class_name=class_name,
                )
                methods.append(method_ent)

        return ClassEntity(
            id=class_id,
            name=class_name,
            qualified_name=qualified_name,
            file_path=file_path,
            docstring=docstring,
            start_line=start_line,
            end_line=end_line,
            bases=bases,
            methods=methods,
            decorators=decorators,
        )

    def _parse_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        module_qual_path: str,
        lines: list[str],
        is_method: bool = False,
        class_name: Optional[str] = None,
    ) -> FunctionEntity:
        """Extracts a function or method definition, signature, and call sites."""
        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)

        if is_method and class_name:
            scope_prefix = f"{class_name}."
            scope_id = f"{class_name}:{func_name}"
        else:
            scope_prefix = ""
            scope_id = f"global:{func_name}"

        qualified_name = (
            f"{module_qual_path}.{scope_prefix}{func_name}"
            if module_qual_path
            else f"{scope_prefix}{func_name}"
        )
        func_id = f"func:{file_path}:{scope_id}"

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)

        # Extract source slice safely
        source_snippet = self._extract_source_slice(lines, start_line, end_line)

        # Extract signature, parameters, and return type
        signature, parameters, return_type = self._extract_signature(node)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Extract decorators
        decorators = [self._unparse_safe(d) for d in node.decorator_list]

        # Extract calls
        distinct_calls, call_sites = CallExtractor.extract_from_node(node, caller_name=func_name)

        return FunctionEntity(
            id=func_id,
            name=func_name,
            qualified_name=qualified_name,
            file_path=file_path,
            signature=signature,
            docstring=docstring,
            source=source_snippet,
            start_line=start_line,
            end_line=end_line,
            calls=distinct_calls,
            call_sites=call_sites,
            decorators=decorators,
            parameters=parameters,
            return_type=return_type,
            is_async=is_async,
            is_method=is_method,
            class_name=class_name,
        )

    def _extract_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> tuple[str, list[str], Optional[str]]:
        """Constructs a clean normalized function signature string."""
        func_name = node.name
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "

        param_names: list[str] = []
        param_strs: list[str] = []

        args = node.args

        # Positional-only args (Python 3.8+)
        for arg in getattr(args, "posonlyargs", []):
            param_names.append(arg.arg)
            param_strs.append(self._format_arg(arg))
        if getattr(args, "posonlyargs", []):
            param_strs.append("/")

        # Standard args
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            param_names.append(arg.arg)
            default_val = None
            if i >= defaults_offset:
                default_idx = i - defaults_offset
                default_val = self._unparse_safe(args.defaults[default_idx])
            param_strs.append(self._format_arg(arg, default_val))

        # Vararg (*args)
        if args.vararg:
            param_names.append(f"*{args.vararg.arg}")
            param_strs.append(f"*{self._format_arg(args.vararg)}")
        elif args.kwonlyargs:
            param_strs.append("*")

        # Keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            param_names.append(arg.arg)
            default_val = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default_val = self._unparse_safe(args.kw_defaults[i])
            param_strs.append(self._format_arg(arg, default_val))

        # Kwarg (**kwargs)
        if args.kwarg:
            param_names.append(f"**{args.kwarg.arg}")
            param_strs.append(f"**{self._format_arg(args.kwarg)}")

        return_annotation: Optional[str] = None
        if node.returns:
            return_annotation = self._unparse_safe(node.returns)

        params_joined = ", ".join(param_strs)
        if return_annotation:
            full_sig = f"{prefix}{func_name}({params_joined}) -> {return_annotation}"
        else:
            full_sig = f"{prefix}{func_name}({params_joined})"

        return full_sig, param_names, return_annotation

    def _format_arg(self, arg: ast.arg, default: Optional[str] = None) -> str:
        """Formats an ast.arg with optional type annotation and default value."""
        base = arg.arg
        if arg.annotation:
            ann = self._unparse_safe(arg.annotation)
            base = f"{base}: {ann}"
        if default is not None:
            base = f"{base}={default}"
        return base

    @staticmethod
    def _extract_source_slice(lines: list[str], start_line: int, end_line: int) -> str:
        """Extracts exact lines 1-based [start_line..end_line] from the file."""
        if not lines:
            return ""
        # 1-based line indexing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        return "".join(lines[start_idx:end_idx]).strip("\r\n")

    @staticmethod
    def _normalize_path(path_str: str) -> str:
        """Converts backslashes to forward slashes and removes leading dot slashes."""
        posix = PurePosixPath(path_str.replace("\\", "/"))
        return str(posix)

    @staticmethod
    def _module_path_from_file(file_path: str) -> str:
        """
        Converts file path to python module dot notation.
        e.g. 'app/core/auth.py' -> 'app.core.auth'
             'app/__init__.py' -> 'app'
        """
        clean = file_path.replace("\\", "/")
        if clean.endswith(".py"):
            clean = clean[:-3]
        parts = clean.split("/")
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(p for p in parts if p and p != ".")

    @staticmethod
    def _unparse_safe(node: Optional[ast.AST]) -> str:
        """Safely unparses an AST node or returns empty string."""
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return "<expr>"
