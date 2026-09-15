import io
import time
import unittest
from contextlib import redirect_stdout

import tae_slow_call_guard as guard


class WarnIfSlowTest(unittest.TestCase):
    def test_fires_when_block_exceeds_threshold(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            with guard.warn_if_slow("thing ticker=AAPL phase=entry", threshold_sec=0.01):
                time.sleep(0.05)
        output = buf.getvalue()
        self.assertIn("thing ticker=AAPL phase=entry", output)
        self.assertIn("elapsed=", output)

    def test_silent_when_block_is_fast(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            with guard.warn_if_slow("thing", threshold_sec=5.0):
                pass
        self.assertEqual(buf.getvalue(), "")

    def test_exception_inside_block_propagates_and_is_not_swallowed(self) -> None:
        with self.assertRaises(ValueError):
            with guard.warn_if_slow("thing", threshold_sec=999.0):
                raise ValueError("boom")

    def test_caught_exception_inside_block_still_times_and_can_continue(self) -> None:
        buf = io.StringIO()
        results = []
        with redirect_stdout(buf):
            for item in ("a", "b"):
                with guard.warn_if_slow(f"thing item={item}", threshold_sec=0.01):
                    try:
                        if item == "a":
                            time.sleep(0.05)
                            raise RuntimeError("boom")
                        results.append(item)
                    except RuntimeError:
                        continue
        self.assertEqual(results, ["b"])
        self.assertIn("item=a", buf.getvalue())
        self.assertNotIn("item=b elapsed", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
