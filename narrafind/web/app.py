"""Flask application for NarraFind Web UI."""

import os

from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    CORS(app)

    # Clips directory
    clips_dir = os.path.expanduser("~/narrafind_clips")
    os.makedirs(clips_dir, exist_ok=True)

    @app.route("/")
    def index_page():
        """Serve the main UI."""
        return render_template("index.html")

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
                    "error": "No indexed footage. Run `narrafind index <video>` first.",
                    "results": [],
                })

            embedder = get_embedder("gemini")
            results = search_footage(
                query, store, embedder,
                n_results=n_results,
                mode=mode,
            )

            # Format results for frontend
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
