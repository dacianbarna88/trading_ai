import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tae_mtime_indexed_cache as mic


class IterJsonlRowsTest(unittest.TestCase):
    def test_missing_file_yields_nothing(self) -> None:
        rows = list(mic.iter_jsonl_rows(Path("/nonexistent/does/not/exist.jsonl")))
        self.assertEqual(rows, [])

    def test_skips_blank_and_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "j.jsonl"
            path.write_text('{"a": 1}\n\nnot json\n{"a": 2}\n')
            rows = list(mic.iter_jsonl_rows(path))
            self.assertEqual(rows, [{"a": 1}, {"a": 2}])

    def test_skips_non_dict_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "j.jsonl"
            path.write_text('[1, 2]\n{"a": 1}\n')
            rows = list(mic.iter_jsonl_rows(path))
            self.assertEqual(rows, [{"a": 1}])


class GroupRowsByKeyTest(unittest.TestCase):
    def test_groups_preserving_order(self) -> None:
        rows = [
            {"ticker": "AAPL", "n": 1},
            {"ticker": "MSFT", "n": 2},
            {"ticker": "AAPL", "n": 3},
        ]
        grouped = mic.group_rows_by_key(rows, key_fn=lambda r: r["ticker"])
        self.assertEqual(grouped["AAPL"], [{"ticker": "AAPL", "n": 1}, {"ticker": "AAPL", "n": 3}])
        self.assertEqual(grouped["MSFT"], [{"ticker": "MSFT", "n": 2}])

    def test_skips_non_dict_and_empty_key(self) -> None:
        rows = ["not a dict", {"ticker": "", "n": 1}, {"ticker": "AAPL", "n": 2}]
        grouped = mic.group_rows_by_key(rows, key_fn=lambda r: r["ticker"])
        self.assertEqual(list(grouped.keys()), ["AAPL"])


class CachedMtimeIndexTest(unittest.TestCase):
    def test_missing_file_returns_empty_without_touching_cache(self) -> None:
        cache: dict = {"mtime": "sentinel", "index": {"x": 1}}
        build_index = mock.Mock()
        result = mic.cached_mtime_index(
            Path("/nonexistent/does/not/exist.jsonl"), cache=cache, build_index=build_index
        )
        self.assertEqual(result, {})
        build_index.assert_not_called()
        self.assertEqual(cache, {"mtime": "sentinel", "index": {"x": 1}})

    def test_builds_once_and_reuses_when_mtime_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "j.jsonl"
            path.write_text(json.dumps({"a": 1}) + "\n")
            cache: dict = {"mtime": None, "index": {}}
            build_index = mock.Mock(return_value={"a": 1})

            first = mic.cached_mtime_index(path, cache=cache, build_index=build_index)
            second = mic.cached_mtime_index(path, cache=cache, build_index=build_index)

            self.assertEqual(first, {"a": 1})
            self.assertEqual(second, {"a": 1})
            build_index.assert_called_once_with(path)

    def test_rebuilds_when_mtime_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "j.jsonl"
            path.write_text("v1\n")
            cache: dict = {"mtime": None, "index": {}}
            build_index = mock.Mock(side_effect=[{"v": 1}, {"v": 2}])

            mic.cached_mtime_index(path, cache=cache, build_index=build_index)
            time.sleep(0.01)
            path.write_text("v2\n")
            result = mic.cached_mtime_index(path, cache=cache, build_index=build_index)

            self.assertEqual(result, {"v": 2})
            self.assertEqual(build_index.call_count, 2)


if __name__ == "__main__":
    unittest.main()
