"""Hybrid search — combines visual and speech results."""

from __future__ import annotations


def search_footage(
    query: str,
    store,
    embedder,
    n_results: int = 5,
    mode: str = "hybrid",
    visual_weight: float = 0.5,
    speech_weight: float = 0.5,
    verbose: bool = False,
) -> list[dict]:
    """Search indexed footage with a natural language query.

    Args:
        query: Natural language search query.
        store: NarraStore instance.
        embedder: Embedder instance (must support embed_query).
        n_results: Number of results to return.
        mode: Search mode — 'visual', 'speech', or 'hybrid'.
        visual_weight: Weight for visual scores in hybrid mode.
        speech_weight: Weight for speech scores in hybrid mode.
        verbose: Print debug info.

    Returns:
        List of result dicts sorted by similarity_score (descending).
    """
    query_embedding = embedder.embed_query(query, verbose=verbose)

    visual_results = []
    speech_results = []

    if mode in ("visual", "hybrid"):
        visual_results = store.search_visual(query_embedding, n_results=n_results * 2)

    if mode in ("speech", "hybrid"):
        speech_results = store.search_speech(query_embedding, n_results=n_results * 2)

    if mode == "visual":
        return _format_results(visual_results, n_results, search_type="visual")
    if mode == "speech":
        return _format_results(speech_results, n_results, search_type="speech")

    # Hybrid: merge and re-rank
    return _merge_results(
        visual_results, speech_results,
        visual_weight=visual_weight,
        speech_weight=speech_weight,
        n_results=n_results,
    )


def _format_results(
    hits: list[dict],
    n_results: int,
    search_type: str = "",
) -> list[dict]:
    """Format raw ChromaDB hits into result dicts."""
    results = []
    for hit in hits[:n_results]:
        results.append({
            "source_file": hit["source_file"],
            "start_time": hit["start_time"],
            "end_time": hit["end_time"],
            "similarity_score": hit["score"],
            "transcript": hit.get("transcript", ""),
            "search_type": search_type,
        })
    return results


def _merge_results(
    visual_hits: list[dict],
    speech_hits: list[dict],
    visual_weight: float = 0.5,
    speech_weight: float = 0.5,
    n_results: int = 5,
) -> list[dict]:
    """Merge visual and speech results using weighted scoring.

    Results that match in both collections get a boosted score.
    Uses a time-overlap based matching strategy.
    """
    # Build a combined set keyed by (source_file, approximate_start)
    combined: dict[str, dict] = {}

    for hit in visual_hits:
        key = _result_key(hit)
        combined[key] = {
            "source_file": hit["source_file"],
            "start_time": hit["start_time"],
            "end_time": hit["end_time"],
            "visual_score": hit["score"],
            "speech_score": 0.0,
            "transcript": "",
        }

    for hit in speech_hits:
        key = _result_key(hit)
        if key in combined:
            # Overlapping — merge scores
            combined[key]["speech_score"] = hit["score"]
            combined[key]["transcript"] = hit.get("transcript", "")
        else:
            # Check for time-overlapping entries
            merged = False
            for existing_key, existing in combined.items():
                if _time_overlaps(existing, hit):
                    existing["speech_score"] = max(
                        existing["speech_score"], hit["score"]
                    )
                    if not existing["transcript"]:
                        existing["transcript"] = hit.get("transcript", "")
                    merged = True
                    break
            if not merged:
                combined[key] = {
                    "source_file": hit["source_file"],
                    "start_time": hit["start_time"],
                    "end_time": hit["end_time"],
                    "visual_score": 0.0,
                    "speech_score": hit["score"],
                    "transcript": hit.get("transcript", ""),
                }

    # Calculate weighted scores
    results = []
    for entry in combined.values():
        if entry["visual_score"] > 0 and entry["speech_score"] > 0:
            # Both matched — weighted combination
            score = (
                visual_weight * entry["visual_score"]
                + speech_weight * entry["speech_score"]
            )
            search_type = "hybrid"
        elif entry["visual_score"] > 0:
            score = entry["visual_score"]
            search_type = "visual"
        else:
            score = entry["speech_score"]
            search_type = "speech"

        results.append({
            "source_file": entry["source_file"],
            "start_time": entry["start_time"],
            "end_time": entry["end_time"],
            "similarity_score": score,
            "transcript": entry["transcript"],
            "search_type": search_type,
        })

    results.sort(key=lambda r: r["similarity_score"], reverse=True)
    return results[:n_results]


def _result_key(hit: dict) -> str:
    """Create a lookup key from a result for merging."""
    # Round start_time to nearest 5s to handle slight boundary differences
    rounded_start = round(hit["start_time"] / 5.0) * 5.0
    return f"{hit['source_file']}:{rounded_start:.0f}"


def _time_overlaps(a: dict, b: dict) -> bool:
    """Check if two results overlap in time and are from the same file."""
    if a["source_file"] != b["source_file"]:
        return False
    return a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]
