"""Tests for the video chunker module."""

import os
import shutil

import pytest

from narrafind.chunker import (
    SUPPORTED_VIDEO_EXTENSIONS,
    chunk_video,
    extract_audio,
    get_video_duration,
    is_supported_video_file,
    scan_directory,
)


class TestIsSupportedVideoFile:
    def test_mp4(self):
        assert is_supported_video_file("video.mp4") is True

    def test_mov(self):
        assert is_supported_video_file("video.MOV") is True

    def test_mkv(self):
        assert is_supported_video_file("video.mkv") is True

    def test_unsupported(self):
        assert is_supported_video_file("file.txt") is False

    def test_no_extension(self):
        assert is_supported_video_file("video") is False


class TestGetVideoDuration:
    def test_returns_duration(self, sample_video):
        duration = get_video_duration(sample_video)
        assert 1.5 <= duration <= 2.5

    def test_file_not_found(self):
        with pytest.raises((FileNotFoundError, RuntimeError, Exception)):
            get_video_duration("/nonexistent/video.mp4")


class TestChunkVideo:
    def test_short_video_single_chunk(self, sample_video):
        """A 2s video with 30s chunk duration should produce 1 chunk."""
        chunks = chunk_video(sample_video, chunk_duration=30, overlap=5)
        assert len(chunks) == 1
        assert chunks[0]["source_file"] == os.path.realpath(sample_video)
        assert chunks[0]["start_time"] == 0.0
        assert os.path.isfile(chunks[0]["chunk_path"])

        # Clean up
        shutil.rmtree(os.path.dirname(chunks[0]["chunk_path"]), ignore_errors=True)

    def test_long_video_multiple_chunks(self, long_video):
        """A 10s video with 5s chunks and 1s overlap should produce multiple chunks."""
        chunks = chunk_video(long_video, chunk_duration=5, overlap=1)
        assert len(chunks) >= 2

        for chunk in chunks:
            assert os.path.isfile(chunk["chunk_path"])
            assert chunk["source_file"] == os.path.realpath(long_video)

        # Clean up
        shutil.rmtree(os.path.dirname(chunks[0]["chunk_path"]), ignore_errors=True)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            chunk_video("/nonexistent/video.mp4")


class TestExtractAudio:
    def test_extracts_wav(self, sample_video):
        wav_path = extract_audio(sample_video)
        assert os.path.isfile(wav_path)
        assert wav_path.endswith(".wav")
        assert os.path.getsize(wav_path) > 0
        os.unlink(wav_path)


class TestScanDirectory:
    def test_finds_videos(self, tmp_dir):
        # Create fake video files
        for name in ["a.mp4", "b.mov", "c.mkv", "d.txt", "e.jpg"]:
            open(os.path.join(tmp_dir, name), "w").close()

        videos = scan_directory(tmp_dir)
        basenames = [os.path.basename(v) for v in videos]
        assert "a.mp4" in basenames
        assert "b.mov" in basenames
        assert "c.mkv" in basenames
        assert "d.txt" not in basenames
        assert "e.jpg" not in basenames

    def test_empty_directory(self, tmp_dir):
        assert scan_directory(tmp_dir) == []
