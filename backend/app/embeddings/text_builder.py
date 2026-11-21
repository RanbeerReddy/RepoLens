"""Build text representations of code entities for embedding generation.

Each builder function takes a parsed entity and returns a human-readable text
string that captures the entity's semantics.  Outputs are truncated to roughly
512 tokens worth of characters (~2 048 chars, using the ≈4 chars/token rule of
thumb for English text with code).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parser.models import ParsedClass, ParsedFunction, ParsedModule

_MAX_CHARS = 2048


def _truncate(text: str, max_chars: int = _MAX_CHARS) -> str:
    """Truncate *text* to *max_chars*, appending '…' when shortened."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


# ------------------------------------------------------------------ #
#  Public builders
# ------------------------------------------------------------------ #


def build_function_text(func: ParsedFunction) -> str:
    """Combine a function's metadata into an embeddable text representation.

    Includes: name, signature, docstring (if any), and the first N lines of
    the source body.
    """
    parts: list[str] = []

    # Name and signature
    prefix = "async " if func.is_async else ""
    kind = "method" if func.is_method else "function"
    parts.append(f"Python {kind}: {prefix}{func.signature}")

    # Decorators
    if func.decorators:
        parts.append("Decorators: " + ", ".join(func.decorators))

    # Docstring
    if func.docstring:
        parts.append(f"Description: {func.docstring}")

    # Arguments
    if func.args:
        parts.append("Arguments: " + ", ".join(func.args))

    # Source body (first ~20 lines after the def line)
    if func.source:
        source_lines = func.source.splitlines()
        # Skip the def/signature line(s) and take the body
        body_lines = source_lines[1:21]
        if body_lines:
            parts.append("Body:\n" + "\n".join(body_lines))

    return _truncate("\n".join(parts))


def build_class_text(cls: ParsedClass) -> str:
    """Combine a class's metadata into an embeddable text representation.

    Includes: name, base classes, docstring, and method names.
    """
    parts: list[str] = []

    # Name and bases
    bases_str = ", ".join(cls.bases) if cls.bases else ""
    if bases_str:
        parts.append(f"Python class: {cls.name}({bases_str})")
    else:
        parts.append(f"Python class: {cls.name}")

    # Decorators
    if cls.decorators:
        parts.append("Decorators: " + ", ".join(cls.decorators))

    # Docstring
    if cls.docstring:
        parts.append(f"Description: {cls.docstring}")

    # Method names with signatures
    if cls.methods:
        method_lines: list[str] = []
        for method in cls.methods:
            prefix = "async " if method.is_async else ""
            method_lines.append(f"  {prefix}{method.signature}")
        parts.append("Methods:\n" + "\n".join(method_lines))

    return _truncate("\n".join(parts))


def build_file_text(module: ParsedModule) -> str:
    """Combine a module's metadata into an embeddable text representation.

    Includes: file path, module docstring, import summary, and the names
    of defined functions and classes.
    """
    parts: list[str] = []

    # File path
    parts.append(f"Python file: {module.file_path}")

    # Module docstring
    if module.module_docstring:
        parts.append(f"Description: {module.module_docstring}")

    # Imports summary
    if module.imports:
        import_names: list[str] = []
        for imp in module.imports:
            if imp.is_from:
                names_str = ", ".join(imp.names) if imp.names else "*"
                import_names.append(f"from {imp.module} import {names_str}")
            else:
                import_names.append(f"import {imp.module}")
        # Only include first 15 imports to stay within budget
        if len(import_names) > 15:
            import_names = import_names[:15] + [f"... and {len(import_names) - 15} more"]
        parts.append("Imports: " + "; ".join(import_names))

    # Function names
    if module.functions:
        func_names = [f.name for f in module.functions]
        parts.append("Functions: " + ", ".join(func_names))

    # Class names
    if module.classes:
        class_entries: list[str] = []
        for cls in module.classes:
            method_names = [m.name for m in cls.methods]
            if method_names:
                class_entries.append(
                    f"{cls.name} (methods: {', '.join(method_names)})"
                )
            else:
                class_entries.append(cls.name)
        parts.append("Classes: " + "; ".join(class_entries))

    return _truncate("\n".join(parts))
