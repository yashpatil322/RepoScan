from pydantic import BaseModel, HttpUrl

class IngestRequest(BaseModel):
    repo_url: str

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
