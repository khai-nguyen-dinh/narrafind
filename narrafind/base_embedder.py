"""Abstract base class for embedding backends."""

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Interface that all embedding backends must implement."""

    @abstractmethod
    def embed_video_chunk(self, chunk_path: str, verbose: bool = False) -> list[float]:
        """Embed a video chunk file and return a vector."""

    @abstractmethod
    def embed_query(self, query_text: str, verbose: bool = False) -> list[float]:
        """Embed a text query and return a vector."""

    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of embeddings produced by this backend."""
