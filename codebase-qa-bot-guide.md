# Codebase Q&A Bot — Complete Project Guide

> A RAG-powered developer tool that lets you ask natural language questions about any GitHub repository and get cited, source-linked answers. Built with Tree-sitter, ChromaDB, FastAPI, and the Claude API.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [What You Will Learn](#2-what-you-will-learn)
3. [Tech Stack — Deep Dive](#3-tech-stack--deep-dive)
4. [System Architecture](#4-system-architecture)
5. [Project Structure](#5-project-structure)
6. [Phase-by-Phase Build Plan](#6-phase-by-phase-build-plan)
7. [Core Code — Every File Explained](#7-core-code--every-file-explained)
8. [How RAG Works in This Project](#8-how-rag-works-in-this-project)
9. [Chunking Strategy — The Hard Part](#9-chunking-strategy--the-hard-part)
10. [Prompt Engineering](#10-prompt-engineering)
11. [Demo Script for Recruiters](#11-demo-script-for-recruiters)
12. [GitHub README Template](#12-github-readme-template)
13. [LinkedIn Post Template](#13-linkedin-post-template)
14. [Common Errors and Fixes](#14-common-errors-and-fixes)
15. [How to Extend the Project](#15-how-to-extend-the-project)

---

## 1. Project Overview

### What it does

You give the bot a GitHub repository URL. It clones the repo, parses every source file using Tree-sitter (an AST-aware parser), chunks the code at function/class boundaries, embeds each chunk, and stores everything in a local ChromaDB vector database.

When you ask a question like *"Where is authentication handled?"* or *"How does the payment flow work?"*, the bot:

1. Embeds your question using the same embedding model
2. Finds the top-k most semantically similar code chunks
3. Passes those chunks as context to Claude
4. Returns a cited answer with file paths and line numbers

### Why this project stands out

Most RAG tutorials use PDFs of books. This project uses **live code** — a much harder and more impressive problem because:

- Code has structure (functions, classes, imports) that plain text splitters destroy
- Context matters differently — a function definition 500 lines away might be critical
- Metadata (file path, language, line numbers) must be preserved and surfaced
- The retrieval needs to understand developer intent, not just keyword matching

This is the kind of project a Staff Engineer at a product company would recognize as non-trivial.

---

## 2. What You Will Learn

### Concepts

| Concept | Where you learn it |
|---|---|
| Retrieval-Augmented Generation (RAG) | The entire project |
| Abstract Syntax Trees (AST) | `parse.py` — Tree-sitter chunker |
| Vector embeddings | `embed.py` — how text becomes numbers |
| Cosine similarity search | ChromaDB internals |
| Prompt engineering | `answer.py` — how to talk to LLMs |
| REST API design | FastAPI backend |
| Async programming | FastAPI + Python async/await |
| Git programmatic access | `clone.py` — gitpython |

### Technologies (hands-on)

- **Tree-sitter** — industry-standard code parser used by GitHub, Neovim, Zed
- **ChromaDB** — the leading open-source vector database
- **Sentence Transformers / OpenAI Embeddings** — how semantic search works
- **FastAPI** — the most popular modern Python API framework
- **Claude API (Anthropic)** — production LLM integration
- **Streamlit** — rapid UI prototyping
- **Docker** — containerizing your app
- **Pytest** — writing real tests

### Soft skills and habits

- Reading library documentation (Tree-sitter's Python bindings are sparse — you'll learn to read source)
- Debugging embedding pipelines (silent failures are common)
- Thinking about chunking as a design decision, not an afterthought
- Writing a README that actually explains the architecture

---

## 3. Tech Stack — Deep Dive

### Tree-sitter

Tree-sitter is a parser generator and incremental parsing library. It produces a **concrete syntax tree** (CST) of your code — meaning it understands that `def foo():` is a function definition, not just a line of text.

**Why not just split by lines or tokens?**

Naive splitting breaks functions in half. If a function is 80 lines and you split every 50 lines, the embedding of chunk 1 and chunk 2 are meaningless fragments. Tree-sitter lets you split at *logical boundaries* — always at function or class edges.

**Languages supported:** Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, and 40+ more.

```
pip install tree-sitter tree-sitter-python tree-sitter-javascript
```

### ChromaDB

ChromaDB is a vector database that runs **locally** (no API key, no cloud account needed). It stores:

- The raw text of each chunk
- The embedding vector (768 or 1536 floats)
- Metadata: file path, language, start line, end line, chunk type (function/class/module)

It supports cosine similarity search out of the box. For this project, local persistent storage is perfect — no infrastructure needed.

```
pip install chromadb
```

### Embedding Models

An embedding model converts text into a dense vector of floats. Semantically similar texts produce vectors that are close in high-dimensional space.

Two good options:

| Model | Dimensions | Speed | Cost | Notes |
|---|---|---|---|---|
| `nomic-ai/nomic-embed-code` | 768 | Fast | Free (local) | Code-specific, best for this |
| `text-embedding-3-small` | 1536 | Fast | ~$0.02/1M tokens | OpenAI API, needs key |
| `all-MiniLM-L6-v2` | 384 | Very fast | Free (local) | General purpose, weaker on code |

**Recommendation:** Start with `nomic-embed-code` via `sentence-transformers`. No API key, runs on CPU, and it understands code semantics.

```
pip install sentence-transformers
```

### FastAPI

FastAPI is a modern Python web framework built on Pydantic and Starlette. It auto-generates OpenAPI (Swagger) docs, supports async natively, and is used at Uber, Netflix, and Microsoft.

You'll use it to expose two endpoints:
- `POST /ingest` — clone a repo and build the index
- `POST /query` — ask a question, get an answer

### Claude API

The Anthropic Python SDK gives you access to `claude-sonnet-4-6`. You'll use it in the final step of the query pipeline — passing retrieved code chunks as context and asking Claude to synthesize an answer.

```
pip install anthropic
```

### Streamlit (UI)

Streamlit lets you build a web UI with pure Python — no HTML/CSS/JS. For a demo, this is perfect. You can always replace it with a React frontend later.

---

## 4. System Architecture

### Ingestion pipeline (run once per repo)

```
GitHub URL
    │
    ▼
gitpython: clone to /tmp/repo
    │
    ▼
os.walk(): find all .py / .js / .ts / .go files
    │
    ▼
Tree-sitter: parse each file into AST
    │
    ▼
Chunker: extract functions, classes, module-level code
    │
    ▼
Metadata builder: attach file_path, language, start_line, end_line, chunk_type
    │
    ▼
Embedding model: convert each chunk text → vector (768 floats)
    │
    ▼
ChromaDB: store (text, vector, metadata) for each chunk
```

### Query pipeline (per user question)

```
User question: "where is auth handled?"
    │
    ▼
Embedding model: question → vector
    │
    ▼
ChromaDB: cosine similarity → top 5 chunks
    │
    ▼
Prompt builder: format chunks + question into Claude prompt
    │
    ▼
Claude API (claude-sonnet-4-6): generate answer with citations
    │
    ▼
Response: answer text + list of cited files + line ranges
```

---

## 5. Project Structure

```
codebase-qa/
│
├── ingest/
│   ├── __init__.py
│   ├── clone.py          # Clone GitHub repo using gitpython
│   ├── parse.py          # Tree-sitter AST chunker (the hard part)
│   ├── embed.py          # Embed chunks and store in ChromaDB
│   └── languages.py      # Language detection and Tree-sitter grammar map
│
├── query/
│   ├── __init__.py
│   ├── retrieve.py       # Cosine similarity search in ChromaDB
│   └── answer.py         # Claude API prompt builder + response parser
│
├── api/
│   ├── __init__.py
│   ├── main.py           # FastAPI app — /ingest and /query endpoints
│   └── models.py         # Pydantic request/response schemas
│
├── app/
│   └── streamlit_app.py  # Streamlit UI
│
├── tests/
│   ├── test_parse.py     # Test chunker on sample files
│   ├── test_retrieve.py  # Test similarity search
│   └── fixtures/
│       └── sample.py     # Sample Python file for tests
│
├── .env.example          # ANTHROPIC_API_KEY placeholder
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 6. Phase-by-Phase Build Plan

### Phase 1 — Ingestion core (Week 1)

**Goal:** Clone a repo and extract code chunks with metadata.

Steps:
1. Set up the project structure and virtual environment
2. Write `clone.py` — clone a GitHub repo to a temp directory
3. Write `languages.py` — map file extensions to Tree-sitter grammars
4. Write `parse.py` — the AST chunker (see Section 9 for full explanation)
5. Test on a small repo (e.g. your own RAKTDAAN or MyDiary project)
6. Print all extracted chunks with their metadata

**Checkpoint:** Running `python -m ingest.parse /path/to/repo` prints all functions/classes found.

### Phase 2 — Embedding and storage (Week 1)

**Goal:** Store chunks in ChromaDB and verify retrieval works.

Steps:
1. Write `embed.py` — load the embedding model, embed each chunk, upsert to ChromaDB
2. Write `retrieve.py` — query ChromaDB with a question, return top-k chunks
3. Test: embed a small repo, then query with a question, print retrieved chunks

**Checkpoint:** A question like "how do users log in?" returns chunks from auth-related files.

### Phase 3 — Answer generation (Week 2)

**Goal:** Get Claude to synthesize a cited answer from retrieved chunks.

Steps:
1. Write `answer.py` — format retrieved chunks into a prompt, call Claude API, parse response
2. Test the full pipeline end-to-end in a Python script
3. Tune the prompt until citations are accurate and answers are concise

**Checkpoint:** Full pipeline works from a Python `main()` function.

### Phase 4 — API layer (Week 2)

**Goal:** Expose the pipeline as a REST API.

Steps:
1. Write FastAPI `main.py` with `/ingest` and `/query` endpoints
2. Add Pydantic models for request/response validation
3. Add error handling (invalid URL, unsupported language, empty repo)
4. Test with `curl` or Postman

**Checkpoint:** `POST /ingest {"repo_url": "https://github.com/..."}` works and returns chunk count.

### Phase 5 — UI and polish (Week 3)

**Goal:** Make it demoable.

Steps:
1. Write Streamlit UI with a URL input, question box, and cited response display
2. Add a Dockerfile and docker-compose
3. Add GitHub Actions CI (run pytest on push)
4. Write the README with a demo GIF
5. Deploy the Streamlit app to Streamlit Cloud (free)

**Checkpoint:** Live URL you can share with recruiters.

---

## 7. Core Code — Every File Explained

### `ingest/clone.py`

```python
import os
import tempfile
import shutil
from git import Repo

def clone_repo(github_url: str) -> str:
    """
    Clone a GitHub repository to a temporary directory.
    Returns the path to the cloned repo.
    """
    tmp_dir = tempfile.mkdtemp(prefix="codebase_qa_")
    try:
        print(f"Cloning {github_url} ...")
        Repo.clone_from(github_url, tmp_dir, depth=1)  # depth=1 = shallow clone, faster
        return tmp_dir
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repo: {e}")


def get_code_files(repo_path: str, extensions: list[str]) -> list[str]:
    """
    Walk the repo directory and return paths of all files
    matching the given extensions.
    """
    code_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-code dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') 
                   and d not in ('node_modules', '__pycache__', '.git', 'dist', 'build')]
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                code_files.append(os.path.join(root, file))
    return code_files
```

### `ingest/languages.py`

```python
from tree_sitter import Language
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript

# Map file extension → (language name, tree-sitter language object)
LANGUAGE_MAP = {
    ".py":  ("python",     Language(tspython.language())),
    ".js":  ("javascript", Language(tsjavascript.language())),
    # Add more as needed: .ts, .go, .rs, .java
}

# Node types to extract as chunks (varies by language)
CHUNK_NODE_TYPES = {
    "python": ["function_definition", "class_definition"],
    "javascript": ["function_declaration", "class_declaration",
                   "arrow_function", "method_definition"],
}

SUPPORTED_EXTENSIONS = list(LANGUAGE_MAP.keys())
```

### `ingest/parse.py`

```python
from tree_sitter import Parser
from .languages import LANGUAGE_MAP, CHUNK_NODE_TYPES
import os

def parse_file(file_path: str) -> list[dict]:
    """
    Parse a single source file using Tree-sitter.
    Returns a list of chunk dicts, each with:
      - text: the raw source code of the chunk
      - file_path: relative path in the repo
      - language: e.g. "python"
      - chunk_type: "function" | "class" | "module"
      - start_line: 1-indexed
      - end_line: 1-indexed
      - name: function/class name if available
    """
    ext = os.path.splitext(file_path)[1]
    if ext not in LANGUAGE_MAP:
        return []

    lang_name, ts_language = LANGUAGE_MAP[ext]
    node_types = CHUNK_NODE_TYPES.get(lang_name, [])

    parser = Parser(ts_language)

    with open(file_path, "rb") as f:
        source_bytes = f.read()

    tree = parser.parse(source_bytes)
    chunks = []

    def extract_node_name(node, source_bytes):
        """Extract the identifier/name from a function or class node."""
        for child in node.children:
            if child.type == "identifier":
                return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        return "unknown"

    def walk(node):
        if node.type in node_types:
            chunk_text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            chunk_type = "function" if "function" in node.type else "class"
            name = extract_node_name(node, source_bytes)

            chunks.append({
                "text": chunk_text,
                "file_path": file_path,
                "language": lang_name,
                "chunk_type": chunk_type,
                "start_line": node.start_point[0] + 1,  # Tree-sitter is 0-indexed
                "end_line": node.end_point[0] + 1,
                "name": name,
            })
            # Don't recurse into children — we want top-level functions/classes
            # (nested functions will be part of the parent chunk's text)
            return

        for child in node.children:
            walk(child)

    walk(tree.root_node)

    # If no named chunks found (e.g. a config file or script), treat whole file as one chunk
    if not chunks:
        full_text = source_bytes.decode("utf-8", errors="replace")
        if full_text.strip():
            chunks.append({
                "text": full_text[:3000],  # cap at 3000 chars for module-level code
                "file_path": file_path,
                "language": lang_name,
                "chunk_type": "module",
                "start_line": 1,
                "end_line": source_bytes.count(b"\n") + 1,
                "name": os.path.basename(file_path),
            })

    return chunks
```

### `ingest/embed.py`

```python
import chromadb
from sentence_transformers import SentenceTransformer
from .parse import parse_file
from .clone import get_code_files, clone_repo
from .languages import SUPPORTED_EXTENSIONS
import hashlib
import os

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "codebase"
EMBED_MODEL = "nomic-ai/nomic-embed-text-v1"   # good general model, free

def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}   # use cosine similarity
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
            chunk["file_path"] = os.path.relpath(chunk["file_path"], repo_path)
        all_chunks.extend(chunks)

    if not all_chunks:
        return {"status": "error", "message": "No supported code files found."}

    model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)

    texts = [chunk["text"] for chunk in all_chunks]
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

    return {
        "status": "success",
        "repo_url": repo_url,
        "files_processed": len(code_files),
        "chunks_stored": len(all_chunks),
    }
```

### `query/retrieve.py`

```python
from sentence_transformers import SentenceTransformer
from ingest.embed import get_collection, EMBED_MODEL

def retrieve(question: str, top_k: int = 5) -> list[dict]:
    """
    Embed the user question and find the most similar code chunks.
    Returns a list of dicts with text + metadata.
    """
    model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)
    question_embedding = model.encode([question]).tolist()

    collection = get_collection()
    results = collection.query(
        query_embeddings=question_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity_score": 1 - results["distances"][0][i],  # cosine distance → similarity
        })

    return chunks
```

### `query/answer.py`

```python
import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def build_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        context_parts.append(
            f"--- Chunk {i} ---\n"
            f"File: {meta['file_path']} (lines {meta['start_line']}–{meta['end_line']})\n"
            f"Type: {meta['chunk_type']} | Name: {meta['name']}\n\n"
            f"{chunk['text']}"
        )

    context = "\n\n".join(context_parts)

    return f"""You are an expert code assistant helping a developer understand a codebase.

You have been given the following relevant code chunks retrieved from the repository:

{context}

---

Based ONLY on the code chunks above, answer this question:
{question}

Rules:
- Cite every file you reference using the format [filename:line_start-line_end]
- If the answer is not in the provided chunks, say "I could not find this in the retrieved code."
- Be concise. Developers prefer short, precise answers with code references over long explanations.
- If relevant, quote the specific function or class name from the chunks.
"""

def answer(question: str, chunks: list[dict]) -> dict:
    """
    Send retrieved chunks + question to Claude and return the answer.
    """
    prompt = build_prompt(question, chunks)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    answer_text = message.content[0].text

    # Extract cited files from the chunks for the response
    cited_files = list({
        f"{c['metadata']['file_path']} (lines {c['metadata']['start_line']}–{c['metadata']['end_line']})"
        for c in chunks
    })

    return {
        "answer": answer_text,
        "sources": cited_files,
        "chunks_used": len(chunks),
    }
```

### `api/main.py`

```python
from fastapi import FastAPI, HTTPException
from api.models import IngestRequest, IngestResponse, QueryRequest, QueryResponse
from ingest.embed import ingest_repo
from query.retrieve import retrieve
from query.answer import answer

app = FastAPI(
    title="Codebase Q&A Bot",
    description="Ask natural language questions about any GitHub repository.",
    version="1.0.0"
)

@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Clone and index a GitHub repository."""
    try:
        result = ingest_repo(request.repo_url)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Ask a question about the indexed codebase."""
    chunks = retrieve(request.question, top_k=request.top_k)
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found. Ingest a repo first.")
    result = answer(request.question, chunks)
    return result

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### `api/models.py`

```python
from pydantic import BaseModel, HttpUrl

class IngestRequest(BaseModel):
    repo_url: HttpUrl

class IngestResponse(BaseModel):
    status: str
    repo_url: str
    files_processed: int
    chunks_stored: int

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    chunks_used: int
```

### `app/streamlit_app.py`

```python
import streamlit as st
import requests

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Codebase Q&A Bot", page_icon="🤖", layout="wide")
st.title("🤖 Codebase Q&A Bot")
st.caption("Ask questions about any GitHub repository in plain English.")

with st.sidebar:
    st.header("Index a Repository")
    repo_url = st.text_input("GitHub URL", placeholder="https://github.com/tiangolo/fastapi")
    if st.button("Ingest Repo", type="primary"):
        with st.spinner("Cloning and indexing..."):
            resp = requests.post(f"{API_BASE}/ingest", json={"repo_url": repo_url})
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"Indexed {data['chunks_stored']} chunks from {data['files_processed']} files.")
            else:
                st.error(resp.json().get("detail", "Unknown error"))

st.header("Ask a Question")
question = st.text_input("Your question", placeholder="Where is authentication handled?")

if st.button("Ask", type="primary") and question:
    with st.spinner("Thinking..."):
        resp = requests.post(f"{API_BASE}/query", json={"question": question})
        if resp.status_code == 200:
            data = resp.json()
            st.markdown("### Answer")
            st.markdown(data["answer"])
            st.markdown("### Sources")
            for src in data["sources"]:
                st.code(src)
        else:
            st.error(resp.json().get("detail", "Unknown error"))
```

---

## 8. How RAG Works in This Project

RAG stands for **Retrieval-Augmented Generation**. It solves a core problem with LLMs: they cannot know the contents of your private codebase.

The naive solution — dump the entire repo into the prompt — fails for large codebases (too many tokens, too expensive, too slow).

RAG solves this in three steps:

**Step 1 — Offline indexing**
Convert every document (in our case, every code chunk) into an embedding vector and store it. This is done once per repo.

**Step 2 — Online retrieval**
When a question arrives, embed it and find the chunks whose vectors are closest to the question vector. "Closeness" in vector space = semantic similarity.

**Step 3 — Generation**
Pass only the relevant retrieved chunks (not the whole codebase) to the LLM as context. The LLM generates an answer grounded in those chunks.

The key insight: **embeddings capture meaning, not keywords**. A question about "user login" will retrieve chunks containing `authenticate()`, `verify_token()`, and `OAuth callback` — even if none contain the word "login".

---

## 9. Chunking Strategy — The Hard Part

Chunking is the most important design decision in any RAG system. Bad chunking = bad retrieval = bad answers.

### Why naive chunking fails for code

```python
# If you split this at line 50:
def process_payment(user_id: int, amount: float):       # line 45
    user = get_user(user_id)                            # line 46
    if not user.subscription_active:                    # line 47
        raise SubscriptionExpiredError()                # line 48
    # ... 40 more lines ...
    return charge_stripe(user.stripe_id, amount)        # line 85 → cut off!
```

A 50-line splitter cuts the function in half. Chunk 1 starts a payment flow, chunk 2 ends it. Neither is semantically complete.

### AST-aware chunking (what we use)

Tree-sitter parses the file into a concrete syntax tree. We walk the tree and extract **complete function and class nodes** — regardless of line count.

```
Module
├── import statements (kept as module-level chunk)
├── ClassDefinition: PaymentProcessor
│   ├── MethodDefinition: __init__
│   ├── MethodDefinition: process_payment   ← extracted as chunk
│   └── MethodDefinition: refund            ← extracted as chunk
└── FunctionDefinition: get_stripe_client   ← extracted as chunk
```

Each chunk is a complete, meaningful unit of code.

### Handling large functions

If a function is extremely long (>150 lines), you can split it further — but stay at logical sub-block boundaries (if blocks, for loops). For v1, cap at 150 lines and add a note in the metadata: `"truncated": true`.

### Metadata is part of the chunk

Always prepend metadata to the chunk text before embedding:

```
file: src/payments/processor.py
function: process_payment (lines 45–93)
language: python

def process_payment(user_id: int, amount: float):
    ...
```

This helps the embedding model understand context and makes retrieved chunks immediately readable.

---

## 10. Prompt Engineering

The quality of Claude's answer depends almost entirely on your prompt. Here is what works for code Q&A:

### System-level instructions

```
You are an expert code assistant. You only answer based on the provided code chunks.
You always cite file paths and line numbers in the format [file:start-end].
If the answer is not in the chunks, you say so honestly.
```

### Context formatting

Format each chunk clearly so Claude can parse it:

```
--- Chunk 1 (score: 0.91) ---
File: src/auth/jwt.py (lines 12–45)
Type: function | Name: verify_token

def verify_token(token: str) -> dict:
    ...
```

### Anti-hallucination constraint

Always include: *"Answer ONLY using the code chunks provided above. Do not use any outside knowledge."*

This prevents Claude from generating plausible-sounding but wrong answers about libraries or patterns it has seen during training.

### Citation enforcement

Ask Claude to cite every file reference. In your response parser, extract citations with a regex:

```python
import re

def extract_citations(answer_text: str) -> list[str]:
    return re.findall(r'\[([^\]]+:\d+-\d+)\]', answer_text)
```

---

## 11. Demo Script for Recruiters

When demoing the project, use **FastAPI's own repo** as the target. It's a well-known Python codebase that any interviewer will recognize.

```bash
# Step 1: Ingest FastAPI's codebase
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi"}'

# Step 2: Ask questions
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How does FastAPI handle dependency injection?"}'

curl -X POST http://localhost:8000/query \
  -d '{"question": "Where is the OpenAPI spec generated?"}'

curl -X POST http://localhost:8000/query \
  -d '{"question": "How are path parameters validated?"}'
```

**Questions that make great demos:**
- "Where is authentication middleware defined?"
- "How does the router handle HTTP method routing?"
- "What happens when a request body validation fails?"
- "How are background tasks scheduled?"

Each answer should cite exact file paths and line numbers from the FastAPI source.

---

## 12. GitHub README Template

```markdown
# 🤖 Codebase Q&A Bot

Ask natural language questions about any GitHub repository and get cited, source-linked answers.

**"Where is authentication handled?" → `src/auth/jwt.py lines 12–45`**

## Demo

[GIF of the Streamlit UI here]

## Architecture

Ingestion: GitHub repo → Tree-sitter AST → function/class chunks → embeddings → ChromaDB
Query: question → embedding → cosine similarity → top-5 chunks → Claude API → cited answer

## What makes this different

Most RAG demos use PDFs. This project uses live code with AST-aware chunking via Tree-sitter —
meaning chunks always align to function and class boundaries, never arbitrary line splits.

## Tech Stack

| Layer | Technology |
|---|---|
| Code parsing | Tree-sitter |
| Vector store | ChromaDB |
| Embeddings | nomic-embed-code |
| LLM | Claude (claude-sonnet-4-6) |
| API | FastAPI |
| UI | Streamlit |

## Quick Start

git clone https://github.com/YOUR_USERNAME/codebase-qa-bot
cd codebase-qa-bot
pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY

# Run API
uvicorn api.main:app --reload

# Run UI (separate terminal)
streamlit run app/streamlit_app.py

## Project Structure

[paste the folder structure from Section 5]
```

---

## 13. LinkedIn Post Template

```
I just shipped a project that got me thinking differently about how developers navigate code.

🤖 Codebase Q&A Bot — ask natural language questions about any GitHub repo and get cited answers with exact file paths and line numbers.

The interesting engineering problem: most RAG tutorials split documents by line count (every 500 characters). For code, that's terrible — you end up with half-functions that mean nothing.

My solution: Tree-sitter AST-aware chunking. Instead of splitting arbitrarily, the parser builds a full syntax tree and extracts complete functions and classes as atomic chunks. A 120-line function stays as one unit.

Pipeline:
→ Clone repo with gitpython
→ Parse with Tree-sitter (understands Python, JS, TS, Go, and 40+ languages)
→ Embed with nomic-embed-code (code-specific, runs locally)
→ Store in ChromaDB with metadata (file, language, line range, chunk type)
→ At query time: embed question → cosine similarity → top-5 chunks → Claude API → cited answer

Demo: indexed the FastAPI repo (~400 chunks) and asked "how does dependency injection work?" — got a precise answer citing fastapi/dependencies/utils.py lines 187–234.

Full project with architecture diagram: [GitHub link]

#buildinpublic #rag #llm #python #fastapi #anthropic
```

---

## 14. Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `tree_sitter.Language` TypeError | Wrong tree-sitter version | Use `tree-sitter>=0.21` and `tree-sitter-python>=0.21` |
| ChromaDB `InvalidDimensionException` | Embedding dimensions mismatch | Delete `./chroma_db/` and re-ingest. Happens when you switch embedding models. |
| `SentenceTransformer` download hangs | First run downloads model weights | Normal — ~250MB download. Use `TRANSFORMERS_OFFLINE=1` after first download. |
| Empty retrieval results | Collection empty or wrong name | Verify `COLLECTION_NAME` matches in `embed.py` and `retrieve.py` |
| Claude API rate limit | Too many requests | Add `time.sleep(0.5)` between API calls in batch processing |
| `ModuleNotFoundError: ingest` | Running from wrong directory | Always run from the project root: `python -m ingest.parse` not `python ingest/parse.py` |
| Tree-sitter returns no chunks | File is too short or config-only | The module-level fallback in `parse.py` handles this — check logs |

---

## 15. How to Extend the Project

These are features you can add to take the project further:

### Multi-repo support
Allow indexing multiple repos simultaneously. Add a `repo_id` field to all metadata. Let the user filter queries by repo.

### Re-ranking
After retrieving top-10 chunks by cosine similarity, add a cross-encoder re-ranker (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) to re-score them by actual relevance to the question. Improves precision significantly.

### Streaming responses
Use Claude's streaming API (`client.messages.stream(...)`) to stream the answer token-by-token to the Streamlit UI. Much better UX for long answers.

### GitHub PR review bot
Instead of querying the whole repo, index only the changed files in a PR. Ask "what could go wrong with these changes?" — practical DevOps application.

### VS Code extension
Wrap the FastAPI backend in a VS Code extension. The user right-clicks any file → "Ask about this file" → question UI opens in sidebar. Real developer tool.

### Conversation memory
Store conversation history and pass it to Claude as prior turns. Users can ask follow-up questions like "and what about the test for that function?"

---

*Built with Tree-sitter · ChromaDB · FastAPI · Claude API*
*By Yash — Computer Engineering, MMIT Pune*
```
