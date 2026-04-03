"""Tests for the hybrid search module."""

from narrafind.search import _merge_results, _result_key, _time_overlaps


class TestTimeOverlaps:
    def test_overlapping(self):
        a = {"source_file": "/v.mp4", "start_time": 0, "end_time": 30}
        b = {"source_file": "/v.mp4", "start_time": 25, "end_time": 55}
        assert _time_overlaps(a, b) is True

    def test_non_overlapping(self):
        a = {"source_file": "/v.mp4", "start_time": 0, "end_time": 30}
        b = {"source_file": "/v.mp4", "start_time": 35, "end_time": 65}
        assert _time_overlaps(a, b) is False

    def test_different_files(self):
        a = {"source_file": "/a.mp4", "start_time": 0, "end_time": 30}
        b = {"source_file": "/b.mp4", "start_time": 0, "end_time": 30}
        assert _time_overlaps(a, b) is False


class TestMergeResults:
    def test_hybrid_boost(self):
        """Results appearing in both visual and speech should get boosted."""
        visual = [
            {"source_file": "/v.mp4", "start_time": 0, "end_time": 30,
             "score": 0.8, "transcript": ""},
        ]
        speech = [
            {"source_file": "/v.mp4", "start_time": 0, "end_time": 30,
             "score": 0.7, "transcript": "talking about vietnam"},
        ]

        results = _merge_results(visual, speech, visual_weight=0.5, speech_weight=0.5)
        assert len(results) == 1
        # Hybrid score = 0.5*0.8 + 0.5*0.7 = 0.75
        assert abs(results[0]["similarity_score"] - 0.75) < 0.01

    def test_visual_only(self):
        visual = [
            {"source_file": "/v.mp4", "start_time": 0, "end_time": 30,
             "score": 0.8, "transcript": ""},
        ]
        results = _merge_results(visual, [], n_results=5)
        assert len(results) == 1
        assert results[0]["search_type"] == "visual"

    def test_speech_only(self):
        speech = [
            {"source_file": "/v.mp4", "start_time": 0, "end_time": 30,
             "score": 0.7, "transcript": "hello"},
        ]
        results = _merge_results([], speech, n_results=5)
        assert len(results) == 1
        assert results[0]["search_type"] == "speech"

    def test_sorted_by_score(self):
        visual = [
            {"source_file": "/v.mp4", "start_time": 0, "end_time": 30,
             "score": 0.5, "transcript": ""},
            {"source_file": "/v.mp4", "start_time": 60, "end_time": 90,
             "score": 0.9, "transcript": ""},
        ]
        results = _merge_results(visual, [], n_results=5)
        assert results[0]["similarity_score"] >= results[1]["similarity_score"]
