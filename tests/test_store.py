"""Tests for the NarraStore module."""

import tempfile
from pathlib import Path

import pytest

from narrafind.store import NarraStore


@pytest.fixture
def store(tmp_dir):
    """Create a NarraStore backed by a temporary directory."""
    return NarraStore(db_path=tmp_dir)


class TestNarraStoreVisual:
    def test_add_and_search_visual(self, store):
        chunks = [
            {
                "source_file": "/videos/test.mp4",
                "start_time": 0.0,
                "end_time": 30.0,
                "embedding": [1.0] * 768,
            },
            {
                "source_file": "/videos/test.mp4",
                "start_time": 25.0,
                "end_time": 55.0,
                "embedding": [0.5] * 768,
            },
        ]
        store.add_visual_chunks(chunks)

        results = store.search_visual([1.0] * 768, n_results=5)
        assert len(results) == 2
        assert results[0]["source_file"] == "/videos/test.mp4"
        assert results[0]["score"] >= results[1]["score"]

    def test_empty_search(self, store):
        results = store.search_visual([1.0] * 768)
        assert results == []


class TestNarraStoreSpeech:
    def test_add_and_search_speech(self, store):
        chunks = [
            {
                "source_file": "/videos/test.mp4",
                "start_time": 0.0,
                "end_time": 30.0,
                "embedding": [1.0] * 768,
                "transcript": "talking about vietnam",
            },
        ]
        store.add_speech_chunks(chunks)

        results = store.search_speech([1.0] * 768, n_results=5)
        assert len(results) == 1
        assert results[0]["transcript"] == "talking about vietnam"


class TestNarraStoreManagement:
    def test_is_indexed(self, store):
        assert store.is_indexed("/videos/test.mp4") is False

        store.add_visual_chunks([{
            "source_file": "/videos/test.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [1.0] * 768,
        }])
        assert store.is_indexed("/videos/test.mp4") is True

    def test_remove_file(self, store):
        store.add_visual_chunks([{
            "source_file": "/videos/test.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [1.0] * 768,
        }])
        store.add_speech_chunks([{
            "source_file": "/videos/test.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [0.5] * 768,
            "transcript": "hello world",
        }])

        removed = store.remove_file("/videos/test.mp4")
        assert removed == 2
        assert store.is_indexed("/videos/test.mp4") is False

    def test_get_stats(self, store):
        stats = store.get_stats()
        assert stats["total_chunks"] == 0
        assert stats["visual_chunks"] == 0
        assert stats["speech_chunks"] == 0

        store.add_visual_chunks([{
            "source_file": "/videos/a.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [1.0] * 768,
        }])
        store.add_speech_chunks([{
            "source_file": "/videos/b.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [0.5] * 768,
            "transcript": "test",
        }])

        stats = store.get_stats()
        assert stats["total_chunks"] == 2
        assert stats["visual_chunks"] == 1
        assert stats["speech_chunks"] == 1
        assert stats["unique_source_files"] == 2

    def test_reset(self, store):
        store.add_visual_chunks([{
            "source_file": "/videos/test.mp4",
            "start_time": 0.0,
            "end_time": 30.0,
            "embedding": [1.0] * 768,
        }])

        store.reset()
        stats = store.get_stats()
        assert stats["total_chunks"] == 0
