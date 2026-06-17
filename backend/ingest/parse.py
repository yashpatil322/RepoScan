"""
parse.py — Tree-sitter AST-aware code chunker.

This is the core of the ingestion pipeline. Instead of naively splitting code
by line count (which destroys function boundaries), we use Tree-sitter to parse
each file into a Concrete Syntax Tree and extract complete, meaningful units:

- Functions (with their full body)
- Classes (with all methods)
- Module-level code (imports, constants, config — as a fallback)

Each chunk gets rich metadata: file path, language, line range, name, and type.
Metadata is also prepended to the chunk text before embedding to improve
semantic search quality.
"""

import os
from tree_sitter import Parser
from .languages import LANGUAGE_MAP, CHUNK_NODE_TYPES

# Maximum lines for a single chunk. Functions longer than this get truncated
# with a metadata flag so the LLM knows the code is incomplete.
MAX_CHUNK_LINES = 150

# Maximum characters for module-level fallback chunks (imports, config files, etc.)
MAX_MODULE_CHUNK_CHARS = 4000


def _extract_node_name(node, source_bytes: bytes) -> str:
    """
    Extract the identifier (name) from a function or class AST node.

    Walks the node's direct children looking for an 'identifier' or
    'property_identifier' node and returns its text.

    Returns 'anonymous' if no name is found (e.g., arrow functions).
    """
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "type_identifier"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
    return "anonymous"


def _classify_chunk_type(node_type: str) -> str:
    """Map an AST node type to a human-readable chunk category."""
    if "class" in node_type or "struct" in node_type or "impl" in node_type:
        return "class"
    if "interface" in node_type or "trait" in node_type:
        return "interface"
    if "enum" in node_type:
        return "enum"
    if "type" in node_type and "alias" in node_type:
        return "type_alias"
    if "module" in node_type:
        return "module"
    # Default: everything else is a function/method
    return "function"


def _build_enriched_text(chunk_text: str, metadata: dict) -> str:
    """
    Prepend metadata to chunk text for better embedding quality.

    The embedding model sees both the structural context AND the code,
    which produces much better semantic search results than raw code alone.

    Example output:
        file: src/auth/jwt.py
        language: python
        function: verify_token (lines 12–45)

        def verify_token(token: str) -> dict:
            ...
    """
    header = (
        f"file: {metadata['file_path']}\n"
        f"language: {metadata['language']}\n"
        f"{metadata['chunk_type']}: {metadata['name']} "
        f"(lines {metadata['start_line']}–{metadata['end_line']})\n"
    )
    return header + "\n" + chunk_text


def parse_file(file_path: str, repo_root: str) -> list[dict]:
    """
    Parse a single source file using Tree-sitter and extract code chunks.

    Each chunk is a complete, semantically meaningful unit of code (function,
    class, or module-level block) with rich metadata for retrieval.

    Args:
        file_path: Absolute path to the source file.
        repo_root: Absolute path to the repo root (for computing relative paths).

    Returns:
        List of chunk dicts, each containing:
        - text: raw source code of the chunk
        - enriched_text: metadata-prepended text for embedding
        - file_path: path relative to repo root
        - language: language name (e.g., "python")
        - chunk_type: "function" | "class" | "interface" | "enum" | "module"
        - start_line: 1-indexed first line
        - end_line: 1-indexed last line
        - name: function/class name (or filename for module chunks)
        - truncated: True if the chunk was truncated due to size
    """
    ext = os.path.splitext(file_path)[1]
    if ext not in LANGUAGE_MAP:
        return []

    lang_name, ts_language = LANGUAGE_MAP[ext]
    node_types = set(CHUNK_NODE_TYPES.get(lang_name, []))

    if not node_types:
        return []

    # Read file as bytes (Tree-sitter works with bytes)
    try:
        with open(file_path, "rb") as f:
            source_bytes = f.read()
    except (OSError, IOError):
        return []

    # Skip empty files and binary files (heuristic: check for null bytes)
    if not source_bytes or b"\x00" in source_bytes[:1024]:
        return []

    # Compute relative path for clean display
    rel_path = os.path.relpath(file_path, repo_root).replace("\\", "/")

    # Parse with Tree-sitter
    parser = Parser(ts_language)
    tree = parser.parse(source_bytes)

    chunks = []
    covered_ranges = []  # Track which byte ranges are covered by named chunks

    def walk(node, depth=0):
        """
        Recursively walk the AST, extracting chunks at logical boundaries.

        We extract top-level functions and classes. For classes, we extract
        the entire class (including all methods) as one chunk, rather than
        extracting each method separately — this preserves class context.

        We don't recurse into extracted nodes (nested functions stay as part
        of their parent chunk).
        """
        if node.type in node_types:
            chunk_text = source_bytes[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace"
            )
            chunk_type = _classify_chunk_type(node.type)
            name = _extract_node_name(node, source_bytes)
            start_line = node.start_point[0] + 1  # Tree-sitter is 0-indexed
            end_line = node.end_point[0] + 1
            line_count = end_line - start_line + 1

            # Handle oversized chunks
            truncated = False
            if line_count > MAX_CHUNK_LINES:
                lines = chunk_text.split("\n")
                chunk_text = "\n".join(lines[:MAX_CHUNK_LINES]) + "\n# ... (truncated)"
                end_line = start_line + MAX_CHUNK_LINES - 1
                truncated = True

            metadata = {
                "file_path": rel_path,
                "language": lang_name,
                "chunk_type": chunk_type,
                "start_line": start_line,
                "end_line": end_line,
                "name": name,
                "truncated": truncated,
            }

            chunks.append({
                "text": chunk_text,
                "enriched_text": _build_enriched_text(chunk_text, metadata),
                **metadata,
            })

            covered_ranges.append((node.start_byte, node.end_byte))

            # Don't recurse into this node — nested functions/classes
            # are part of the parent chunk's text
            return

        # Recurse into children
        for child in node.children:
            walk(child, depth + 1)

    walk(tree.root_node)

    # ── Module-level fallback ──────────────────────────────────────────
    # If no named chunks were found (config files, scripts with only
    # top-level code), treat the entire file as one module chunk.
    # Also, capture significant module-level code that isn't inside
    # any function/class (imports, constants, global setup).
    if not chunks:
        full_text = source_bytes.decode("utf-8", errors="replace")
        if full_text.strip():
            truncated = len(full_text) > MAX_MODULE_CHUNK_CHARS
            if truncated:
                full_text = full_text[:MAX_MODULE_CHUNK_CHARS] + "\n# ... (truncated)"

            metadata = {
                "file_path": rel_path,
                "language": lang_name,
                "chunk_type": "module",
                "start_line": 1,
                "end_line": source_bytes.count(b"\n") + 1,
                "name": os.path.basename(file_path),
                "truncated": truncated,
            }

            chunks.append({
                "text": full_text,
                "enriched_text": _build_enriched_text(full_text, metadata),
                **metadata,
            })

    return chunks


def parse_repo(repo_path: str, code_files: list[str]) -> list[dict]:
    """
    Parse all code files in a repository and return all extracted chunks.

    Args:
        repo_path: Absolute path to the cloned repository root.
        code_files: List of absolute paths to source files to parse.

    Returns:
        List of all chunk dicts across all files.
    """
    all_chunks = []
    for file_path in code_files:
        file_chunks = parse_file(file_path, repo_path)
        all_chunks.extend(file_chunks)
    return all_chunks
