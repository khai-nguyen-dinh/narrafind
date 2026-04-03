"""Click-based CLI entry point for NarraFind."""

import os
import platform
import shutil
import subprocess

import click
from dotenv import load_dotenv

_ENV_PATH = os.path.join(os.path.expanduser("~"), ".narrafind", ".env")

load_dotenv(_ENV_PATH)
load_dotenv()


def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _open_file(path: str) -> None:
    """Open a file with the system's default application."""
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", path])
        elif system == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass


def _handle_error(e: Exception) -> None:
    """Print a user-friendly error and exit."""
    from .gemini_embedder import GeminiAPIKeyError, GeminiQuotaError

    if isinstance(e, GeminiAPIKeyError):
        click.secho("Error: " + str(e), fg="red", err=True)
        raise SystemExit(1)
    if isinstance(e, GeminiQuotaError):
        click.secho("Error: " + str(e), fg="yellow", err=True)
        raise SystemExit(1)
    if isinstance(e, PermissionError):
        click.secho("Error: " + str(e), fg="red", err=True)
        raise SystemExit(1)
    if isinstance(e, FileNotFoundError):
        click.secho("Error: " + str(e), fg="red", err=True)
        raise SystemExit(1)
    if isinstance(e, RuntimeError) and "ffmpeg not found" in str(e).lower():
        click.secho(
            "Error: ffmpeg is not available.\n\n"
            "Install it with one of:\n"
            "  Ubuntu/Debian:  sudo apt install ffmpeg\n"
            "  macOS:          brew install ffmpeg\n"
            "  pip fallback:   uv add imageio-ffmpeg",
            fg="red",
            err=True,
        )
        raise SystemExit(1)
    raise e


@click.group()
def cli():
    """NarraFind — search inside videos using natural language."""


# -----------------------------------------------------------------------
# init
# -----------------------------------------------------------------------

@cli.command()
def init():
    """Set up your Gemini API key for narrafind."""
    env_path = _ENV_PATH
    os.makedirs(os.path.dirname(env_path), exist_ok=True)

    if os.path.exists(env_path):
        with open(env_path) as f:
            contents = f.read()
        if "GEMINI_API_KEY=" in contents:
            if not click.confirm("API key already configured. Overwrite?", default=False):
                return

    api_key = click.prompt(
        "Enter your Gemini API key\n"
        "  Get one at https://aistudio.google.com/apikey\n"
        "  (input is hidden)",
        hide_input=True,
    )

    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
        with open(env_path, "w") as f:
            found = False
            for line in lines:
                if line.startswith("GEMINI_API_KEY="):
                    f.write(f"GEMINI_API_KEY={api_key}\n")
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f"GEMINI_API_KEY={api_key}\n")
    else:
        with open(env_path, "w") as f:
            f.write(f"GEMINI_API_KEY={api_key}\n")

    os.environ["GEMINI_API_KEY"] = api_key
    click.echo("Validating API key...")
    try:
        from .embedder import get_embedder
        embedder = get_embedder("gemini")
        vec = embedder.embed_query("test")
        if len(vec) != 768:
            click.secho(
                f"Unexpected embedding dimension: {len(vec)} (expected 768).",
                fg="yellow",
                err=True,
            )
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        click.secho(f"Validation failed: {e}", fg="red", err=True)
        raise SystemExit(1)

    click.secho(
        "Setup complete. You're ready to go — run "
        "`narrafind index <video>` to get started.",
        fg="green",
    )


# -----------------------------------------------------------------------
# index
# -----------------------------------------------------------------------

@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True))
@click.option("--chunk-duration", default=30, show_default=True,
              help="Chunk duration in seconds.")
@click.option("--overlap", default=5, show_default=True,
              help="Overlap between chunks in seconds.")
@click.option("--preprocess/--no-preprocess", default=True, show_default=True,
              help="Downscale and reduce frame rate before embedding.")
@click.option("--target-resolution", default=480, show_default=True,
              help="Target video height in pixels for preprocessing.")
@click.option("--target-fps", default=5, show_default=True,
              help="Target frames per second for preprocessing.")
