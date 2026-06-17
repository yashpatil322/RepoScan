"""
languages.py — Language detection and Tree-sitter grammar mapping.

Maps file extensions to their Tree-sitter language objects and defines
which AST node types to extract as chunks for each language.

Languages are loaded with graceful degradation — if a tree-sitter-{lang}
package is not installed, that language is simply skipped (no crash).
"""

from tree_sitter import Language

# ──────────────────────────────────────────────────────────────────────
# Language Map: file extension → (language_name, tree_sitter_Language)
# Built dynamically — only includes languages whose packages are installed.
# ──────────────────────────────────────────────────────────────────────

LANGUAGE_MAP: dict[str, tuple[str, Language]] = {}


def _try_register(ext_list: list[str], lang_name: str, module_name: str, attr: str = "language"):
    """Attempt to import a tree-sitter language and register it."""
    try:
        import importlib
        mod = importlib.import_module(module_name)
        lang_fn = getattr(mod, attr)
        ts_language = Language(lang_fn())
        for ext in ext_list:
            LANGUAGE_MAP[ext] = (lang_name, ts_language)
    except (ImportError, AttributeError, Exception):
        pass  # Language package not installed — skip gracefully


# Register all supported languages
_try_register([".py", ".pyw"],          "python",     "tree_sitter_python")
_try_register([".js", ".jsx", ".mjs"],  "javascript", "tree_sitter_javascript")
_try_register([".java"],                "java",       "tree_sitter_java")
_try_register([".go"],                  "go",         "tree_sitter_go")
_try_register([".rs"],                  "rust",       "tree_sitter_rust")
_try_register([".c", ".h"],             "c",          "tree_sitter_c")
_try_register([".rb"],                  "ruby",       "tree_sitter_ruby")

# TypeScript is special — the package exposes two languages
try:
    import tree_sitter_typescript as ts_typescript
    ts_lang = Language(ts_typescript.language_typescript())
    tsx_lang = Language(ts_typescript.language_tsx())
    LANGUAGE_MAP[".ts"] = ("typescript", ts_lang)
    LANGUAGE_MAP[".tsx"] = ("tsx", tsx_lang)
except (ImportError, AttributeError, Exception):
    pass


# ──────────────────────────────────────────────────────────────────────
# Chunk Node Types: which AST node types to extract per language
# These represent the "logical boundaries" for code chunking.
# ──────────────────────────────────────────────────────────────────────

CHUNK_NODE_TYPES: dict[str, list[str]] = {
    "python": [
        "function_definition",
        "class_definition",
    ],
    "javascript": [
        "function_declaration",
        "class_declaration",
        "arrow_function",
        "method_definition",
        "export_statement",
    ],
    "typescript": [
        "function_declaration",
        "class_declaration",
        "arrow_function",
        "method_definition",
        "interface_declaration",
        "type_alias_declaration",
        "export_statement",
    ],
    "tsx": [
        "function_declaration",
        "class_declaration",
        "arrow_function",
        "method_definition",
        "interface_declaration",
        "type_alias_declaration",
        "export_statement",
    ],
    "java": [
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "constructor_declaration",
        "enum_declaration",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
    "rust": [
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
    ],
    "c": [
        "function_definition",
        "struct_specifier",
        "enum_specifier",
    ],
    "ruby": [
        "method",
        "singleton_method",
        "class",
        "module",
    ],
}


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

# All extensions that have a loaded Tree-sitter grammar
SUPPORTED_EXTENSIONS: list[str] = list(LANGUAGE_MAP.keys())


def get_language_info() -> list[dict]:
    """
    Return info about all supported languages for the /languages endpoint.

    Returns:
        List of dicts with language name, supported extensions, and chunk types.
    """
    # Group extensions by language name
    lang_extensions: dict[str, list[str]] = {}
    for ext, (lang_name, _) in LANGUAGE_MAP.items():
        lang_extensions.setdefault(lang_name, []).append(ext)

    result = []
    for lang_name, extensions in sorted(lang_extensions.items()):
        result.append({
            "language": lang_name,
            "extensions": sorted(extensions),
            "chunk_types": CHUNK_NODE_TYPES.get(lang_name, []),
        })

    return result
