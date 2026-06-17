"""
main.py — FastAPI application with 12 endpoints across 5 modules.

Module 1 — Ingestion (2 endpoints)
    POST /ingest           — Clone & index a GitHub repo (background task)
    GET  /ingest/status    — Poll ingestion progress

Module 2 — Query (2 endpoints)
    POST /query            — Ask a question, get a cited answer from Gemini
    POST /query/stream     — Same but streams response via Server-Sent Events

Module 3 — Repo Management (3 endpoints)
    GET    /repos          — List all indexed repos
    DELETE /repos/{id}     — Delete a repo and its chunks
    GET    /repos/{id}/chunks — Browse raw chunks for a repo

Module 4 — Search (2 endpoints)
    POST /search                  — Raw similarity search (no LLM)
    GET  /search/similar/{chunk_id} — Find chunks similar to a given chunk

Module 5 — Utility (3 endpoints)
    GET /health     — API + ChromaDB + Gemini status
    GET /languages  — Supported file extensions & languages
    GET /stats      — System-wide statistics

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

# Load environment variables before importing modules that use them
load_dotenv()

from api.models import (
    # Ingestion
    IngestRequest, IngestResponse, IngestStatusResponse, IngestionStatus,
    # Query
    QueryRequest, QueryResponse, SourceInfo,
    # Repo management
    RepoInfo, RepoListResponse, RepoDeleteResponse,
    RepoChunksResponse, ChunkDetail,
    # Search
    SearchRequest, SearchResponse, SearchResult,
    # Utility
    HealthResponse, LanguagesResponse, LanguageInfo, StatsResponse,
)

from ingest.embed import (
    ingest_repo,
    get_all_repos,
    get_repo_info,
    delete_collection,
    get_repo_chunks,
    get_system_stats,
    get_chroma_client,
)

from query.retrieve import retrieve, find_similar_chunks, raw_search
from query.answer import generate_answer, generate_answer_stream, extract_citations, GEMINI_API_KEY
from ingest.languages import get_language_info, SUPPORTED_EXTENSIONS
from ingest.clone import generate_repo_id


# ══════════════════════════════════════════════════════════════════════
# FastAPI App Configuration
# ══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="RepoScan — Codebase Q&A Bot API",
    description=(
        "A RAG-powered API that lets you ask natural language questions about "
        "any GitHub repository and get cited, source-linked answers. "
        "Built with Tree-sitter, ChromaDB, and Google Gemini."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins for development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════
# In-Memory Ingestion Task Tracker
# ══════════════════════════════════════════════════════════════════════

# Maps task_id → task status dict
# In production, use Redis or a database. For this project, in-memory is fine.
ingestion_tasks: dict[str, dict] = {}


def _create_task(task_id: str, repo_id: str, repo_url: str) -> dict:
    """Create a new ingestion task entry."""
    task = {
        "task_id": task_id,
        "repo_id": repo_id,
        "repo_url": repo_url,
        "status": IngestionStatus.QUEUED,
        "message": "Ingestion queued...",
        "progress": {},
        "result": None,
        "error": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    ingestion_tasks[task_id] = task
    return task


def _run_ingestion(task_id: str, repo_url: str):
    """
    Run the full ingestion pipeline synchronously.
    Called as a background task by FastAPI.
    Updates the task tracker as it progresses.
    """
    task = ingestion_tasks.get(task_id)
    if not task:
        return

    def progress_callback(status: str, message: str, extra: dict = None):
        """Callback invoked by ingest_repo() at each stage."""
        task["status"] = status
        task["message"] = message
        if extra:
            task["progress"].update(extra)

    try:
        result = ingest_repo(repo_url, progress_callback=progress_callback)
        task["status"] = IngestionStatus.COMPLETED
        task["message"] = (
            f"Successfully indexed {result['chunks_stored']} chunks "
            f"from {result['files_processed']} files."
        )
        task["result"] = result
        task["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        task["status"] = IngestionStatus.FAILED
        task["message"] = f"Ingestion failed: {str(e)}"
        task["error"] = str(e)
        task["completed_at"] = datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════
# MODULE 1 — INGESTION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post(
    "/ingest",
    response_model=IngestResponse,
    tags=["Ingestion"],
    summary="Clone & index a GitHub repository",
    description=(
        "Takes a GitHub URL, clones the repo, parses all source files with "
        "Tree-sitter, generates embeddings, and stores everything in ChromaDB. "
        "Returns immediately with a task_id — poll GET /ingest/status for progress."
    ),
)
async def ingest_endpoint(request: IngestRequest, background_tasks: BackgroundTasks):
    repo_url = str(request.repo_url)
    repo_id = generate_repo_id(repo_url)
    task_id = str(uuid.uuid4())

    # Check if already being ingested
    for existing_task in ingestion_tasks.values():
        if (
            existing_task["repo_id"] == repo_id
            and existing_task["status"] in (
                IngestionStatus.QUEUED, IngestionStatus.CLONING,
                IngestionStatus.PARSING, IngestionStatus.EMBEDDING,
            )
        ):
            return IngestResponse(
                task_id=existing_task["task_id"],
                repo_id=repo_id,
                repo_url=repo_url,
                status=existing_task["status"],
                message=f"Ingestion already in progress for this repo (task: {existing_task['task_id']})",
            )

    # Create task and launch in background
    _create_task(task_id, repo_id, repo_url)
    background_tasks.add_task(_run_ingestion, task_id, repo_url)

    return IngestResponse(
        task_id=task_id,
        repo_id=repo_id,
        repo_url=repo_url,
        status=IngestionStatus.QUEUED,
        message="Ingestion started. Poll GET /ingest/status?task_id=... for progress.",
    )


@app.get(
    "/ingest/status",
    response_model=IngestStatusResponse,
    tags=["Ingestion"],
    summary="Poll ingestion progress",
    description=(
        "Returns the current status of an ingestion task. "
        "Poll this endpoint until status is 'completed' or 'failed'."
    ),
)
async def ingest_status_endpoint(
    task_id: str = Query(..., description="Task ID returned by POST /ingest"),
):
    task = ingestion_tasks.get(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"No ingestion task found with ID '{task_id}'",
        )

    return IngestStatusResponse(
        task_id=task["task_id"],
        repo_id=task["repo_id"],
        repo_url=task["repo_url"],
        status=task["status"],
        message=task["message"],
        progress=task["progress"],
        result=task["result"],
        error=task["error"],
        started_at=task["started_at"],
        completed_at=task["completed_at"],
    )


# ══════════════════════════════════════════════════════════════════════
# MODULE 2 — QUERY ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post(
    "/query",
    response_model=QueryResponse,
    tags=["Query"],
    summary="Ask a question about the indexed codebase",
    description=(
        "Takes a natural language question, retrieves the top-k most relevant "
        "code chunks via similarity search, passes them to Google Gemini, and "
        "returns a cited answer with source references."
    ),
)
async def query_endpoint(request: QueryRequest):
    # Retrieve relevant chunks
    chunks = retrieve(
        question=request.question,
        repo_id=request.repo_id,
        top_k=request.top_k,
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail=(
                "No relevant code chunks found. "
                "Make sure you've ingested a repository first (POST /ingest)."
            ),
        )

    # Generate answer using Gemini
    try:
        result = generate_answer(request.question, chunks)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating answer: {str(e)}",
        )

    # Build response with typed source info
    sources = [
        SourceInfo(
            file_path=s["file_path"],
            start_line=s["start_line"],
            end_line=s["end_line"],
            name=s["name"],
            chunk_type=s["chunk_type"],
            language=s["language"],
            similarity_score=s["similarity_score"],
        )
        for s in result["sources"]
    ]

    return QueryResponse(
        answer=result["answer"],
        sources=sources,
        citations=result["citations"],
        chunks_used=result["chunks_used"],
        model=result["model"],
        repo_id=request.repo_id,
    )


@app.post(
    "/query/stream",
    tags=["Query"],
    summary="Stream a question answer via Server-Sent Events",
    description=(
        "Same as POST /query but streams the response token-by-token "
        "using Server-Sent Events (SSE). Great for real-time UI rendering."
    ),
)
async def query_stream_endpoint(request: QueryRequest):
    # Retrieve relevant chunks
    chunks = retrieve(
        question=request.question,
        repo_id=request.repo_id,
        top_k=request.top_k,
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant code chunks found. Ingest a repository first.",
        )

    # Build source info for the final event
    sources = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        sources.append({
            "file_path": meta.get("file_path", ""),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "name": meta.get("name", ""),
            "chunk_type": meta.get("chunk_type", ""),
            "language": meta.get("language", ""),
            "similarity_score": chunk.get("similarity_score", 0),
        })

    async def event_generator():
        """
        Yield SSE events:
        - {"event": "token", "data": {"token": "..."}}  — for each text fragment
        - {"event": "done",  "data": {"sources": [...], "citations": [...]}}  — final event
        - {"event": "error", "data": {"error": "..."}}  — on failure
        """
        full_answer = ""

        try:
            for text_chunk in generate_answer_stream(request.question, chunks):
                full_answer += text_chunk
                yield {
                    "event": "token",
                    "data": json.dumps({"token": text_chunk}),
                }
                await asyncio.sleep(0)  # Yield control to event loop

            # Final event with metadata
            citations = extract_citations(full_answer)
            yield {
                "event": "done",
                "data": json.dumps({
                    "sources": sources,
                    "citations": citations,
                    "chunks_used": len(chunks),
                    "model": "gemini-2.0-flash",
                }),
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


# ══════════════════════════════════════════════════════════════════════
# MODULE 3 — REPO MANAGEMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.get(
    "/repos",
    response_model=RepoListResponse,
    tags=["Repos"],
    summary="List all indexed repositories",
    description="Returns metadata for every repository that has been indexed.",
)
async def list_repos_endpoint():
    repos_data = get_all_repos()

    repos = [
        RepoInfo(
            repo_id=r["repo_id"],
            repo_url=r["repo_url"],
            ingested_at=r.get("ingested_at", ""),
            files_processed=r.get("files_processed", 0),
            chunks_stored=r.get("chunks_stored", 0),
            languages_found=r.get("languages_found", []),
        )
        for r in repos_data
    ]

    return RepoListResponse(repos=repos, total=len(repos))


@app.delete(
    "/repos/{repo_id}",
    response_model=RepoDeleteResponse,
    tags=["Repos"],
    summary="Delete a repository and all its chunks",
    description=(
        "Removes all indexed data for a specific repository from ChromaDB "
        "and the repo registry. This action is irreversible."
    ),
)
async def delete_repo_endpoint(repo_id: str):
    # Check if repo exists
    repo_info = get_repo_info(repo_id)
    if not repo_info:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_id}' not found. Use GET /repos to see indexed repos.",
        )

    chunks_removed = delete_collection(repo_id)

    return RepoDeleteResponse(
        repo_id=repo_id,
        status="deleted",
        message=f"Successfully deleted repository '{repo_id}' and all its data.",
        chunks_removed=chunks_removed,
    )


@app.get(
    "/repos/{repo_id}/chunks",
    response_model=RepoChunksResponse,
    tags=["Repos"],
    summary="Browse chunks for a repository",
    description=(
        "Returns paginated raw chunks stored for a specific repo. "
        "Useful for debugging, inspecting what the bot 'knows', and building UIs."
    ),
)
async def get_repo_chunks_endpoint(
    repo_id: str,
    limit: int = Query(20, ge=1, le=100, description="Max chunks to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    # Check if repo exists
    repo_info = get_repo_info(repo_id)
    if not repo_info:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_id}' not found.",
        )

    data = get_repo_chunks(repo_id, limit=limit, offset=offset)

    chunks = [
        ChunkDetail(
            chunk_id=c["chunk_id"],
            text=c["text"],
            file_path=c["file_path"],
            language=c["language"],
            chunk_type=c["chunk_type"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            name=c["name"],
            truncated=c.get("truncated", False),
        )
        for c in data["chunks"]
    ]

    return RepoChunksResponse(
        repo_id=repo_id,
        chunks=chunks,
        total=data["total"],
        limit=data["limit"],
        offset=data["offset"],
    )


# ══════════════════════════════════════════════════════════════════════
# MODULE 4 — SEARCH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post(
    "/search",
    response_model=SearchResponse,
    tags=["Search"],
    summary="Raw similarity search (no LLM call)",
    description=(
        "Performs a pure cosine similarity search on indexed code chunks. "
        "Returns matching chunks ranked by relevance — no LLM generation. "
        "Useful for showing 'relevant files' before the full answer loads."
    ),
)
async def search_endpoint(request: SearchRequest):
    results = raw_search(
        query=request.query,
        repo_id=request.repo_id,
        top_k=request.top_k,
        filter_language=request.filter_language,
        filter_chunk_type=request.filter_chunk_type,
    )

    search_results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            text=r["text"],
            file_path=r["metadata"].get("file_path", ""),
            language=r["metadata"].get("language", ""),
            chunk_type=r["metadata"].get("chunk_type", ""),
            start_line=r["metadata"].get("start_line", 0),
            end_line=r["metadata"].get("end_line", 0),
            name=r["metadata"].get("name", ""),
            similarity_score=r["similarity_score"],
            repo_id=r.get("repo_id"),
        )
        for r in results
    ]

    return SearchResponse(
        results=search_results,
        total_results=len(search_results),
        query=request.query,
    )


@app.get(
    "/search/similar/{chunk_id}",
    response_model=SearchResponse,
    tags=["Search"],
    summary="Find chunks similar to a given chunk",
    description=(
        "Given a specific chunk ID, finds other code chunks that are "
        "semantically similar to it. Good for 'show me related code' features."
    ),
)
async def similar_chunks_endpoint(
    chunk_id: str,
    repo_id: str = Query(..., description="Repository ID containing the chunk"),
    top_k: int = Query(5, ge=1, le=20, description="Number of similar chunks"),
):
    # Check if repo exists
    repo_info = get_repo_info(repo_id)
    if not repo_info:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{repo_id}' not found.",
        )

    results = find_similar_chunks(
        chunk_id=chunk_id,
        repo_id=repo_id,
        top_k=top_k,
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Chunk '{chunk_id}' not found or has no similar chunks.",
        )

    search_results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            text=r["text"],
            file_path=r["metadata"].get("file_path", ""),
            language=r["metadata"].get("language", ""),
            chunk_type=r["metadata"].get("chunk_type", ""),
            start_line=r["metadata"].get("start_line", 0),
            end_line=r["metadata"].get("end_line", 0),
            name=r["metadata"].get("name", ""),
            similarity_score=r["similarity_score"],
            repo_id=repo_id,
        )
        for r in results
    ]

    return SearchResponse(
        results=search_results,
        total_results=len(search_results),
        query=f"similar to chunk {chunk_id}",
    )


# ══════════════════════════════════════════════════════════════════════
# MODULE 5 — UTILITY ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Utility"],
    summary="Health check",
    description="Returns API status, ChromaDB connection, and Gemini API key presence.",
)
async def health_endpoint():
    # Check ChromaDB
    try:
        client = get_chroma_client()
        client.heartbeat()
        chromadb_status = "connected"
    except Exception:
        chromadb_status = "unreachable"

    # Check Gemini API key
    gemini_status = "configured" if GEMINI_API_KEY else "missing_api_key"

    return HealthResponse(
        status="ok",
        api="running",
        chromadb=chromadb_status,
        gemini=gemini_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/languages",
    response_model=LanguagesResponse,
    tags=["Utility"],
    summary="List supported programming languages",
    description=(
        "Returns all programming languages supported by the parser, "
        "including their file extensions and extractable chunk types."
    ),
)
async def languages_endpoint():
    lang_info = get_language_info()

    languages = [
        LanguageInfo(
            language=li["language"],
            extensions=li["extensions"],
            chunk_types=li["chunk_types"],
        )
        for li in lang_info
    ]

    return LanguagesResponse(languages=languages, total=len(languages))


@app.get(
    "/stats",
    response_model=StatsResponse,
    tags=["Utility"],
    summary="System-wide statistics",
    description="Returns total repos indexed, total chunks, and per-repo summaries.",
)
async def stats_endpoint():
    stats = get_system_stats()

    return StatsResponse(
        total_repos=stats["total_repos"],
        total_chunks=stats["total_chunks"],
        total_files_processed=stats["total_files_processed"],
        languages=stats["languages"],
        repos=stats["repos"],
    )


# ══════════════════════════════════════════════════════════════════════
# Startup Event
# ══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Pre-warm expensive resources on app startup."""
    import logging
    logger = logging.getLogger("uvicorn")

    logger.info("🚀 RepoScan API starting up...")

    # Pre-initialize ChromaDB client
    try:
        get_chroma_client()
        logger.info("✅ ChromaDB connected")
    except Exception as e:
        logger.warning(f"⚠️  ChromaDB connection failed: {e}")

    # Check Gemini API key
    if GEMINI_API_KEY:
        logger.info("✅ Gemini API key configured")
    else:
        logger.warning("⚠️  GEMINI_API_KEY not set — /query endpoints will fail")

    # Log supported languages
    langs = [li["language"] for li in get_language_info()]
    logger.info(f"✅ Supported languages: {', '.join(langs) if langs else 'none (install tree-sitter-* packages)'}")

    logger.info("🟢 RepoScan API ready at http://localhost:8000/docs")
