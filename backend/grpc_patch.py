"""
grpc_patch.py — Stub out gRPC before ChromaDB can import its native DLL.

Problem:
    ChromaDB imports `opentelemetry-exporter-otlp-proto-grpc` at startup,
    which in turn loads grpc's native C extension (cygrpc.pyd).
    On some Windows machines, Windows Defender Application Control (WDAC)
    or AppLocker blocks this DLL from loading:

        ImportError: DLL load failed while importing cygrpc:
        An Application Control policy has blocked this file.

    This crash happens even though we never use gRPC ourselves — ChromaDB
    imports it unconditionally for its OpenTelemetry telemetry pipeline.

Solution:
    Before importing chromadb, inject lightweight stub modules into
    sys.modules for every grpc-related module that ChromaDB touches.
    Python's import system finds these stubs first and never tries to
    load the native DLL.

    ChromaDB's local PersistentClient uses SQLite + HNSW — zero gRPC
    required. The stubs only affect the telemetry exporter, which is
    never invoked in a local dev setup.

Usage:
    import grpc_patch          # must be the VERY FIRST import in main.py
    grpc_patch.apply()
"""

import sys
import types


def apply() -> None:
    """
    Inject grpc stubs into sys.modules before ChromaDB is imported.

    Safe to call multiple times — checks whether grpc was already
    successfully imported before doing anything.
    """
    # If grpc already loaded cleanly (e.g. policy allows it), do nothing
    if "grpc" in sys.modules:
        existing = sys.modules["grpc"]
        # Make sure it's a real module, not our own stub
        if hasattr(existing, "_is_stub"):
            pass  # Our stub — continue with patching
        else:
            return  # Real grpc loaded fine — no patch needed

    # Try to import grpc for real first
    try:
        import grpc  # noqa: F401
        # Succeeded — no stub needed
        return
    except (ImportError, OSError):
        # ImportError: DLL load failed — we need to stub it out
        pass

    _inject_grpc_stubs()
    _inject_otel_grpc_stubs()


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _make_stub(name: str) -> types.ModuleType:
    """Create a named stub module and register it."""
    mod = types.ModuleType(name)
    mod._is_stub = True  # marker so we can detect our own stubs
    sys.modules[name] = mod
    return mod


def _inject_grpc_stubs() -> None:
    """
    Stub the grpc package and its sub-modules that ChromaDB touches.

    We provide just enough attributes to satisfy the import chain without
    loading any native code.
    """
    # Core grpc stub
    grpc_stub = _make_stub("grpc")

    # Attribute stubs — classes ChromaDB/otel reference at class-definition time
    grpc_stub.ChannelCredentials = type("ChannelCredentials", (), {})
    grpc_stub.Compression = type(
        "Compression", (),
        {"NoCompression": 0, "Deflate": 1, "Gzip": 2}
    )
    grpc_stub.StatusCode = type("StatusCode", (), {"OK": 0})
    grpc_stub.Channel = type("Channel", (), {})
    grpc_stub.CallCredentials = type("CallCredentials", (), {})
    grpc_stub.insecure_channel = lambda *a, **kw: None
    grpc_stub.secure_channel = lambda *a, **kw: None
    grpc_stub.ssl_channel_credentials = lambda *a, **kw: None
    grpc_stub.composite_channel_credentials = lambda *a, **kw: None
    grpc_stub.metadata_call_credentials = lambda *a, **kw: None

    # Sub-modules
    for sub in ("_compression", "_channel", "_interceptor",
                 "_utilities", "_cython", "_cython.cygrpc",
                 "experimental", "aio", "aio._channel"):
        _make_stub(f"grpc.{sub}")

    # grpc._compression is imported directly in some paths
    _make_stub("grpc._compression")


def _inject_otel_grpc_stubs() -> None:
    """
    Stub the opentelemetry gRPC exporters that ChromaDB imports at module level.

    The import chain ChromaDB triggers:
        chromadb.auth.token_authn
          → chromadb.telemetry.opentelemetry
              → opentelemetry.exporter.otlp.proto.grpc.trace_exporter
                  → grpc  (the blocked DLL)
    """
    # Build up the package hierarchy so Python's import system is happy
    _make_stub("opentelemetry.exporter.otlp.proto.grpc")

    # trace_exporter stub — provides OTLPSpanExporter which chromadb imports
    trace_stub = _make_stub(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
    )
    trace_stub.OTLPSpanExporter = type(
        "OTLPSpanExporter", (),
        {
            "__init__": lambda self, *a, **kw: None,
            "export": lambda self, *a, **kw: None,
            "shutdown": lambda self, *a, **kw: None,
        }
    )

    # Additional grpc exporter sub-modules referenced in some chromadb versions
    for sub in ("_log_exporter", "metric_exporter", "exporter"):
        mod = _make_stub(
            f"opentelemetry.exporter.otlp.proto.grpc.{sub}"
        )
        # Provide commonly imported names as empty stubs
        mod.OTLPLogExporter = type("OTLPLogExporter", (), {"__init__": lambda self, *a, **kw: None})
        mod.OTLPMetricExporter = type("OTLPMetricExporter", (), {"__init__": lambda self, *a, **kw: None})
