# RepoScan Backend — Complete API Reference

## Setup Instructions

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Gemini API key
# Edit backend/.env and replace 'your_gemini_api_key_here' with your actual key
# Get a FREE key at: https://aistudio.google.com/apikey

# 5. Run the server
uvicorn api.main:app --reload --port 8000

# 6. Open Swagger docs
# http://localhost:8000/docs
```

---

## Project Structure

```
backend/
├── api/
│   ├── __init__.py
│   ├── main.py             ← FastAPI app (12 endpoints, 5 modules)
│   └── models.py           ← All Pydantic request/response schemas
├── ingest/
│   ├── __init__.py
│   ├── clone.py            ← Git cloning + file discovery
│   ├── languages.py        ← Tree-sitter language map (9 languages)
│   ├── parse.py            ← AST-aware code chunker
│   └── embed.py            ← Embedding + ChromaDB storage + repo registry
├── query/
│   ├── __init__.py
│   ├── retrieve.py         ← Similarity search + chunk lookup
│   └── answer.py           ← Gemini prompt builder + streaming
├── .env                    ← Your GEMINI_API_KEY goes here
├── .env.example            ← Template
├── .gitignore
└── requirements.txt
```

---

## All 12 Endpoints

### Module 1 — Ingestion

---

#### `POST /ingest` — Clone & index a GitHub repo

Starts the ingestion in the background and returns immediately.

**Request:**
```json
POST http://localhost:8000/ingest
Content-Type: application/json

{
    "repo_url": "https://github.com/tiangolo/fastapi"
}
```

**Response (202 — Accepted):**
```json
{
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "repo_id": "tiangolo-fastapi",
    "repo_url": "https://github.com/tiangolo/fastapi",
    "status": "queued",
    "message": "Ingestion started. Poll GET /ingest/status?task_id=... for progress."
}
```

---

#### `GET /ingest/status` — Poll ingestion progress

**Request:**
```
GET http://localhost:8000/ingest/status?task_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (while in progress):**
```json
{
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "repo_id": "tiangolo-fastapi",
    "repo_url": "https://github.com/tiangolo/fastapi",
    "status": "embedding",
    "message": "Parsed 450 chunks. Generating embeddings...",
    "progress": {
        "files_found": 120,
        "chunks_created": 450
    },
    "result": null,
    "error": null,
    "started_at": "2026-06-17T10:30:00Z",
    "completed_at": null
}
```

**Response (when completed):**
```json
{
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "repo_id": "tiangolo-fastapi",
    "repo_url": "https://github.com/tiangolo/fastapi",
    "status": "completed",
    "message": "Successfully indexed 450 chunks from 120 files.",
    "progress": {
        "files_found": 120,
        "chunks_created": 450
    },
    "result": {
        "status": "success",
        "repo_id": "tiangolo-fastapi",
        "repo_url": "https://github.com/tiangolo/fastapi",
        "files_processed": 120,
        "chunks_stored": 450,
        "languages_found": ["python"]
    },
    "error": null,
    "started_at": "2026-06-17T10:30:00Z",
    "completed_at": "2026-06-17T10:32:15Z"
}
```

**Ingestion Status Flow:**
```
queued → cloning → parsing → embedding → completed
                                       → failed (if error)
```

---

### Module 2 — Query

---

#### `POST /query` — Ask a question (full response)

**Request:**
```json
POST http://localhost:8000/query
Content-Type: application/json

{
    "question": "How does FastAPI handle dependency injection?",
    "repo_id": "tiangolo-fastapi",
    "top_k": 5
}
```

> **Fields:**
> - `question` (required, 3–1000 chars) — Your natural language question
> - `repo_id` (optional) — Specific repo to query. Omit to search all repos
> - `top_k` (optional, 1–20, default 5) — Number of context chunks to retrieve

