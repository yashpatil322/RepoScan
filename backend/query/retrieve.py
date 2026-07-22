from __future__ import annotations

"""
retrieve.py — Similarity search in ChromaDB.

Handles:
- Embedding user queries with the same model used for indexing
- Cosine similarity search in ChromaDB with optional metadata filters
- Finding similar chunks given a specific chunk ID
- Cross-repo search (search across all indexed repos at once)
"""

from ingest.embed import (
    get_chroma_client,
    get_embed_model,
    get_or_create_collection,
    get_all_repos,
    get_chunk_by_id,
    _collection_name,
)


def retrieve(
    question: str,
    repo_id: str | None = None,
    top_k: int = 5,
    filter_language: str | None = None,
    filter_chunk_type: str | None = None,
) -> list[dict]:
    """
    Embed a user question and find the most semantically similar code chunks.

    Args:
        question: Natural language question about the codebase.
        repo_id: Specific repo to search. If None, searches ALL indexed repos.
        top_k: Number of results to return.
        filter_language: Optional — only return chunks in this language.
        filter_chunk_type: Optional — only return chunks of this type (function/class/module).

    Returns:
        List of dicts, each containing:
        - text: raw source code of the chunk
        - metadata: file_path, language, chunk_type, start_line, end_line, name
        - similarity_score: cosine similarity (0–1, higher = more similar)
        - chunk_id: the chunk's unique ID in ChromaDB
        - repo_id: which repo this chunk belongs to
    """
    model = get_embed_model()
    question_embedding = model.encode(
        [question],
        normalize_embeddings=True,
    ).tolist()

    # Build ChromaDB where filter
    where_filter = _build_where_filter(filter_language, filter_chunk_type)

    # Determine which collections to search
    if repo_id:
        collections_to_search = [(repo_id, repo_id)]
    else:
        repos = get_all_repos()
        collections_to_search = [(r["repo_id"], r["repo_id"]) for r in repos]

    if not collections_to_search:
        return []

    # Search across all target collections and merge results
    all_results = []
    client = get_chroma_client()

    for search_repo_id, _ in collections_to_search:
        try:
            collection = client.get_collection(name=_collection_name(search_repo_id))
        except Exception:
            continue

        if collection.count() == 0:
            continue

        query_params = {
            "query_embeddings": question_embedding,
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }

        if where_filter:
            query_params["where"] = where_filter

        try:
            results = collection.query(**query_params)
        except Exception:
            continue

        if not results["documents"] or not results["documents"][0]:
            continue

        for i in range(len(results["documents"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0

            all_results.append({
                "text": results["documents"][0][i],
                "metadata": meta,
                "similarity_score": round(1 - distance, 4),  # cosine distance → similarity
                "chunk_id": results["ids"][0][i] if results["ids"] else "",
                "repo_id": search_repo_id,
            })

    # Sort by similarity (descending) and take top_k
    all_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return all_results[:top_k]


def find_similar_chunks(
    chunk_id: str,
    repo_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Given a specific chunk ID, find other chunks semantically similar to it.

    This is useful for "show me related code" features — e.g., finding all
    functions that are semantically related to a given function.

    Args:
        chunk_id: The ID of the reference chunk.
        repo_id: The repo containing the chunk.
        top_k: Number of similar chunks to return.

    Returns:
        List of similar chunks (same format as retrieve()), excluding the
        input chunk itself.
    """
    # Get the reference chunk's embedding
    chunk_data = get_chunk_by_id(repo_id, chunk_id)
    if not chunk_data or not chunk_data.get("embedding"):
        return []

    embedding = chunk_data["embedding"]
    client = get_chroma_client()

    try:
        collection = client.get_collection(name=_collection_name(repo_id))
    except Exception:
        return []

    # Query with the chunk's own embedding (top_k + 1 because the chunk itself will match)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k + 1, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    similar = []
    for i in range(len(results["documents"][0])):
        result_id = results["ids"][0][i] if results["ids"] else ""

        # Skip the input chunk itself
        if result_id == chunk_id:
            continue

        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 1.0

        similar.append({
            "text": results["documents"][0][i],
            "metadata": meta,
            "similarity_score": round(1 - distance, 4),
            "chunk_id": result_id,
            "repo_id": repo_id,
        })

    return similar[:top_k]


def raw_search(
    query: str,
    repo_id: str | None = None,
    top_k: int = 10,
    filter_language: str | None = None,
    filter_chunk_type: str | None = None,
) -> list[dict]:
    """
    Raw similarity search — same as retrieve() but designed for the
    /search endpoint. Returns results in a format suitable for browsing
    (no LLM call).

    This is a convenience wrapper around retrieve() with a higher default top_k.
    """
    return retrieve(
        question=query,
        repo_id=repo_id,
        top_k=top_k,
        filter_language=filter_language,
        filter_chunk_type=filter_chunk_type,
    )


def _build_where_filter(
    filter_language: str | None = None,
    filter_chunk_type: str | None = None,
) -> dict | None:
    """
    Build a ChromaDB 'where' filter from optional parameters.

    ChromaDB where syntax:
        {"language": "python"}                           # single filter
        {"$and": [{"language": "python"}, {"chunk_type": "function"}]}  # multiple
    """
    conditions = []

    if filter_language:
        conditions.append({"language": filter_language})

    if filter_chunk_type:
        conditions.append({"chunk_type": filter_chunk_type})

    if not conditions:
        return None
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return {"$and": conditions}
