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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Ask a question about the indexed codebase."""
    try:
        chunks = retrieve(request.question, top_k=request.top_k)
        if not chunks:
            raise HTTPException(status_code=404, detail="No matching code chunks found. Ingest a repository first.")
        result = answer(request.question, chunks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