**Response:**
```json
{
    "answer": "FastAPI handles dependency injection through the `Depends` function defined in [fastapi/dependencies/utils.py:187-234]. When you declare a parameter with `Depends(get_db)`, FastAPI's dependency resolution system...\n\nThe core resolver is the `solve_dependencies` function [fastapi/dependencies/utils.py:45-120] which recursively resolves the dependency graph...",
    "sources": [
        {
            "file_path": "fastapi/dependencies/utils.py",
            "start_line": 187,
            "end_line": 234,
            "name": "get_dependant",
            "chunk_type": "function",
            "language": "python",
            "similarity_score": 0.8923
        },
        {
            "file_path": "fastapi/dependencies/utils.py",
            "start_line": 45,
            "end_line": 120,
            "name": "solve_dependencies",
            "chunk_type": "function",
            "language": "python",
            "similarity_score": 0.8541
        }
    ],
    "citations": [
        "fastapi/dependencies/utils.py:187-234",
        "fastapi/dependencies/utils.py:45-120"
    ],
    "chunks_used": 5,
    "model": "gemini-2.0-flash",
    "repo_id": "tiangolo-fastapi"
}
```

---

#### `POST /query/stream` — Stream answer via SSE

Same request body as `/query`. Returns Server-Sent Events.

**Request:**
```json
POST http://localhost:8000/query/stream
Content-Type: application/json

{
    "question": "Where is authentication handled?",
    "repo_id": "tiangolo-fastapi",
    "top_k": 5
}
```

**SSE Response Stream:**
```
event: token
data: {"token": "FastAPI handles "}

event: token
data: {"token": "authentication through "}

event: token
data: {"token": "the `Security` class defined in "}

event: token
data: {"token": "[fastapi/security/base.py:12-45]..."}

event: done
data: {"sources": [...], "citations": ["fastapi/security/base.py:12-45"], "chunks_used": 5, "model": "gemini-2.0-flash"}
```

> **In Postman:** Set the response type to "Event Stream" to see SSE events.

---

### Module 3 — Repo Management

---

#### `GET /repos` — List all indexed repos

**Request:**
```
GET http://localhost:8000/repos
```

**Response:**
```json
{
    "repos": [
        {
            "repo_id": "tiangolo-fastapi",
            "repo_url": "https://github.com/tiangolo/fastapi",
            "ingested_at": "2026-06-17T10:32:15Z",
            "files_processed": 120,
            "chunks_stored": 450,
            "languages_found": ["python"]
        },
        {
            "repo_id": "expressjs-express",
            "repo_url": "https://github.com/expressjs/express",
            "ingested_at": "2026-06-17T11:00:00Z",
            "files_processed": 45,
            "chunks_stored": 180,
            "languages_found": ["javascript"]
        }
    ],
    "total": 2
}
```

---

#### `DELETE /repos/{repo_id}` — Delete a repo

**Request:**
```
DELETE http://localhost:8000/repos/tiangolo-fastapi
```

**Response:**
```json
{
    "repo_id": "tiangolo-fastapi",
    "status": "deleted",
    "message": "Successfully deleted repository 'tiangolo-fastapi' and all its data.",
    "chunks_removed": 450
}
```

---

#### `GET /repos/{repo_id}/chunks` — Browse chunks

**Request:**
```
GET http://localhost:8000/repos/tiangolo-fastapi/chunks?limit=3&offset=0
```

**Response:**
```json
{
    "repo_id": "tiangolo-fastapi",
    "chunks": [
        {
            "chunk_id": "a3f2b1c4d5e6f7890123456789abcdef",
            "text": "def get_dependant(\n    *, path: str, ...\n) -> Dependant:\n    ...",
            "file_path": "fastapi/dependencies/utils.py",
            "language": "python",
            "chunk_type": "function",
            "start_line": 187,
            "end_line": 234,
            "name": "get_dependant",
            "truncated": false
        }
    ],
    "total": 450,
    "limit": 3,
    "offset": 0
}
```

---

### Module 4 — Search

---

#### `POST /search` — Raw similarity search (no LLM)

**Request:**
```json
POST http://localhost:8000/search
Content-Type: application/json

{
    "query": "database connection pooling",
    "repo_id": "tiangolo-fastapi",
    "top_k": 10,
    "filter_language": "python",
    "filter_chunk_type": "function"
}
```

> **Fields:**
> - `query` (required) — Search query text
> - `repo_id` (optional) — Specific repo to search
> - `top_k` (optional, 1–50, default 10) — Number of results
> - `filter_language` (optional) — e.g., `"python"`, `"javascript"`
> - `filter_chunk_type` (optional) — e.g., `"function"`, `"class"`, `"module"`

