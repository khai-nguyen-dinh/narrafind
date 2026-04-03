"""Flask application for NarraFind Web UI."""

import os
import shutil
import threading
import uuid
from datetime import datetime

from flask import Flask, Response, jsonify, render_template, request, send_file
from flask_cors import CORS


# ---------------------------------------------------------------------------
# Indexing job tracker
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _create_job() -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "progress": 0,
            "total": 0,
            "current_file": "",
            "current_step": "",
            "logs": [],
            "error": None,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "visual_chunks": 0,
            "speech_chunks": 0,
            "skipped_files": 0,
        }
    return job_id


def _update_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _log_job(job_id: str, message: str) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["logs"].append(message)


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id, {}).copy() if job_id in _jobs else None


# ---------------------------------------------------------------------------
# Background indexing worker
# ---------------------------------------------------------------------------

def _download_url_if_needed(uri: str, job_id: str) -> str:
    """Download a YouTube/Web URL via yt-dlp if it's a valid link."""
    if not (uri.startswith("http://") or uri.startswith("https://")):
        return uri
    try:
        import yt_dlp
        uploads_dir = os.path.expanduser("~/.narrafind/uploads")
        ydl_opts = {
            'outtmpl': os.path.join(uploads_dir, '%(title)s_%(id)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        _log_job(job_id, f"📥 Downloading video from URL -> yt-dlp...")
        _update_job(job_id, current_step="Downloading URL...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(uri, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            return filename
    except ImportError:
        _log_job(job_id, f"❌ yt-dlp is not installed. Run: uv add yt-dlp")
        return uri
    except Exception as e:
        _log_job(job_id, f"❌ Failed to download {uri}: {e}")
        return uri

def _index_worker(
    job_id: str,
    video_paths: list[str],
    chunk_duration: int = 30,
    overlap: int = 5,
    speech: bool = True,
    whisper_model: str = "base",
) -> None:
    """Run indexing in the background, updating job progress."""
    from ..chunker import (
        chunk_video,
        is_still_frame_chunk,
        preprocess_chunk,
    )
    from ..embedder import get_embedder, reset_embedder
    from ..store import NarraStore

    try:
        _update_job(job_id, status="running", total=len(video_paths))
        embedder = get_embedder("gemini")
        store = NarraStore()

        total_visual = 0
        total_speech = 0
        skipped = 0

        for file_idx, video_path in enumerate(video_paths):
            _update_job(
                job_id,
                progress=file_idx,
                current_file=video_path,
                current_step="Validating...",
            )

            real_path = _download_url_if_needed(video_path, job_id)
            if not os.path.exists(real_path):
                _log_job(job_id, f"❌ File not found or download failed: {real_path}")
                skipped += 1
                continue

            abs_path = os.path.abspath(real_path)
            basename = os.path.basename(real_path)

            _update_job(job_id, current_file=basename, current_step="Checking...")

            if store.is_indexed(abs_path):
                _log_job(job_id, f"⏭️ Skipped (already indexed): {basename}")
                skipped += 1
                continue

            # --- Visual indexing ---
            _update_job(job_id, current_step="Chunking video...")
            _log_job(job_id, f"📹 Processing: {basename}")

            try:
                chunks = chunk_video(abs_path, chunk_duration=chunk_duration, overlap=overlap)
            except Exception as e:
                _log_job(job_id, f"❌ Failed to chunk {basename}: {e}")
                continue

            num_chunks = len(chunks)
            visual_embedded = []
            files_to_cleanup = []

            for chunk_idx, chunk in enumerate(chunks, 1):
                _update_job(
                    job_id,
                    current_step=f"Visual embedding [{chunk_idx}/{num_chunks}]",
                )

                if is_still_frame_chunk(chunk["chunk_path"]):
                    _log_job(job_id, f"  ⏭️ Chunk {chunk_idx}/{num_chunks} (still frame)")
                    files_to_cleanup.append(chunk["chunk_path"])
                    continue

                embed_path = chunk["chunk_path"]
                preprocessed = preprocess_chunk(embed_path)
                if preprocessed != embed_path:
                    files_to_cleanup.append(preprocessed)

                try:
                    embedding = embedder.embed_video_chunk(preprocessed)
                    visual_embedded.append({**chunk, "embedding": embedding})
                except Exception as e:
                    _log_job(job_id, f"  ⚠️ Embed failed chunk {chunk_idx}: {e}")

                files_to_cleanup.append(chunk["chunk_path"])

            # Cleanup temp files
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
                total_visual += len(visual_embedded)
                _log_job(job_id, f"  🎬 {len(visual_embedded)} visual chunks indexed")

            # --- Speech indexing ---
            if speech:
                _update_job(job_id, current_step="Transcribing audio...")
                try:
                    from ..transcriber import (
                        group_transcript_by_chunks,
                        transcribe_video_chunks,
                    )

                    transcript_segments = transcribe_video_chunks(
                        [{"source_file": abs_path, "start_time": c["start_time"],
                          "end_time": c["end_time"], "chunk_path": ""}
                         for c in chunks],
                        model_name=whisper_model,
                    )

                    if transcript_segments:
                        transcript_chunks = group_transcript_by_chunks(
                            transcript_segments,
                            chunk_duration=chunk_duration,
                            overlap=overlap,
                        )

                        speech_embedded = []
                        for tc_idx, tc in enumerate(transcript_chunks, 1):
                            _update_job(
                                job_id,
                                current_step=f"Speech embedding [{tc_idx}/{len(transcript_chunks)}]",
                            )
                            text_embedding = embedder.embed_text(tc["transcript"])
                            speech_embedded.append({**tc, "embedding": text_embedding})

                        if speech_embedded:
                            store.add_speech_chunks(speech_embedded)
                            total_speech += len(speech_embedded)
                            _log_job(job_id, f"  🎙️ {len(speech_embedded)} speech chunks indexed")
                    else:
                        _log_job(job_id, "  🔇 No speech detected")
                except ImportError:
                    _log_job(job_id, "  ⚠️ Whisper not installed, skipping speech")
                except Exception as e:
                    _log_job(job_id, f"  ⚠️ Speech indexing failed: {e}")

        _update_job(
            job_id,
            status="done",
            progress=len(video_paths),
            current_step="Complete",
            current_file="",
            visual_chunks=total_visual,
            speech_chunks=total_speech,
            skipped_files=skipped,
            finished_at=datetime.utcnow().isoformat(),
        )
        _log_job(
            job_id,
            f"✅ Done! {total_visual} visual + {total_speech} speech chunks indexed.",
        )

    except Exception as e:
        _update_job(job_id, status="error", error=str(e))
        _log_job(job_id, f"❌ Fatal error: {e}")
    finally:
        reset_embedder()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10 GB
    CORS(app)

    clips_dir = os.path.expanduser("~/narrafind_clips")
    uploads_dir = os.path.expanduser("~/.narrafind/uploads")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(uploads_dir, exist_ok=True)

    @app.route("/")
    def index_page():
        """Serve the main UI."""
        return render_template("index.html")

    # -------------------------------------------------------------------
    # Index API
    # -------------------------------------------------------------------

    @app.route("/api/index/path", methods=["POST"])
    def api_index_path():
        """Start indexing from a local path (file or directory)."""
        from ..chunker import SUPPORTED_VIDEO_EXTENSIONS, is_supported_video_file, scan_directory

        data = request.get_json()
        path = data.get("path", "").strip()
        speech = data.get("speech", True)
        whisper_model = data.get("whisper_model", "base")
        chunk_duration = data.get("chunk_duration", 30)
        overlap = data.get("overlap", 5)

        if not path:
            return jsonify({"error": "Path is required"}), 400

        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return jsonify({"error": f"Path not found: {path}"}), 404

        if os.path.isfile(path):
            if not is_supported_video_file(path):
                return jsonify({"error": f"Unsupported file format"}), 400
            video_paths = [path]
        else:
            video_paths = scan_directory(path)

        if not video_paths:
            supported = ", ".join(SUPPORTED_VIDEO_EXTENSIONS)
            return jsonify({"error": f"No video files found ({supported})"}), 404

        job_id = _create_job()
        thread = threading.Thread(
            target=_index_worker,
            args=(job_id, video_paths),
            kwargs={
                "chunk_duration": chunk_duration,
                "overlap": overlap,
                "speech": speech,
                "whisper_model": whisper_model,
            },
            daemon=True,
        )
        thread.start()

        return jsonify({
            "job_id": job_id,
            "files_found": len(video_paths),
            "filenames": [os.path.basename(p) for p in video_paths],
        })

    @app.route("/api/index/upload", methods=["POST"])
    def api_index_upload():
        """Upload video files and start indexing."""
        from ..chunker import is_supported_video_file

        files = request.files.getlist("videos")
        if not files:
            return jsonify({"error": "No files uploaded"}), 400

        speech = request.form.get("speech", "true").lower() == "true"
        whisper_model = request.form.get("whisper_model", "base")

        # Save uploaded files
        video_paths = []
        for f in files:
            if not f.filename:
                continue
            if not is_supported_video_file(f.filename):
                continue
            save_path = os.path.join(uploads_dir, f.filename)
            f.save(save_path)
            video_paths.append(save_path)

        if not video_paths:
            return jsonify({"error": "No supported video files in upload"}), 400

        job_id = _create_job()
        thread = threading.Thread(
            target=_index_worker,
            args=(job_id, video_paths),
            kwargs={"speech": speech, "whisper_model": whisper_model},
            daemon=True,
        )
        thread.start()

        return jsonify({
            "job_id": job_id,
            "files_found": len(video_paths),
            "filenames": [os.path.basename(p) for p in video_paths],
        })

    @app.route("/api/index/status/<job_id>")
    def api_index_status(job_id):
        """Get indexing job status."""
        job = _get_job(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)

    @app.route("/api/index", methods=["DELETE"])
    def api_index_remove():
        """Remove a specific file from the index."""
        from ..store import NarraStore

        data = request.get_json()
        source_file = data.get("source_file")
        if not source_file:
            return jsonify({"error": "source_file is required"}), 400

        try:
            store = NarraStore()
            removed_count = store.remove_file(source_file)
            return jsonify({"success": True, "removed_chunks": removed_count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # -------------------------------------------------------------------
    # Search API
    # -------------------------------------------------------------------

    @app.route("/api/search", methods=["POST"])
    def api_search():
        """Search indexed footage."""
        from ..embedder import get_embedder, reset_embedder
        from ..search import search_footage
        from ..store import NarraStore

        data = request.get_json()
        query = data.get("query", "").strip()
        mode = data.get("mode", "hybrid")
        n_results = data.get("n_results", 10)

        if not query:
            return jsonify({"error": "Query is required"}), 400

        try:
            store = NarraStore()
            stats = store.get_stats()

            if stats["total_chunks"] == 0:
                return jsonify({
                    "error": "No indexed footage. Use the Index tab to add videos first.",
                    "results": [],
                })

            embedder = get_embedder("gemini")
            results = search_footage(
                query, store, embedder,
                n_results=n_results,
                mode=mode,
            )

            formatted = []
            for r in results:
                formatted.append({
                    "source_file": r["source_file"],
                    "filename": os.path.basename(r["source_file"]),
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "score": round(r["similarity_score"], 4),
                    "transcript": r.get("transcript", ""),
                    "search_type": r.get("search_type", ""),
                    "start_formatted": _fmt_time(r["start_time"]),
                    "end_formatted": _fmt_time(r["end_time"]),
                })

            return jsonify({"results": formatted, "query": query, "mode": mode})

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            reset_embedder()

    # -------------------------------------------------------------------
    # Trim / Clip / Video / Stats
    # -------------------------------------------------------------------

    @app.route("/api/trim", methods=["POST"])
    def api_trim():
        """Trim a clip from a search result."""
        from ..trimmer import trim_clip

        data = request.get_json()
        source_file = data.get("source_file")
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        if not all([source_file, start_time is not None, end_time is not None]):
            return jsonify({"error": "Missing required fields"}), 400

        try:
            clip_path = trim_clip(source_file, start_time, end_time, clips_dir)
            return jsonify({
                "clip_path": clip_path,
                "clip_url": f"/api/clips/{os.path.basename(clip_path)}",
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/clips/<filename>")
    def serve_clip(filename):
        """Serve a trimmed clip file."""
        clip_path = os.path.join(clips_dir, filename)
        if not os.path.isfile(clip_path):
            return jsonify({"error": "Clip not found"}), 404
        return send_file(clip_path, mimetype="video/mp4")

    @app.route("/api/stats")
    def api_stats():
        """Return index statistics."""
        from ..store import NarraStore

        store = NarraStore()
        stats = store.get_stats()
        return jsonify(stats)

    @app.route("/api/video")
    def serve_video():
        """Serve a source video file for in-browser playback."""
        filepath = request.args.get("path")
        if not filepath or not os.path.isfile(filepath):
            return jsonify({"error": "File not found"}), 404
        return send_file(filepath, mimetype="video/mp4")

    return app


def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"
