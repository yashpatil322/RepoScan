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

    parser = Parser()
    parser.language = ts_language

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
