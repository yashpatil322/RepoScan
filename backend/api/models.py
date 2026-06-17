"""
models.py — Pydantic request/response schemas for all API endpoints.

Organized by module:
- Ingestion models (POST /ingest, GET /ingest/status)
- Query models (POST /query, POST /query/stream)
- Repo management models (GET /repos, DELETE /repos/:id, GET /repos/:id/chunks)
- Search models (POST /search, GET /search/similar/:chunk_id)
- Utility models (GET /health, GET /languages, GET /stats)
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from enum import Enum


# ══════════════════════════════════════════════════════════════════════
# Ingestion Models
# ══════════════════════════════════════════════════════════════════════

class IngestRequest(BaseModel):
    """Request body for POST /ingest"""
    repo_url: HttpUrl = Field(
        ...,
        description="Full GitHub repository URL (e.g., https://github.com/owner/repo)",
        examples=["https://github.com/tiangolo/fastapi"],
    )


class IngestionStatus(str, Enum):
    """Possible states of an ingestion task."""
    QUEUED = "queued"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestResponse(BaseModel):
    """Response for POST /ingest — returns immediately with task tracking info."""
    task_id: str = Field(..., description="Unique ID to poll ingestion status")
    repo_id: str = Field(..., description="Derived repo identifier (e.g., 'tiangolo-fastapi')")
    repo_url: str = Field(..., description="The submitted GitHub URL")
    status: IngestionStatus = Field(..., description="Current ingestion status")
    message: str = Field(..., description="Human-readable status message")


class IngestStatusResponse(BaseModel):
    """Response for GET /ingest/status — poll for ingestion progress."""
    task_id: str
    repo_id: str
    repo_url: str
    status: IngestionStatus
    message: str
    progress: dict = Field(
        default_factory=dict,
        description="Progress details: files_found, files_parsed, chunks_created, etc.",
    )
    result: Optional[dict] = Field(
        None,
        description="Final result when status is 'completed' — file count, chunk count, etc.",
    )
    error: Optional[str] = Field(None, description="Error message if status is 'failed'")
    started_at: str = Field(..., description="ISO timestamp of when ingestion started")
    completed_at: Optional[str] = Field(None, description="ISO timestamp of completion")


# ══════════════════════════════════════════════════════════════════════
# Query Models
# ══════════════════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    """Request body for POST /query and POST /query/stream"""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question about the codebase",
        examples=["Where is authentication handled?", "How does the payment flow work?"],
    )
    repo_id: Optional[str] = Field(
        None,
        description="Specific repo to query. If None, searches across all indexed repos.",
    )
    top_k: int = Field(
        5,
        ge=1,
        le=20,
        description="Number of code chunks to retrieve for context (1–20)",
    )


class SourceInfo(BaseModel):
    """A single cited source from the codebase."""
    file_path: str = Field(..., description="Relative file path in the repo")
    start_line: int = Field(..., description="Start line number (1-indexed)")
    end_line: int = Field(..., description="End line number (1-indexed)")
    name: str = Field(..., description="Function/class/module name")
    chunk_type: str = Field(..., description="Type: function, class, module, etc.")
    language: str = Field(..., description="Programming language")
    similarity_score: float = Field(..., description="Cosine similarity score (0–1)")


class QueryResponse(BaseModel):
    """Response for POST /query — full answer with cited sources."""
    answer: str = Field(..., description="LLM-generated answer with inline citations")
    sources: list[SourceInfo] = Field(..., description="Code chunks used as context")
    citations: list[str] = Field(
        default_factory=list,
        description="Extracted citation references from the answer text (e.g., 'auth/jwt.py:12-45')",
    )
    chunks_used: int = Field(..., description="Number of chunks passed to the LLM")
    model: str = Field(..., description="LLM model used for generation")
    repo_id: Optional[str] = Field(None, description="Repo that was queried")


# ══════════════════════════════════════════════════════════════════════
# Repo Management Models
# ══════════════════════════════════════════════════════════════════════

class RepoInfo(BaseModel):
    """Information about an indexed repository."""
    repo_id: str
    repo_url: str
    ingested_at: str = Field(..., description="ISO timestamp of when the repo was indexed")
    files_processed: int
    chunks_stored: int
    languages_found: list[str] = Field(default_factory=list)


class RepoListResponse(BaseModel):
    """Response for GET /repos"""
    repos: list[RepoInfo]
    total: int


class RepoDeleteResponse(BaseModel):
    """Response for DELETE /repos/:id"""
    repo_id: str
    status: str = "deleted"
    message: str
    chunks_removed: int


class ChunkDetail(BaseModel):
    """Detailed info about a single stored chunk."""
    chunk_id: str
    text: str = Field(..., description="Raw source code of the chunk")
    file_path: str
    language: str
    chunk_type: str
    start_line: int
    end_line: int
    name: str
    truncated: bool = False


class RepoChunksResponse(BaseModel):
    """Response for GET /repos/:id/chunks — paginated chunk browser."""
    repo_id: str
    chunks: list[ChunkDetail]
    total: int
    limit: int
    offset: int


# ══════════════════════════════════════════════════════════════════════
# Search Models
# ══════════════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    """Request body for POST /search — raw similarity search, no LLM."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query (code snippet, description, or question)",
    )
    repo_id: Optional[str] = Field(
        None,
        description="Specific repo to search. If None, searches all repos.",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=50,
        description="Number of results to return (1–50)",
    )
    filter_language: Optional[str] = Field(
        None,
        description="Filter results by language (e.g., 'python', 'javascript')",
    )
    filter_chunk_type: Optional[str] = Field(
        None,
        description="Filter by chunk type (e.g., 'function', 'class', 'module')",
    )


class SearchResult(BaseModel):
    """A single search result with similarity score."""
    chunk_id: str
    text: str
    file_path: str
    language: str
    chunk_type: str
    start_line: int
    end_line: int
    name: str
    similarity_score: float
    repo_id: Optional[str] = None


class SearchResponse(BaseModel):
    """Response for POST /search and GET /search/similar/:chunk_id"""
    results: list[SearchResult]
    total_results: int
    query: str


# ══════════════════════════════════════════════════════════════════════
# Utility Models
# ══════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Response for GET /health"""
    status: str = "ok"
    api: str = "running"
    chromadb: str = Field(..., description="'connected' or 'unreachable'")
    gemini: str = Field(..., description="'configured' or 'missing_api_key'")
    timestamp: str


class LanguageInfo(BaseModel):
    """Info about a supported language."""
    language: str
    extensions: list[str]
    chunk_types: list[str]


class LanguagesResponse(BaseModel):
    """Response for GET /languages"""
    languages: list[LanguageInfo]
    total: int


class StatsResponse(BaseModel):
    """Response for GET /stats"""
    total_repos: int
    total_chunks: int
    total_files_processed: int
    languages: list[str] = Field(
        default_factory=list,
        description="All languages found across all indexed repos",
    )
    repos: list[dict] = Field(
        default_factory=list,
        description="Per-repo summary stats",
    )
