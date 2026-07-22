from __future__ import annotations

"""
embed.py — Embedding pipeline and ChromaDB storage.

This module is the bridge between parsing and retrieval. It:
1. Takes parsed code chunks from parse.py
2. Embeds them using a sentence-transformer model
3. Stores embeddings + metadata in ChromaDB (one collection per repo)
4. Maintains a JSON-based repo registry for tracking indexed repos

The repo registry allows us to:
- List all indexed repos without scanning ChromaDB collections
- Store metadata (URL, ingestion time, stats) per repo
- Support multi-repo querying
"""

import os
import json
import hashlib
from datetime import datetime, timezone

import chromadb
# sentence_transformers is imported lazily inside get_embed_model() to ensure fast API startup

from .clone import clone_repo, get_code_files, cleanup_repo, generate_repo_id
from .parse import parse_repo
from .languages import SUPPORTED_EXTENSIONS


# ──────────────────────────────────────────────────────────────────────
# Configuration (overridable via environment variables)
# ──────────────────────────────────────────────────────────────────────

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", "./data/chroma_db")
REPOS_REGISTRY_PATH = os.environ.get("REPOS_REGISTRY_PATH", "./data/repos_registry.json")
EMBED_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBED_BATCH_SIZE = 16
CHROMA_UPSERT_BATCH = 500  # ChromaDB's max per call


# ──────────────────────────────────────────────────────────────────────
# Singletons — avoid reloading the model and client on every call
# ──────────────────────────────────────────────────────────────────────

_chroma_client: chromadb.PersistentClient | None = None
_embed_model = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Get or create the persistent ChromaDB client (singleton)."""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _chroma_client


def get_embed_model():
    """Get or create the sentence-transformer embedding model (singleton)."""
    global _embed_model
    if _embed_model is None:
        try:
            import torch
            torch.set_num_threads(1)
        except Exception:
            pass
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME, trust_remote_code=True)
    return _embed_model


# ──────────────────────────────────────────────────────────────────────
# ChromaDB Collection Management
# ──────────────────────────────────────────────────────────────────────

def _collection_name(repo_id: str) -> str:
    """Convert a repo_id to a valid ChromaDB collection name."""
    # ChromaDB rules: 3–63 chars, alphanumeric + underscores, starts with letter
    name = f"repo_{repo_id}".replace("-", "_")
    # Ensure length constraints
    if len(name) > 63:
        name = name[:63]
    return name


def get_or_create_collection(repo_id: str):
    """Get or create a ChromaDB collection for a specific repo."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=_collection_name(repo_id),
        metadata={"hnsw:space": "cosine"},
    )


def delete_collection(repo_id: str) -> int:
    """
    Delete a repo's ChromaDB collection and remove from registry.
    Returns the number of chunks that were removed.
    """
    client = get_chroma_client()
    col_name = _collection_name(repo_id)

    try:
        collection = client.get_collection(name=col_name)
        chunk_count = collection.count()
    except Exception:
        chunk_count = 0

    try:
        client.delete_collection(name=col_name)
    except Exception:
        pass

    # Remove from registry
    _remove_from_registry(repo_id)

    return chunk_count


