"""ChromaDB vector store with separate collections for visual and speech search."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import chromadb


DEFAULT_DB_PATH = Path.home() / ".narrafind" / "db"


def _make_chunk_id(source_file: str, start_time: float, prefix: str = "") -> str:
    """Deterministic chunk ID from source file + start time."""
    raw = f"{prefix}{source_file}:{start_time}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class NarraStore:
    """Persistent vector store backed by ChromaDB.

    Maintains two collections:
    - visual: video chunk embeddings (Gemini visual embedding)
    - speech: transcript text embeddings (Gemini text embedding)
    """

    def __init__(self, db_path: str | Path | None = None):
        db_path = str(db_path or DEFAULT_DB_PATH)
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=db_path)

        self._visual = self._client.get_or_create_collection(
            name="narrafind_visual",
            metadata={"hnsw:space": "cosine", "search_type": "visual"},
        )
        self._speech = self._client.get_or_create_collection(
            name="narrafind_speech",
            metadata={"hnsw:space": "cosine", "search_type": "speech"},
        )

    @property
    def visual(self) -> chromadb.Collection:
        return self._visual

    @property
    def speech(self) -> chromadb.Collection:
        return self._speech

    # ------------------------------------------------------------------
    # Write — Visual
    # ------------------------------------------------------------------

    def add_visual_chunks(self, chunks: list[dict]) -> None:
        """Batch-store visual embeddings."""
        if not chunks:
            return
        now = datetime.now(timezone.utc).isoformat()
        ids = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            chunk_id = _make_chunk_id(chunk["source_file"], chunk["start_time"], "v:")
            ids.append(chunk_id)
            embeddings.append(chunk["embedding"])
            metadatas.append({
                "source_file": chunk["source_file"],
                "start_time": float(chunk["start_time"]),
                "end_time": float(chunk["end_time"]),
                "indexed_at": now,
            })

        self._visual.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    # ------------------------------------------------------------------
    # Write — Speech
    # ------------------------------------------------------------------

    def add_speech_chunks(self, chunks: list[dict]) -> None:
        """Batch-store speech/transcript embeddings.

        Each chunk dict should have: source_file, start_time, end_time,
        embedding, transcript.
        """
        if not chunks:
            return
        now = datetime.now(timezone.utc).isoformat()
        ids = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            chunk_id = _make_chunk_id(chunk["source_file"], chunk["start_time"], "s:")
            ids.append(chunk_id)
            embeddings.append(chunk["embedding"])
            metadatas.append({
                "source_file": chunk["source_file"],
                "start_time": float(chunk["start_time"]),
                "end_time": float(chunk["end_time"]),
                "transcript": chunk.get("transcript", ""),
                "indexed_at": now,
            })

        self._speech.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search_visual(
        self,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[dict]:
        """Search visual collection."""
        return self._search_collection(self._visual, query_embedding, n_results)

    def search_speech(
        self,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[dict]:
        """Search speech collection."""
        return self._search_collection(self._speech, query_embedding, n_results)

    def _search_collection(
        self,
        collection: chromadb.Collection,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[dict]:
        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, count),
        )

        hits = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            hits.append({
                "source_file": meta["source_file"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "transcript": meta.get("transcript", ""),
                "score": 1.0 - distance,
                "distance": distance,
            })
        return hits

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def is_indexed(self, source_file: str) -> bool:
        """Check whether any chunks from source_file are already stored."""
        visual_results = self._visual.get(
            where={"source_file": source_file}, limit=1,
        )
        return len(visual_results["ids"]) > 0

    def remove_file(self, source_file: str) -> int:
        """Remove all chunks (visual + speech) for a given source file."""
        total = 0
        for col in (self._visual, self._speech):
            results = col.get(where={"source_file": source_file})
            ids = results["ids"]
            if ids:
                col.delete(ids=ids)
                total += len(ids)
        return total

    def get_stats(self) -> dict:
        """Return combined store statistics."""
        visual_count = self._visual.count()
        speech_count = self._speech.count()
        total = visual_count + speech_count

        if total == 0:
            return {
                "total_chunks": 0,
                "visual_chunks": 0,
                "speech_chunks": 0,
                "unique_source_files": 0,
                "source_files": [],
            }

        source_files = set()
        if visual_count > 0:
            all_meta = self._visual.get(include=["metadatas"])
            source_files.update(m["source_file"] for m in all_meta["metadatas"])
        if speech_count > 0:
            all_meta = self._speech.get(include=["metadatas"])
            source_files.update(m["source_file"] for m in all_meta["metadatas"])

        return {
            "total_chunks": total,
            "visual_chunks": visual_count,
            "speech_chunks": speech_count,
            "unique_source_files": len(source_files),
            "source_files": sorted(source_files),
        }

    def reset(self) -> None:
        """Delete all data from both collections."""
        self._client.delete_collection("narrafind_visual")
        self._client.delete_collection("narrafind_speech")
        # Recreate empty collections
        self._visual = self._client.get_or_create_collection(
            name="narrafind_visual",
            metadata={"hnsw:space": "cosine", "search_type": "visual"},
        )
        self._speech = self._client.get_or_create_collection(
            name="narrafind_speech",
            metadata={"hnsw:space": "cosine", "search_type": "speech"},
        )
