"""Embedder factory — returns the appropriate backend."""

from .base_embedder import BaseEmbedder

_embedder: BaseEmbedder | None = None


def get_embedder(backend: str = "gemini", **kwargs) -> BaseEmbedder:
    """Return a singleton embedder for the given backend."""
    global _embedder
    if _embedder is not None:
        return _embedder

    if backend == "gemini":
        from .gemini_embedder import GeminiEmbedder
        _embedder = GeminiEmbedder()
    else:
        raise ValueError(f"Unknown backend: {backend}")

    return _embedder


def reset_embedder() -> None:
    """Release the cached embedder (frees GPU memory for local backends)."""
    global _embedder
    _embedder = None
