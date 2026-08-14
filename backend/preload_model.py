"""
preload_model.py — Pre-download the fastembed ONNX embedding model
during the Render BUILD phase so the first request doesn't stall.

fastembed downloads a small ONNX model (~25MB for all-MiniLM-L6-v2)
compared to ~450MB for the full PyTorch sentence-transformers stack.
This is also why we switched: fastembed uses ~80MB RAM vs ~400MB for
sentence-transformers — critical for staying under Render's 512MB limit.
"""

import os
import sys

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

print(f"[preload] Downloading fastembed model: {MODEL_NAME}")

try:
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=MODEL_NAME)
    # Run a tiny encode to confirm the ONNX model is ready
    _ = list(model.embed(["warm up"]))
    print(f"[preload] ✅ fastembed model '{MODEL_NAME}' ready.")
except Exception as e:
    print(f"[preload] ⚠️  Model download failed: {e}", file=sys.stderr)
    # Don't fail the build — model will download on first request instead
    sys.exit(0)
