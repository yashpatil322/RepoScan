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
    if results and "documents" in results and results["documents"]:
        for i in range(len(results["documents"][0])):
            chunks.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity_score": 1 - results["distances"][0][i],  # cosine distance → similarity
            })

    return chunks
