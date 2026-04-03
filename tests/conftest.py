"""Shared test fixtures."""

import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    d = tempfile.mkdtemp(prefix="narrafind_test_")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_video(tmp_dir):
    """Create a minimal test video using ffmpeg.

    Returns the path to a ~2-second silent video.
    """
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available")

    video_path = os.path.join(tmp_dir, "test_video.mp4")
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "2",
            "-c:v", "libx264", "-crf", "28",
            "-c:a", "aac",
            video_path,
        ],
        capture_output=True,
        check=True,
    )
    return video_path


@pytest.fixture
def long_video(tmp_dir):
    """Create a longer test video (~10 seconds) for chunking tests."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available")

    video_path = os.path.join(tmp_dir, "long_video.mp4")
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc=s=320x240:d=10",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "10",
            "-c:v", "libx264", "-crf", "28",
            "-c:a", "aac",
            video_path,
        ],
        capture_output=True,
        check=True,
    )
    return video_path