# ──────────────────────────────────────────────────────────────────────
# Repo Registry (JSON file)
# ──────────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    """Load the repos registry from disk."""
    if os.path.exists(REPOS_REGISTRY_PATH):
        try:
            with open(REPOS_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_registry(registry: dict) -> None:
    """Save the repos registry to disk."""
    os.makedirs(os.path.dirname(REPOS_REGISTRY_PATH), exist_ok=True)
    with open(REPOS_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, default=str)


def _add_to_registry(repo_id: str, repo_url: str, stats: dict) -> None:
    """Add or update a repo entry in the registry."""
    registry = _load_registry()
    registry[repo_id] = {
        "repo_id": repo_id,
        "repo_url": str(repo_url),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "files_processed": stats.get("files_processed", 0),
        "chunks_stored": stats.get("chunks_stored", 0),
        "languages_found": stats.get("languages_found", []),
    }
    _save_registry(registry)


def _remove_from_registry(repo_id: str) -> None:
    """Remove a repo entry from the registry."""
    registry = _load_registry()
    registry.pop(repo_id, None)
    _save_registry(registry)


def get_all_repos() -> list[dict]:
    """Get all indexed repos from the registry."""
    registry = _load_registry()
    return list(registry.values())


def get_repo_info(repo_id: str) -> dict | None:
    """Get info for a specific repo, or None if not found."""
    registry = _load_registry()
    return registry.get(repo_id)


# ──────────────────────────────────────────────────────────────────────
# Chunk ID Generation
# ──────────────────────────────────────────────────────────────────────

def _generate_chunk_id(repo_id: str, file_path: str, start_line: int, name: str) -> str:
    """
    Generate a stable, unique chunk ID.
    Uses MD5 of repo_id + file_path + start_line + name for determinism,
    so re-ingesting the same repo produces the same IDs (enables upsert).
    """
    content = f"{repo_id}:{file_path}:{start_line}:{name}"
    return hashlib.md5(content.encode()).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# Chunk Browsing
# ──────────────────────────────────────────────────────────────────────

def get_repo_chunks(repo_id: str, limit: int = 20, offset: int = 0) -> dict:
    """
    Browse stored chunks for a repo with pagination.

    Returns:
        Dict with 'chunks', 'total', 'limit', 'offset'.
    """
    try:
        client = get_chroma_client()
        collection = client.get_collection(name=_collection_name(repo_id))
    except Exception:
        return {"chunks": [], "total": 0, "limit": limit, "offset": offset}

    total = collection.count()

    if total == 0:
        return {"chunks": [], "total": 0, "limit": limit, "offset": offset}

    # ChromaDB doesn't support offset/limit natively on get(),
    # so we get all IDs and slice manually
    all_data = collection.get(
        include=["documents", "metadatas"],
        limit=limit,
        offset=offset,
    )

    chunks = []
    if all_data["ids"]:
        for i, chunk_id in enumerate(all_data["ids"]):
            meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
            chunks.append({
                "chunk_id": chunk_id,
                "text": all_data["documents"][i] if all_data["documents"] else "",
                "file_path": meta.get("file_path", ""),
                "language": meta.get("language", ""),
                "chunk_type": meta.get("chunk_type", ""),
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "name": meta.get("name", ""),
                "truncated": meta.get("truncated", False),
            })

    return {
        "chunks": chunks,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_chunk_by_id(repo_id: str, chunk_id: str) -> dict | None:
    """Retrieve a single chunk by its ID from a specific repo's collection."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(name=_collection_name(repo_id))
        result = collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas", "embeddings"],
        )
        if not result["ids"]:
            return None

        meta = result["metadatas"][0] if result["metadatas"] else {}
        return {
            "chunk_id": result["ids"][0],
            "text": result["documents"][0] if result["documents"] else "",
            "embedding": result["embeddings"][0] if result["embeddings"] else None,
            "metadata": meta,
        }
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# Main Ingestion Pipeline
# ──────────────────────────────────────────────────────────────────────

def ingest_repo(repo_url: str, progress_callback=None) -> dict:
    """
    Full ingestion pipeline: clone → parse → embed → store in ChromaDB.

    Args:
        repo_url: GitHub repository URL.
        progress_callback: Optional callable(status, message, progress_dict)
                          for real-time status updates to the API layer.

    Returns:
        Dict with:
        - status: "success" or "error"
        - repo_id: generated repo identifier
        - repo_url: the input URL
        - files_processed: number of source files parsed
        - chunks_stored: total chunks stored in ChromaDB
        - languages_found: list of detected languages

    Raises:
        RuntimeError: If cloning fails.
        ValueError: If no supported code files are found.
    """
    repo_url_str = str(repo_url)
    repo_id = generate_repo_id(repo_url_str)
    repo_path = None

    def _update(status, message, extra=None):
        if progress_callback:
            progress_callback(status, message, extra or {})

    try:
        # ── Step 1: Clone ──────────────────────────────────────────
        _update("cloning", f"Cloning {repo_url_str}...")
        clone_dir = os.environ.get("CLONE_DIR")
        repo_path = clone_repo(repo_url_str, clone_dir)

        # ── Step 2: Discover files ─────────────────────────────────
        _update("parsing", "Discovering source code files...")
        code_files = get_code_files(repo_path, SUPPORTED_EXTENSIONS)

        if not code_files:
            raise ValueError(
                f"No supported source code files found in {repo_url_str}. "
                f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        _update("parsing", f"Found {len(code_files)} source files. Parsing with Tree-sitter...",
                {"files_found": len(code_files)})

        # ── Step 3: Parse with Tree-sitter ─────────────────────────
        all_chunks = parse_repo(repo_path, code_files)

        if not all_chunks:
            raise ValueError("Tree-sitter parsed 0 chunks. The repo may contain unsupported languages only.")

        # Collect unique languages
        languages_found = sorted(set(c["language"] for c in all_chunks))

        _update("embedding", f"Parsed {len(all_chunks)} chunks. Generating embeddings...",
                {"files_found": len(code_files), "chunks_created": len(all_chunks)})

        # ── Step 4: Embed ──────────────────────────────────────────
        model = get_embed_model()
        texts_to_embed = [chunk["enriched_text"] for chunk in all_chunks]

        embeddings = model.encode(
            texts_to_embed,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

        # ── Step 5: Store in ChromaDB ──────────────────────────────
        _update("embedding", f"Storing {len(all_chunks)} chunks in ChromaDB...")

        collection = get_or_create_collection(repo_id)

        # Generate stable IDs
        ids = [
            _generate_chunk_id(repo_id, c["file_path"], c["start_line"], c["name"])
            for c in all_chunks
        ]

        # Prepare metadata (only serializable fields)
        metadatas = [
            {
                "file_path": c["file_path"],
                "language": c["language"],
                "chunk_type": c["chunk_type"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "name": c["name"],
                "truncated": c["truncated"],
                "repo_id": repo_id,
            }
            for c in all_chunks
        ]

        # Store raw text as documents (not enriched — retrieval returns raw code)
        documents = [c["text"] for c in all_chunks]

        # Batch upsert
        for i in range(0, len(all_chunks), CHROMA_UPSERT_BATCH):
            end = min(i + CHROMA_UPSERT_BATCH, len(all_chunks))
            collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
            )

        # ── Step 6: Update registry ────────────────────────────────
        stats = {
            "files_processed": len(code_files),
            "chunks_stored": len(all_chunks),
            "languages_found": languages_found,
        }
        _add_to_registry(repo_id, repo_url_str, stats)

        result = {
            "status": "success",
            "repo_id": repo_id,
            "repo_url": repo_url_str,
            **stats,
        }

        _update("completed", "Ingestion complete!", stats)
        return result

    finally:
        # Always clean up the cloned repo
        if repo_path:
            cleanup_repo(repo_path)


# ──────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────

def get_system_stats() -> dict:
    """
    Get system-wide statistics across all indexed repos.

    Returns dict with total_repos, total_chunks, total_files_processed,
    languages, and per-repo summaries.
    """
    repos = get_all_repos()

    total_chunks = 0
    total_files = 0
    all_languages = set()
    repo_summaries = []

    for repo in repos:
        total_chunks += repo.get("chunks_stored", 0)
        total_files += repo.get("files_processed", 0)
        all_languages.update(repo.get("languages_found", []))
        repo_summaries.append({
            "repo_id": repo["repo_id"],
            "chunks": repo.get("chunks_stored", 0),
            "files": repo.get("files_processed", 0),
        })

    return {
        "total_repos": len(repos),
        "total_chunks": total_chunks,
        "total_files_processed": total_files,
        "languages": sorted(all_languages),
        "repos": repo_summaries,
    }
