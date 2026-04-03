"""Trim clips from source video files."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _get_ffmpeg_executable() -> str:
    """Return a usable ffmpeg executable path."""
    from .chunker import _get_ffmpeg_executable as _get_ffmpeg
    return _get_ffmpeg()


def _fmt_time_filename(seconds: float) -> str:
    """Format seconds as XmYs for filenames."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}m{s:02d}s"


def trim_clip(
    source_file: str,
    start_time: float,
    end_time: float,
    output_dir: str,
) -> str:
    """Trim a segment from a source video and save to output_dir.

    Returns:
        Path to the saved clip.
    """
    ffmpeg_exe = _get_ffmpeg_executable()
    os.makedirs(output_dir, exist_ok=True)

    basename = Path(source_file).stem
    start_str = _fmt_time_filename(start_time)
    end_str = _fmt_time_filename(end_time)
    clip_name = f"match_{basename}_{start_str}-{end_str}.mp4"
    clip_path = os.path.join(output_dir, clip_name)

    duration = end_time - start_time
    subprocess.run(
        [ffmpeg_exe, "-y",
         "-ss", str(start_time),
         "-i", source_file,
         "-t", str(duration),
         "-c", "copy",
         clip_path],
        capture_output=True,
        check=True,
    )

    return clip_path


def trim_top_results(
    results: list[dict],
    output_dir: str,
    count: int = 1,
) -> list[str]:
    """Trim and save clips for the top N results.

    Returns:
        List of saved clip paths.
    """
    clips = []
    for r in results[:count]:
        if not os.path.isfile(r["source_file"]):
            continue
        clip = trim_clip(
            r["source_file"],
            r["start_time"],
            r["end_time"],
            output_dir,
        )
        clips.append(clip)
    return clips
