import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

def build_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"--- Chunk {i} ---\n"
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
- Cite every file you reference using the format [filename:line_start-line_end] (e.g. [api/main.py:12-45])
- If the answer is not in the provided chunks, say "I could not find this in the retrieved code."
- Be concise. Developers prefer short, precise answers with code references over long explanations.
- If relevant, quote the specific function or class name from the chunks.
"""

def answer(question: str, chunks: list[dict]) -> dict:
    """
    Send retrieved chunks + question to Gemini and return the answer.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = build_prompt(question, chunks)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    print(f"Calling Gemini API ({model_name}) ...")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    
    answer_text = response.text

    # Extract cited files from the chunks for the response
    cited_files = list({
        f"{c['metadata']['file_path']} (lines {c['metadata']['start_line']}-{c['metadata']['end_line']})"
        for c in chunks
    })

    return {
        "answer": answer_text,
        "sources": cited_files,
        "chunks_used": len(chunks),
    }
