"""
preload_model.py — Pre-download the sentence-transformer embedding model
during the Render BUILD phase so the first /query request doesn't time out.

Called by the build command (see render.yaml):
    pip install -r requirements.txt && python preload_model.py

The model (~90MB for all-MiniLM-L6-v2) is cached in HuggingFace's default
cache directory, which persists between Render builds on the same instance.
"""

import os
import sys

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

print(f"[preload] Downloading embedding model: {MODEL_NAME}")

try:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
    # Run a tiny test to confirm it works
    _ = model.encode(["test"])
    print(f"[preload] ✅ Model '{MODEL_NAME}' ready.")
except Exception as e:
    print(f"[preload] ⚠️  Model download failed: {e}", file=sys.stderr)
    # Don't fail the build — the model will download on first request instead
    sys.exit(0)