**Response:**
```json
{
    "results": [
        {
            "chunk_id": "abc123def456",
            "text": "def get_db_pool():\n    ...",
            "file_path": "src/database/pool.py",
            "language": "python",
            "chunk_type": "function",
            "start_line": 15,
            "end_line": 40,
            "name": "get_db_pool",
            "similarity_score": 0.8734,
            "repo_id": "tiangolo-fastapi"
        }
    ],
    "total_results": 10,
    "query": "database connection pooling"
}
```

---

#### `GET /search/similar/{chunk_id}` — Find related code

**Request:**
```
GET http://localhost:8000/search/similar/abc123def456?repo_id=tiangolo-fastapi&top_k=5
```

**Response:**
```json
{
    "results": [
        {
            "chunk_id": "xyz789ghi012",
            "text": "def close_db_pool():\n    ...",
            "file_path": "src/database/pool.py",
            "language": "python",
            "chunk_type": "function",
            "start_line": 42,
            "end_line": 55,
            "name": "close_db_pool",
            "similarity_score": 0.9123,
            "repo_id": "tiangolo-fastapi"
        }
    ],
    "total_results": 5,
    "query": "similar to chunk abc123def456"
}
```

---

### Module 5 — Utility

---

#### `GET /health` — Health check

**Request:**
```
GET http://localhost:8000/health
```

**Response:**
```json
{
    "status": "ok",
    "api": "running",
    "chromadb": "connected",
    "gemini": "configured",
    "timestamp": "2026-06-17T10:30:00Z"
}
```

---

#### `GET /languages` — Supported languages

**Request:**
```
GET http://localhost:8000/languages
```

**Response:**
```json
{
    "languages": [
        {
            "language": "python",
            "extensions": [".py", ".pyw"],
            "chunk_types": ["function_definition", "class_definition"]
        },
        {
            "language": "javascript",
            "extensions": [".js", ".jsx", ".mjs"],
            "chunk_types": ["function_declaration", "class_declaration", "arrow_function", "method_definition", "export_statement"]
        },
        {
            "language": "typescript",
            "extensions": [".ts"],
            "chunk_types": ["function_declaration", "class_declaration", "arrow_function", "method_definition", "interface_declaration", "type_alias_declaration", "export_statement"]
        }
    ],
    "total": 9
}
```

---

#### `GET /stats` — System statistics

**Request:**
```
GET http://localhost:8000/stats
```

**Response:**
```json
{
    "total_repos": 2,
    "total_chunks": 630,
    "total_files_processed": 165,
    "languages": ["javascript", "python"],
    "repos": [
        {"repo_id": "tiangolo-fastapi", "chunks": 450, "files": 120},
        {"repo_id": "expressjs-express", "chunks": 180, "files": 45}
    ]
}
```

---

## Postman Testing Workflow

Follow this order to test the full backend:

| Step | Endpoint | What to Check |
|------|----------|---------------|
| 1 | `GET /health` | API running, ChromaDB connected, Gemini configured |
| 2 | `GET /languages` | Shows which Tree-sitter languages are loaded |
| 3 | `POST /ingest` | Returns task_id, status is "queued" |
| 4 | `GET /ingest/status` | Poll until status is "completed" |
| 5 | `GET /repos` | Your repo appears in the list |
| 6 | `GET /repos/{id}/chunks` | Browse what was indexed |
| 7 | `POST /search` | Raw search works without LLM |
| 8 | `POST /query` | Full Q&A with Gemini, check citations |
| 9 | `POST /query/stream` | SSE streaming works |
| 10 | `GET /search/similar/{chunk_id}` | Related code discovery |
| 11 | `GET /stats` | Dashboard stats are correct |
| 12 | `DELETE /repos/{id}` | Cleanup works |

> **Tip:** Use a small repo for initial testing (e.g., your own or a repo with < 50 files). Large repos take longer to clone and embed.

---

## Swagger / Interactive Docs

Once the server is running, visit:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)  
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

Both are auto-generated from the Pydantic models and FastAPI decorators. You can test every endpoint directly in the browser.
