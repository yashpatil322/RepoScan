import chromadb
from sentence_transformers import SentenceTransformer
from .parse import parse_file
from .clone import get_code_files, clone_repo
from .languages import SUPPORTED_EXTENSIONS
import hashlib
import os
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "chroma_db")
COLLECTION_NAME = "codebase"
EMBED_MODEL = "nomic-ai/nomic-embed-text-v1"   # good general model, free

def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}   # use cosine similarity
    )

def format_chunk_text(chunk: dict) -> str:
    """Prepend metadata to the chunk text before embedding."""
    return (
        f"file: {chunk['file_path']}\n"
        f"type: {chunk['chunk_type']} | name: {chunk['name']} (lines {chunk['start_line']}-{chunk['end_line']})\n"
        f"language: {chunk['language']}\n\n"
        f"{chunk['text']}"
    )

def ingest_repo(repo_url: str) -> dict:
    """
    Full ingestion pipeline:
    1. Clone the repo
    2. Parse all code files into chunks
    3. Embed each chunk
    4. Store in ChromaDB
    Returns summary stats.
    """
    repo_path = clone_repo(repo_url)
    code_files = get_code_files(repo_path, SUPPORTED_EXTENSIONS)

    all_chunks = []
    for file_path in code_files:
        chunks = parse_file(file_path)
        # Make file paths relative to repo root for cleaner display
        for chunk in chunks:
            chunk["file_path"] = os.path.relpath(chunk["file_path"], repo_path).replace("\\", "/")
        all_chunks.extend(chunks)

    if not all_chunks:
        shutil.rmtree(repo_path, ignore_errors=True)
        return {"status": "error", "message": "No supported code files found."}

    print(f"Loading embedding model: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)

    # Prepend metadata header to each chunk's text to embed and store
    texts = [format_chunk_text(c) for c in all_chunks]
    
    print(f"Embedding {len(texts)} chunks ...")
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True).tolist()

    collection = get_collection()

    # Generate stable IDs from file_path + start_line to allow re-ingestion
    ids = [
        hashlib.md5(f"{c['file_path']}:{c['start_line']}".encode()).hexdigest()
        for c in all_chunks
    ]

    metadatas = [
        {
            "file_path": c["file_path"],
            "language": c["language"],
            "chunk_type": c["chunk_type"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "name": c["name"],
        }
        for c in all_chunks
    ]

    # Upsert in batches of 500 (ChromaDB limit per call)
    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        collection.upsert(
            ids=ids[i:i+batch_size],
            documents=texts[i:i+batch_size],
            embeddings=embeddings[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
        )

    # Clean up cloned repo temp folder
    shutil.rmtree(repo_path, ignore_errors=True)

    return {
        "status": "success",
        "repo_url": repo_url,
        "files_processed": len(code_files),
        "chunks_stored": len(all_chunks),
    }