@click.option("--skip-still/--no-skip-still", default=True, show_default=True,
              help="Skip chunks with no meaningful visual change.")
@click.option("--speech/--no-speech", default=True, show_default=True,
              help="Also index speech/transcript (requires Whisper).")
@click.option("--whisper-model", default="base", show_default=True,
              help="Whisper model size (tiny, base, small, medium, large).")
@click.option("--language", default=None,
              help="Language code for transcription (auto-detect if omitted).")
@click.option("--verbose", is_flag=True, help="Show debug info.")
def index(path, chunk_duration, overlap, preprocess, target_resolution,
          target_fps, skip_still, speech, whisper_model, language, verbose):
    """Index video files at PATH (file or directory) for searching."""
    from .chunker import (
        SUPPORTED_VIDEO_EXTENSIONS,
        chunk_video,
        is_still_frame_chunk,
        preprocess_chunk,
        scan_directory,
    )
    from .embedder import get_embedder, reset_embedder
    from .store import NarraStore

    try:
        embedder = get_embedder("gemini")
        store = NarraStore()

        if os.path.isfile(path):
            videos = [os.path.abspath(path)]
        else:
            videos = scan_directory(path)

        if not videos:
            supported = ", ".join(SUPPORTED_VIDEO_EXTENSIONS)
            click.echo(f"No supported video files found ({supported}).")
            return

        total_files = len(videos)
        new_chunks_visual = 0
        new_chunks_speech = 0
        skipped_chunks = 0

        for file_idx, video_path in enumerate(videos, 1):
            abs_path = os.path.abspath(video_path)
            basename = os.path.basename(video_path)

            if store.is_indexed(abs_path):
                click.echo(f"Skipping ({file_idx}/{total_files}): {basename} (already indexed)")
                continue

            click.secho(f"\n📹 Processing ({file_idx}/{total_files}): {basename}", fg="cyan")

            # --- Visual indexing ---
            chunks = chunk_video(abs_path, chunk_duration=chunk_duration, overlap=overlap)
            num_chunks = len(chunks)
            visual_embedded = []
            files_to_cleanup = []

            for chunk_idx, chunk in enumerate(chunks, 1):
                if skip_still and is_still_frame_chunk(
                    chunk["chunk_path"], verbose=verbose,
                ):
                    click.echo(f"  Skipping chunk {chunk_idx}/{num_chunks} (still frame)")
                    skipped_chunks += 1
                    files_to_cleanup.append(chunk["chunk_path"])
                    continue

                click.echo(
                    f"  🎬 Visual embedding [{chunk_idx}/{num_chunks}]"
                )

                embed_path = chunk["chunk_path"]
                if preprocess:
                    original_size = os.path.getsize(embed_path)
                    embed_path = preprocess_chunk(
                        embed_path,
                        target_resolution=target_resolution,
                        target_fps=target_fps,
                    )
                    if verbose and embed_path != chunk["chunk_path"]:
                        new_size = os.path.getsize(embed_path)
                        click.echo(
                            f"    [verbose] preprocess: {original_size / 1024:.0f}KB -> "
                            f"{new_size / 1024:.0f}KB "
                            f"({100 * (1 - new_size / original_size):.0f}% reduction)",
                            err=True,
                        )
                    if embed_path != chunk["chunk_path"]:
                        files_to_cleanup.append(embed_path)

                embedding = embedder.embed_video_chunk(embed_path, verbose=verbose)
                visual_embedded.append({**chunk, "embedding": embedding})
                files_to_cleanup.append(chunk["chunk_path"])

            # Clean up temp files
            for f in files_to_cleanup:
                try:
                    os.unlink(f)
                except OSError:
                    pass
            if chunks:
                tmp_dir = os.path.dirname(chunks[0]["chunk_path"])
                shutil.rmtree(tmp_dir, ignore_errors=True)

            if visual_embedded:
                store.add_visual_chunks(visual_embedded)
                new_chunks_visual += len(visual_embedded)

            # --- Speech indexing ---
            if speech:
                click.echo(f"  🎙️  Transcribing audio...")
                try:
                    from .transcriber import (
                        group_transcript_by_chunks,
                        transcribe_video_chunks,
                    )

                    transcript_segments = transcribe_video_chunks(
                        [{"source_file": abs_path, "start_time": c["start_time"],
                          "end_time": c["end_time"], "chunk_path": c.get("chunk_path", "")}
                         for c in chunks],
                        model_name=whisper_model,
                        language=language,
                        verbose=verbose,
                    )

                    if transcript_segments:
                        transcript_chunks = group_transcript_by_chunks(
                            transcript_segments,
                            chunk_duration=chunk_duration,
                            overlap=overlap,
                        )

                        speech_embedded = []
                        for tc_idx, tc in enumerate(transcript_chunks, 1):
                            click.echo(
                                f"  📝 Speech embedding [{tc_idx}/{len(transcript_chunks)}]"
                            )
                            text_embedding = embedder.embed_text(
                                tc["transcript"], verbose=verbose,
                            )
                            speech_embedded.append({
                                **tc,
                                "embedding": text_embedding,
                            })

                        if speech_embedded:
                            store.add_speech_chunks(speech_embedded)
                            new_chunks_speech += len(speech_embedded)
                    else:
                        click.echo("  (no speech detected)")
                except ImportError:
                    click.secho(
                        "  Whisper not installed — skipping speech indexing. "
                        "Install with: pip install openai-whisper",
                        fg="yellow", err=True,
                    )
                except Exception as e:
                    click.secho(f"  Speech indexing failed: {e}", fg="yellow", err=True)

        # Summary
        stats = store.get_stats()
        click.echo(f"\n{'='*50}")
        click.secho("✅ Indexing complete!", fg="green", bold=True)
        click.echo(f"  Visual chunks indexed: {new_chunks_visual}")
        click.echo(f"  Speech chunks indexed: {new_chunks_speech}")
        if skipped_chunks:
            click.echo(f"  Still frames skipped:  {skipped_chunks}")
        click.echo(f"  Total in database:     {stats['total_chunks']} chunks "
                    f"from {stats['unique_source_files']} files")

    except Exception as e:
        _handle_error(e)
    finally:
        reset_embedder()


