"""FastAPI repository endpoints for RepoLens."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.embeddings.embedder import CodeEmbedder
from app.graph.ingester import GraphIngester
from app.graph.neo4j_client import Neo4jClient
from app.graph.schema import init_schema
from app.ingestion.pipeline import IngestionPipeline
from app.parser.models import ParsedRepository
from app.retrieval.hybrid_search import HybridSearchEngine, HybridSearchResult
from app.retrieval.semantic_search import SemanticSearchEngine
from app.services.chat_service import ChatResponse, ChatService
from app.services.impact_service import ImpactReport, ImpactService

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])

# Global in-memory cache for registered repositories and their parsed AST structures
REPO_STORE: dict[str, dict[str, Any]] = {}
PARSED_CACHE: dict[str, ParsedRepository] = {}


class RegisterRepoRequest(BaseModel):
    path: str = Field(description="Local directory path to Python repository")
    name: Optional[str] = Field(default=None, description="Human readable name")


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5


class ImpactRequest(BaseModel):
    function_name: str


@router.post("", status_code=201)
def register_repository(req: RegisterRepoRequest) -> dict[str, Any]:
    """Registers a local repository for indexing."""
    target_path = Path(req.path).resolve()
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Invalid repository directory: {req.path}")

    repo_name = req.name or target_path.name
    repo_id = f"repo:{repo_name}"

    record = {
        "id": repo_id,
        "name": repo_name,
        "root_path": str(target_path),
        "status": "registered",
        "total_files": 0,
        "total_functions": 0,
        "total_classes": 0,
        "total_lines": 0,
    }
    REPO_STORE[repo_id] = record
    return record


@router.get("")
def list_repositories() -> list[dict[str, Any]]:
    """Lists all registered repositories."""
    neo4j = Neo4jClient()
    if neo4j.ping():
        records = neo4j.execute_read(
            "MATCH (r:Repository) RETURN r.id AS id, r.name AS name, r.root_path AS root_path, "
            "r.total_files AS total_files, r.total_functions AS total_functions, "
            "r.total_classes AS total_classes, r.total_lines AS total_lines"
        )
        for r in records:
            if r["id"] not in REPO_STORE:
                REPO_STORE[r["id"]] = r
    return list(REPO_STORE.values())


@router.get("/{repo_id}")
def get_repository(repo_id: str) -> dict[str, Any]:
    """Gets details for a single repository."""
    if repo_id not in REPO_STORE:
        raise HTTPException(status_code=404, detail="Repository not found")
    return REPO_STORE[repo_id]


@router.delete("/{repo_id}")
def delete_repository(repo_id: str) -> dict[str, Any]:
    """Deletes repository from registry and Neo4j graph."""
    if repo_id not in REPO_STORE:
        raise HTTPException(status_code=404, detail="Repository not found")

    neo4j = Neo4jClient()
    if neo4j.ping():
        neo4j.execute_write(
            "MATCH (r:Repository {id: $id}) "
            "OPTIONAL MATCH (r)-[:CONTAINS]->(f:File) "
            "OPTIONAL MATCH (f)-[:DEFINES]->(entity) "
            "DETACH DELETE r, f, entity",
            {"id": repo_id},
        )

    del REPO_STORE[repo_id]
    PARSED_CACHE.pop(repo_id, None)
    return {"status": "deleted", "id": repo_id}


@router.post("/{repo_id}/ingest")
def ingest_repository(repo_id: str) -> dict[str, Any]:
    """
    Parses Python AST, builds Neo4j knowledge graph, and indexes embeddings.
    """
    if repo_id not in REPO_STORE:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_info = REPO_STORE[repo_id]
    pipeline = IngestionPipeline()
    parsed_repo = pipeline.parse_repository(repo_info["root_path"], repo_name=repo_info["name"])
    PARSED_CACHE[repo_id] = parsed_repo

    # Update in-memory metadata
    repo_info.update(
        {
            "status": "indexed",
            "total_files": parsed_repo.total_files,
            "total_functions": parsed_repo.total_functions,
            "total_classes": parsed_repo.total_classes,
            "total_lines": parsed_repo.total_lines,
        }
    )

    # Ingest to Neo4j if available
    neo4j = Neo4jClient()
    stats: dict[str, Any] = {"neo4j_online": False}
    if neo4j.ping():
        init_schema(neo4j)
        ingester = GraphIngester(neo4j)
        graph_stats = ingester.ingest_repository(parsed_repo, repo_id=repo_id)
        stats.update({"neo4j_online": True, **graph_stats})

        # Generate and store embeddings for all functions
        embedder = CodeEmbedder()
        all_funcs = [fn for f in parsed_repo.files for fn in f.get_all_functions()]
        if all_funcs:
            texts = [embedder.format_function(fn) for fn in all_funcs]
            vectors = embedder.embed_texts(texts)
            func_embeddings = [
                {
                    "id": f"func:{repo_id}:{fn.file_path}:{fn.class_name or 'global'}:{fn.name}",
                    "embedding": vec,
                }
                for fn, vec in zip(all_funcs, vectors, strict=False)
            ]
            search_engine = SemanticSearchEngine(client=neo4j, embedder=embedder)
            stored_count = search_engine.store_function_embeddings(func_embeddings)
            stats["embedded_functions"] = stored_count

    return {"status": "success", "repository": repo_info, "stats": stats}


@router.get("/{repo_id}/files")
def list_files(repo_id: str) -> list[str]:
    """Lists relative file paths of all indexed Python files."""
    if repo_id in PARSED_CACHE:
        return [f.file_path for f in PARSED_CACHE[repo_id].files]
    repo_info = REPO_STORE.get(repo_id)
    if not repo_info:
        raise HTTPException(status_code=404, detail="Repository not found")
    pipeline = IngestionPipeline()
    parsed = pipeline.parse_repository(repo_info["root_path"], repo_name=repo_info["name"])
    PARSED_CACHE[repo_id] = parsed
    return [f.file_path for f in parsed.files]


@router.get("/{repo_id}/files/{file_path:path}")
def get_file_details(repo_id: str, file_path: str) -> dict[str, Any]:
    """Retrieves file source code and extracted AST entities."""
    if repo_id not in PARSED_CACHE:
        list_files(repo_id)
    parsed_repo = PARSED_CACHE[repo_id]
    clean_path = file_path.replace("\\", "/")
    target_file = next((f for f in parsed_repo.files if f.file_path == clean_path), None)
    if not target_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Read actual source code from disk
    abs_path = Path(parsed_repo.root_path) / clean_path
    source_text = (
        abs_path.read_text(encoding="utf-8", errors="replace") if abs_path.is_file() else ""
    )

    return {
        "file_path": target_file.file_path,
        "total_lines": target_file.total_lines,
        "docstring": target_file.docstring,
        "source": source_text,
        "imports": [imp.model_dump() for imp in target_file.imports],
        "classes": [c.model_dump() for c in target_file.classes],
        "functions": [fn.model_dump() for fn in target_file.get_all_functions()],
    }


@router.get("/{repo_id}/symbols")
def list_symbols(repo_id: str, query: str = Query(default="")) -> list[dict[str, Any]]:
    """Lists functions and classes in the repository, with optional search filter."""
    if repo_id not in PARSED_CACHE:
        list_files(repo_id)
    parsed_repo = PARSED_CACHE[repo_id]
    symbols: list[dict[str, Any]] = []

    for f in parsed_repo.files:
        for c in f.classes:
            if not query or query.lower() in c.name.lower():
                symbols.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "kind": "class",
                        "file_path": f.file_path,
                        "start_line": c.start_line,
                        "end_line": c.end_line,
                    }
                )
        for fn in f.get_all_functions():
            if not query or query.lower() in fn.name.lower():
                symbols.append(
                    {
                        "id": fn.id,
                        "name": fn.name,
                        "kind": "function" if not fn.is_method else "method",
                        "file_path": f.file_path,
                        "start_line": fn.start_line,
                        "end_line": fn.end_line,
                        "class_name": fn.class_name,
                    }
                )
    return symbols


@router.get("/{repo_id}/graph")
def get_graph_data(
    repo_id: str,
    focus: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """
    Retrieves nodes and edges for the graph explorer view.
    Centers around `focus` symbol if specified, or top module entities.
    """
    if repo_id not in PARSED_CACHE:
        list_files(repo_id)
    parsed_repo = PARSED_CACHE[repo_id]

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    def add_node(nid: str, label: str, ntype: str, file_path: str = ""):
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "label": label, "type": ntype, "file_path": file_path})

    for f in parsed_repo.files:
        file_nid = f"file:{f.file_path}"
        if not focus or any(focus.lower() in fn.name.lower() for fn in f.get_all_functions()):
            add_node(file_nid, f.file_path.split("/")[-1], "file", f.file_path)

            for c in f.classes:
                c_nid = f"class:{c.name}"
                add_node(c_nid, c.name, "class", f.file_path)
                edges.append({"source": file_nid, "target": c_nid, "type": "DEFINES"})
                for base in c.bases:
                    base_nid = f"class:{base}"
                    add_node(base_nid, base, "class")
                    edges.append({"source": c_nid, "target": base_nid, "type": "INHERITS"})

            for fn in f.get_all_functions():
                fn_nid = f"func:{fn.name}"
                add_node(fn_nid, f"{fn.name}()", "function", f.file_path)
                if fn.class_name:
                    edges.append(
                        {"source": f"class:{fn.class_name}", "target": fn_nid, "type": "HAS_METHOD"}
                    )
                else:
                    edges.append({"source": file_nid, "target": fn_nid, "type": "DEFINES"})

                for callee in fn.calls:
                    callee_nid = f"func:{callee}"
                    add_node(callee_nid, f"{callee}()", "function")
                    edges.append({"source": fn_nid, "target": callee_nid, "type": "CALLS"})

    # Limit to reasonable neighborhood if too large
    return {"nodes": nodes[:80], "edges": edges[:120]}


@router.post("/{repo_id}/search")
def search_repository(repo_id: str, req: SearchRequest) -> list[HybridSearchResult]:
    """Runs hybrid code search across the repository."""
    neo4j = Neo4jClient()
    hybrid = HybridSearchEngine(client=neo4j if neo4j.ping() else None)
    return hybrid.search(query=req.query, limit=req.limit, repo_id=repo_id)


@router.post("/{repo_id}/chat")
def chat_repository(repo_id: str, req: ChatRequest) -> ChatResponse:
    """Answers a question about the repository using grounded RAG."""
    neo4j = Neo4jClient()
    service = ChatService(neo4j_client=neo4j if neo4j.ping() else None)
    return service.ask(query=req.query, repo_id=repo_id, top_k=req.top_k)


@router.post("/{repo_id}/impact")
def impact_analysis_repository(repo_id: str, req: ImpactRequest) -> ImpactReport:
    """Runs change impact blast-radius analysis on a function."""
    neo4j = Neo4jClient()
    service = ImpactService(neo4j_client=neo4j if neo4j.ping() else None)
    return service.analyze_impact(function_identifier=req.function_name, repo_id=repo_id)
