"""Whisper-based audio transcription for speech search."""

import os
import sys
import tempfile


def transcribe_audio(
    audio_path: str,
    model_name: str = "base",
    language: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Transcribe an audio file using OpenAI Whisper.

    Args:
        audio_path: Path to WAV audio file.
        model_name: Whisper model size (tiny, base, small, medium, large).
        language: Language code (e.g. 'en', 'vi'). None for auto-detect.
        verbose: Print debug info.

    Returns:
        List of segment dicts with keys: start, end, text.
    """
    import whisper

    if verbose:
        print(f"  [verbose] Loading Whisper model: {model_name}", file=sys.stderr)

    model = whisper.load_model(model_name)

    if verbose:
        print(f"  [verbose] Transcribing: {audio_path}", file=sys.stderr)

    options = {}
    if language:
        options["language"] = language

    result = model.transcribe(audio_path, **options)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        })

    if verbose:
        total_segs = len(segments)
        detected_lang = result.get("language", "unknown")
        print(
            f"  [verbose] Transcribed {total_segs} segments, "
            f"detected language: {detected_lang}",
            file=sys.stderr,
        )

    return segments


def transcribe_video_chunks(
    chunks: list[dict],
    model_name: str = "base",
    language: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Transcribe audio from video chunks and return segments with global timestamps.

    Args:
        chunks: List of chunk dicts (source_file, start_time, end_time, chunk_path).
        model_name: Whisper model size.
        language: Language code or None for auto-detect.
        verbose: Print debug info.

    Returns:
        List of transcript segment dicts with global timestamps and text.
        Each has: source_file, start_time, end_time, text.
    """
    from .chunker import extract_audio_chunk

    all_segments = []

    for chunk in chunks:
        source_file = chunk["source_file"]
        chunk_start = chunk["start_time"]
        chunk_end = chunk["end_time"]

        # Extract audio for this chunk's time range from the original video
        try:
            audio_path = extract_audio_chunk(
                source_file, chunk_start, chunk_end,
            )
        except Exception as e:
            if verbose:
                print(
                    f"  [verbose] Failed to extract audio for chunk "
                    f"{chunk_start:.1f}-{chunk_end:.1f}: {e}",
                    file=sys.stderr,
                )
            continue

        try:
            segments = transcribe_audio(
                audio_path, model_name=model_name,
                language=language, verbose=verbose,
            )

            for seg in segments:
                if not seg["text"]:
                    continue
                all_segments.append({
                    "source_file": source_file,
                    "start_time": chunk_start + seg["start"],
                    "end_time": chunk_start + seg["end"],
                    "text": seg["text"],
                })
        finally:
            try:
                os.unlink(audio_path)
            except OSError:
                pass

    return all_segments


def group_transcript_by_chunks(
    segments: list[dict],
    chunk_duration: float = 30.0,
    overlap: float = 5.0,
) -> list[dict]:
    """Group transcript segments into time-aligned chunks for embedding.

    Creates chunks of text aligned with video chunk boundaries so that
    speech embeddings can be compared alongside visual embeddings.

    Returns:
        List of dicts with: source_file, start_time, end_time, transcript.
    """
    if not segments:
        return []

    # Group by source file
    by_file: dict[str, list[dict]] = {}
    for seg in segments:
        by_file.setdefault(seg["source_file"], []).append(seg)

    result = []
    step = chunk_duration - overlap

    for source_file, file_segments in by_file.items():
        file_segments.sort(key=lambda s: s["start_time"])
        max_time = max(s["end_time"] for s in file_segments)

        start = 0.0
        while start < max_time:
            end = start + chunk_duration

            # Collect transcript text within this time window
            texts = []
            for seg in file_segments:
                if seg["start_time"] < end and seg["end_time"] > start:
                    texts.append(seg["text"])

            if texts:
                result.append({
                    "source_file": source_file,
                    "start_time": start,
                    "end_time": end,
                    "transcript": " ".join(texts),
                })

            start += step
            if start + overlap >= max_time:
                break

    return result
