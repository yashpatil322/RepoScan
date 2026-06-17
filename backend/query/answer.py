from __future__ import annotations

"""
answer.py — Gemini API prompt builder, answer generator, and streaming support.

This module handles the final step of the RAG pipeline:
1. Takes retrieved code chunks + user question
2. Builds a carefully engineered prompt with anti-hallucination constraints
3. Calls Google Gemini API to generate a cited answer
4. Extracts inline citations from the response
5. Supports both full-response and streaming modes

Uses google-genai SDK (free tier) instead of Anthropic Claude.
"""

import os
import re
from typing import Generator

from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load .env file for API key
load_dotenv()


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Maximum tokens for the generated answer
MAX_OUTPUT_TOKENS = 2048

# System instruction for the LLM
SYSTEM_INSTRUCTION = """You are an expert code assistant helping a developer understand a codebase.

Your job is to answer questions about the codebase using ONLY the provided code chunks.

Rules you MUST follow:
1. Answer ONLY using the code chunks provided. Do NOT use any outside knowledge about libraries, frameworks, or patterns.
2. Cite every file you reference using the format [filename:line_start-line_end]. For example: [src/auth/jwt.py:12-45]
3. If the answer is not in the provided chunks, say "I could not find this in the retrieved code chunks."
4. Be concise. Developers prefer short, precise answers with code references over long explanations.
5. If relevant, quote the specific function or class name from the chunks.
6. When multiple chunks are relevant, synthesize the information and cite all relevant sources.
7. Structure your answer with clear sections if the question requires a multi-part answer."""


def _get_client() -> genai.Client:
    """Get the Gemini API client."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. "
            "Get a free API key at https://aistudio.google.com/apikey "
            "and add it to your .env file."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


# ──────────────────────────────────────────────────────────────────────
# Prompt Building
# ──────────────────────────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict]) -> str:
    """
    Build a structured prompt with retrieved code chunks as context.

    The prompt format is designed to:
    - Clearly separate each chunk with metadata headers
    - Include similarity scores so the LLM knows which chunks are most relevant
    - Enforce citation format
    - Prevent hallucination

    Args:
        question: The user's natural language question.
        chunks: List of retrieved chunk dicts from retrieve.py.

    Returns:
        Formatted prompt string ready for the LLM.
    """
    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        score = chunk.get("similarity_score", 0)

        context_parts.append(
            f"--- Chunk {i} (relevance: {score:.2f}) ---\n"
            f"File: {meta.get('file_path', 'unknown')} "
            f"(lines {meta.get('start_line', '?')}–{meta.get('end_line', '?')})\n"
            f"Type: {meta.get('chunk_type', 'unknown')} | "
            f"Name: {meta.get('name', 'unknown')} | "
            f"Language: {meta.get('language', 'unknown')}\n\n"
            f"{chunk.get('text', '')}"
        )

    context = "\n\n".join(context_parts)

    prompt = (
        f"You have been given the following relevant code chunks "
        f"retrieved from the repository:\n\n"
        f"{context}\n\n"
        f"---\n\n"
        f"Based ONLY on the code chunks above, answer this question:\n"
        f"{question}\n\n"
        f"Remember: cite every file using [filename:line_start-line_end] format. "
        f"If the code doesn't contain the answer, say so."
    )

    return prompt


# ──────────────────────────────────────────────────────────────────────
# Citation Extraction
# ──────────────────────────────────────────────────────────────────────

def extract_citations(answer_text: str) -> list[str]:
    """
    Extract inline citations from the LLM's answer.

    Looks for patterns like:
    - [src/auth/jwt.py:12-45]
    - [utils.py:100-120]
    - [main.go:5-30]

    Returns:
        Deduplicated list of citation strings.
    """
    pattern = r'\[([^\]]+?:\d+[\-–]\d+)\]'
    matches = re.findall(pattern, answer_text)
    # Normalize en-dash to hyphen and deduplicate
    normalized = list(dict.fromkeys(m.replace("–", "-") for m in matches))
    return normalized


# ──────────────────────────────────────────────────────────────────────
# Answer Generation (Full Response)
# ──────────────────────────────────────────────────────────────────────

def generate_answer(question: str, chunks: list[dict]) -> dict:
    """
    Generate a full answer using Google Gemini.

    Args:
        question: The user's question.
        chunks: Retrieved code chunks from similarity search.

    Returns:
        Dict with:
        - answer: the LLM's response text
        - sources: list of source info dicts from the chunks
        - citations: extracted citation references
        - chunks_used: number of chunks in context
        - model: model name used
    """
    client = _get_client()
    prompt = build_prompt(question, chunks)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.2,  # Low temperature for factual, precise answers
        ),
    )

    answer_text = response.text or "No response generated."

    # Extract citations from the answer
    citations = extract_citations(answer_text)

    # Build source info from chunks
    sources = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        sources.append({
            "file_path": meta.get("file_path", ""),
            "start_line": meta.get("start_line", 0),
            "end_line": meta.get("end_line", 0),
            "name": meta.get("name", ""),
            "chunk_type": meta.get("chunk_type", ""),
            "language": meta.get("language", ""),
            "similarity_score": chunk.get("similarity_score", 0),
        })

    return {
        "answer": answer_text,
        "sources": sources,
        "citations": citations,
        "chunks_used": len(chunks),
        "model": GEMINI_MODEL,
    }


# ──────────────────────────────────────────────────────────────────────
# Answer Generation (Streaming via SSE)
# ──────────────────────────────────────────────────────────────────────

def generate_answer_stream(question: str, chunks: list[dict]) -> Generator[str, None, None]:
    """
    Stream the answer token-by-token using Gemini's streaming API.

    Yields individual text chunks as they arrive from the API.
    Used by the POST /query/stream endpoint with Server-Sent Events.

    Args:
        question: The user's question.
        chunks: Retrieved code chunks from similarity search.

    Yields:
        Text fragments as they arrive from the LLM.
    """
    client = _get_client()
    prompt = build_prompt(question, chunks)

    response_stream = client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.2,
        ),
    )

    for chunk in response_stream:
        if chunk.text:
            yield chunk.text