# -----------------------------------------------------------------------
# search
# -----------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("-n", "--results", "n_results", default=5, show_default=True,
              help="Number of results to return.")
@click.option("-o", "--output-dir", default="~/narrafind_clips", show_default=True,
              help="Directory to save trimmed clips.")
@click.option("--trim/--no-trim", default=True, show_default=True,
              help="Auto-trim the top result.")
@click.option("--mode", type=click.Choice(["hybrid", "visual", "speech"]),
              default="hybrid", show_default=True,
              help="Search mode.")
@click.option("--threshold", default=0.35, show_default=True, type=float,
              help="Minimum similarity score for confident match.")
@click.option("--verbose", is_flag=True, help="Show debug info.")
def search(query, n_results, output_dir, trim, mode, threshold, verbose):
    """Search indexed footage with a natural language QUERY."""
    from .embedder import get_embedder, reset_embedder
    from .search import search_footage
    from .store import NarraStore

    output_dir = os.path.expanduser(output_dir)

    try:
        store = NarraStore()
        stats = store.get_stats()

        if stats["total_chunks"] == 0:
            click.echo(
                "No indexed footage found. "
                "Run `narrafind index <video>` first."
            )
            return

        embedder = get_embedder("gemini")

        results = search_footage(
            query, store, embedder,
            n_results=n_results,
            mode=mode,
            verbose=verbose,
        )

        if not results:
            click.echo("No results found.")
            return

        best_score = results[0]["similarity_score"]
        low_confidence = best_score < threshold

        if low_confidence and not trim:
            click.secho(
                f"(low confidence — best score: {best_score:.2f})",
                fg="yellow", err=True,
            )

        click.echo()
        for i, r in enumerate(results, 1):
            basename = os.path.basename(r["source_file"])
            start_str = _fmt_time(r["start_time"])
            end_str = _fmt_time(r["end_time"])
            score = r["similarity_score"]
            stype = r.get("search_type", "")
            type_badge = f" [{stype}]" if stype else ""

            if verbose:
                click.echo(
                    f"  #{i} [{score:.6f}]{type_badge} {basename} "
                    f"@ {start_str}-{end_str}"
                )
            else:
                click.echo(
                    f"  #{i} [{score:.2f}]{type_badge} {basename} "
                    f"@ {start_str}-{end_str}"
                )
            if r.get("transcript"):
                truncated = r["transcript"][:120]
                if len(r["transcript"]) > 120:
                    truncated += "..."
                click.echo(f"      💬 \"{truncated}\"")

        if trim:
            if low_confidence:
                if not click.confirm(
                    f"\nNo confident match found (best score: {best_score:.2f}). "
                    "Trim top result anyway?",
                    default=False,
                ):
                    return

            from .trimmer import trim_top_results
            clip_paths = trim_top_results(results, output_dir, count=1)

            for clip_path in clip_paths:
                click.echo(f"\n🎬 Saved clip: {clip_path}")

            if clip_paths:
                _open_file(clip_paths[0])

    except Exception as e:
        _handle_error(e)
    finally:
        reset_embedder()


