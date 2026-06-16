from tree_sitter import Language
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript

# Map file extension → (language name, tree-sitter language object)
LANGUAGE_MAP = {
    ".py":  ("python",     Language(tspython.language())),
    ".js":  ("javascript", Language(tsjavascript.language())),
}

# Node types to extract as chunks (varies by language)
CHUNK_NODE_TYPES = {
    "python": ["function_definition", "class_definition"],
    "javascript": ["function_declaration", "class_declaration",
                   "arrow_function", "method_definition"],
}

SUPPORTED_EXTENSIONS = list(LANGUAGE_MAP.keys())
