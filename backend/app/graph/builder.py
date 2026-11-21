"""Graph builder – takes parsed modules and populates the Neo4j graph."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.graph.operations import GraphOperations

if TYPE_CHECKING:
    from app.parser.models import ParsedClass, ParsedFunction, ParsedModule

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Orchestrates creation of graph nodes and relationships from parsed code."""

    def __init__(self, graph_ops: GraphOperations) -> None:
        self._ops = graph_ops

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def build_file_graph(self, parsed_module: ParsedModule) -> None:
        """Create all graph entities for a single parsed file.

        Creates:
        - File node
        - Function nodes + DEFINES relationships from File
        - Class nodes + DEFINES relationships from File
        - HAS_METHOD relationships from Class to its methods
        - CALLS relationships between functions
        - IMPORTS relationships to other files
        - INHERITS relationships between classes
        """
        repo_id = parsed_module.repo_id
        file_path = parsed_module.file_path

        logger.debug("Building graph for %s in repo %s", file_path, repo_id)

        # 1. Create the File node
        await self._ops.create_file(
            repo_id=repo_id,
            file_path=file_path,
            relative_path=file_path,
            source_hash=parsed_module.source_hash,
            size_bytes=parsed_module.size_bytes,
            last_modified="",
        )

        # 2. Create top-level Function nodes
        function_ids: dict[str, str] = {}  # name -> entity_id
        for func in parsed_module.functions:
            await self._ops.create_function(
                entity_id=func.entity_id,
                name=func.name,
                qualified_name=func.qualified_name,
                file_path=file_path,
                repo_id=repo_id,
                line_start=func.line_start,
                line_end=func.line_end,
                source=func.source,
                signature=func.signature,
                docstring=func.docstring,
                is_method=func.is_method,
                is_async=func.is_async,
                decorators=func.decorators,
                args=func.args,
            )
            function_ids[func.name] = func.entity_id
            function_ids[func.qualified_name] = func.entity_id

        # 3. Create Class nodes and their methods
        class_ids: dict[str, str] = {}  # name -> entity_id
        for cls in parsed_module.classes:
            await self._ops.create_class(
                entity_id=cls.entity_id,
                name=cls.name,
                qualified_name=cls.qualified_name,
                file_path=file_path,
                repo_id=repo_id,
                line_start=cls.line_start,
                line_end=cls.line_end,
                source=cls.source,
                docstring=cls.docstring,
                decorators=cls.decorators,
                bases=cls.bases,
            )
            class_ids[cls.name] = cls.entity_id
            class_ids[cls.qualified_name] = cls.entity_id

            # Create method nodes and HAS_METHOD relationships
            for method in cls.methods:
                await self._ops.create_function(
                    entity_id=method.entity_id,
                    name=method.name,
                    qualified_name=method.qualified_name,
                    file_path=file_path,
                    repo_id=repo_id,
                    line_start=method.line_start,
                    line_end=method.line_end,
                    source=method.source,
                    signature=method.signature,
                    docstring=method.docstring,
                    is_method=True,
                    is_async=method.is_async,
                    decorators=method.decorators,
                    args=method.args,
                )
                function_ids[method.name] = method.entity_id
                function_ids[method.qualified_name] = method.entity_id

                # HAS_METHOD: Class -> Method
                await self._ops.create_relationship(
                    from_id=cls.entity_id,
                    to_id=method.entity_id,
                    rel_type="HAS_METHOD",
                )

        # 4. Resolve CALLS relationships
        await self._resolve_calls(parsed_module, function_ids)

        # 5. Resolve IMPORTS relationships
        await self._resolve_imports(parsed_module)

        # 6. Resolve INHERITS relationships
        await self._resolve_inherits(parsed_module, class_ids)

        logger.debug("Finished graph for %s", file_path)

    async def remove_stale_file(self, repo_id: str, file_path: str) -> None:
        """Remove all entities from a file that has been deleted or changed."""
        logger.debug(
            "Removing stale entities for %s in repo %s", file_path, repo_id
        )
        await self._ops.remove_file_entities(repo_id, file_path)

    async def build_repository_graph(
        self,
        repo_id: str,
        parsed_modules: list[ParsedModule],
    ) -> None:
        """Orchestrate full graph build for all parsed modules in a repository.

        Steps:
        1. Create/update the Repository node
        2. Build graph for each parsed module
        3. Resolve cross-file relationships (calls, imports, inheritance)
        """
        logger.info(
            "Building repository graph for %s (%d modules)",
            repo_id,
            len(parsed_modules),
        )

        # Collect all function and class entity IDs across the repo
        all_function_ids: dict[str, str] = {}
        all_class_ids: dict[str, str] = {}

        # Build individual file graphs
        for module in parsed_modules:
            if module.error:
                logger.warning(
                    "Skipping %s due to parse error: %s",
                    module.file_path,
                    module.error,
                )
                continue

            await self.build_file_graph(module)

            # Track entity IDs for cross-file resolution
            for func in module.functions:
                all_function_ids[func.name] = func.entity_id
                all_function_ids[func.qualified_name] = func.entity_id
            for cls in module.classes:
                all_class_ids[cls.name] = cls.entity_id
                all_class_ids[cls.qualified_name] = cls.entity_id
                for method in cls.methods:
                    all_function_ids[method.name] = method.entity_id
                    all_function_ids[method.qualified_name] = method.entity_id

        # Resolve cross-file CALLS relationships
        await self._resolve_cross_file_calls(
            parsed_modules, all_function_ids
        )

        # Resolve cross-file INHERITS relationships
        await self._resolve_cross_file_inherits(
            parsed_modules, all_class_ids
        )

        logger.info("Repository graph build complete for %s", repo_id)

    # ------------------------------------------------------------------ #
    #  Relationship resolution helpers
    # ------------------------------------------------------------------ #

    async def _resolve_calls(
        self,
        module: ParsedModule,
        function_ids: dict[str, str],
    ) -> None:
        """Resolve CALLS relationships within a single file."""
        all_funcs: list[ParsedFunction] = list(module.functions)
        for cls in module.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            for call in func.calls:
                target_id = function_ids.get(
                    call.qualified_name or ""
                ) or function_ids.get(call.name)
                if target_id and target_id != func.entity_id:
                    await self._ops.create_relationship(
                        from_id=func.entity_id,
                        to_id=target_id,
                        rel_type="CALLS",
                        properties={"line_number": call.line_number},
                    )

    async def _resolve_cross_file_calls(
        self,
        modules: list[ParsedModule],
        all_function_ids: dict[str, str],
    ) -> None:
        """Resolve CALLS relationships across files."""
        for module in modules:
            if module.error:
                continue

            all_funcs: list[ParsedFunction] = list(module.functions)
            for cls in module.classes:
                all_funcs.extend(cls.methods)

            for func in all_funcs:
                for call in func.calls:
                    target_id = all_function_ids.get(
                        call.qualified_name or ""
                    ) or all_function_ids.get(call.name)
                    if target_id and target_id != func.entity_id:
                        await self._ops.create_relationship(
                            from_id=func.entity_id,
                            to_id=target_id,
                            rel_type="CALLS",
                            properties={"line_number": call.line_number},
                        )

    async def _resolve_imports(self, module: ParsedModule) -> None:
        """Resolve IMPORTS relationships by matching import paths to known files."""
        file_id = f"{module.repo_id}:{module.file_path}"

        for imp in module.imports:
            # Convert module path to possible file paths
            if imp.is_from:
                # from foo.bar import baz -> try foo/bar.py, foo/bar/__init__.py
                rel_path = imp.module.replace(".", "/")
            else:
                # import foo.bar -> try foo/bar.py, foo/bar/__init__.py
                rel_path = imp.module.replace(".", "/")

            possible_paths = [
                f"{rel_path}.py",
                f"{rel_path}/__init__.py",
            ]

            for candidate_path in possible_paths:
                target_file_id = f"{module.repo_id}:{candidate_path}"
                # Try to create the relationship; it will only succeed if
                # the target node exists
                created = await self._ops.create_relationship(
                    from_id=file_id,
                    to_id=target_file_id,
                    rel_type="IMPORTS",
                    properties={
                        "module": imp.module,
                        "names": ",".join(imp.names) if imp.names else "",
                    },
                )
                if created:
                    break  # Found the target file, no need to try other paths

    async def _resolve_inherits(
        self,
        module: ParsedModule,
        class_ids: dict[str, str],
    ) -> None:
        """Resolve INHERITS relationships within a single file."""
        for cls in module.classes:
            for base_name in cls.bases:
                target_id = class_ids.get(base_name)
                if target_id and target_id != cls.entity_id:
                    await self._ops.create_relationship(
                        from_id=cls.entity_id,
                        to_id=target_id,
                        rel_type="INHERITS",
                    )

    async def _resolve_cross_file_inherits(
        self,
        modules: list[ParsedModule],
        all_class_ids: dict[str, str],
    ) -> None:
        """Resolve INHERITS relationships across files."""
        for module in modules:
            if module.error:
                continue
            for cls in module.classes:
                for base_name in cls.bases:
                    target_id = all_class_ids.get(base_name)
                    if target_id and target_id != cls.entity_id:
                        await self._ops.create_relationship(
                            from_id=cls.entity_id,
                            to_id=target_id,
                            rel_type="INHERITS",
                        )
