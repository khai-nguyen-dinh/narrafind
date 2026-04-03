"""Tests for the transcriber module."""

from narrafind.transcriber import group_transcript_by_chunks


class TestGroupTranscriptByChunks:
    def test_groups_segments_into_chunks(self):
        segments = [
            {"source_file": "/v.mp4", "start_time": 2.0, "end_time": 5.0, "text": "hello"},
            {"source_file": "/v.mp4", "start_time": 8.0, "end_time": 12.0, "text": "world"},
            {"source_file": "/v.mp4", "start_time": 28.0, "end_time": 32.0, "text": "foo"},
        ]

        chunks = group_transcript_by_chunks(segments, chunk_duration=30, overlap=5)
        assert len(chunks) >= 1
        # First chunk should contain "hello" and "world"
        assert "hello" in chunks[0]["transcript"]
        assert "world" in chunks[0]["transcript"]
        assert chunks[0]["source_file"] == "/v.mp4"

    def test_empty_segments(self):
        assert group_transcript_by_chunks([]) == []

    def test_multiple_files(self):
        segments = [
            {"source_file": "/a.mp4", "start_time": 0.0, "end_time": 5.0, "text": "from a"},
            {"source_file": "/b.mp4", "start_time": 0.0, "end_time": 5.0, "text": "from b"},
        ]

        chunks = group_transcript_by_chunks(segments, chunk_duration=30, overlap=5)
        files = {c["source_file"] for c in chunks}
        assert "/a.mp4" in files
        assert "/b.mp4" in files