# -----------------------------------------------------------------------
# stats
# -----------------------------------------------------------------------

@cli.command()
def stats():
    """Print index statistics."""
    from .store import NarraStore

    store = NarraStore()
    s = store.get_stats()

    if s["total_chunks"] == 0:
        click.echo("Index is empty. Run `narrafind index <video>` first.")
        return

    click.echo(f"Total chunks:   {s['total_chunks']}")
    click.echo(f"  Visual:       {s['visual_chunks']}")
    click.echo(f"  Speech:       {s['speech_chunks']}")
    click.echo(f"Source files:   {s['unique_source_files']}")
    click.echo("\nIndexed files:")
    for f in s["source_files"]:
        exists = os.path.exists(f)
        label = "" if exists else "  [missing]"
        click.echo(f"  {f}{label}")


# -----------------------------------------------------------------------
# reset
# -----------------------------------------------------------------------

@cli.command()
@click.confirmation_option(prompt="This will delete all indexed data. Continue?")
def reset():
    """Delete all indexed data."""
    from .store import NarraStore

    store = NarraStore()
    s = store.get_stats()

    if s["total_chunks"] == 0:
        click.echo("Index is already empty.")
        return

    store.reset()
    click.echo(
        f"Removed {s['total_chunks']} chunks "
        f"({s['visual_chunks']} visual, {s['speech_chunks']} speech) "
        f"from {s['unique_source_files']} files."
    )


# -----------------------------------------------------------------------
# remove
# -----------------------------------------------------------------------

@cli.command()
@click.argument("files", nargs=-1, required=True)
def remove(files):
    """Remove specific files from the index."""
    from .store import NarraStore

    store = NarraStore()
    s = store.get_stats()

    if s["total_chunks"] == 0:
        click.echo("Index is empty.")
        return

    total_removed = 0
    for pattern in files:
        matches = [f for f in s["source_files"] if pattern in f]
        if not matches:
            click.echo(f"No indexed files matching '{pattern}'")
            continue
        for source_file in matches:
            removed = store.remove_file(source_file)
            click.echo(f"Removed {removed} chunks from {source_file}")
            total_removed += removed

    if total_removed:
        click.echo(f"\nTotal: removed {total_removed} chunks.")


# -----------------------------------------------------------------------
# serve (Web UI)
# -----------------------------------------------------------------------

@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True,
              help="Host to bind to.")
@click.option("--port", default=5000, show_default=True,
              help="Port to bind to.")
@click.option("--debug", is_flag=True, help="Enable debug mode.")
def serve(host, port, debug):
    """Start the web UI for searching and browsing indexed footage."""
    from .web.app import create_app

    app = create_app()
    click.secho(f"\n🌐 NarraFind Web UI: http://{host}:{port}\n", fg="green", bold=True)
    app.run(host=host, port=port, debug=debug)
