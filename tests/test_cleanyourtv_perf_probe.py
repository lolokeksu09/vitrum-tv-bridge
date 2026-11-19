"""Behavior and privacy tests for bounded CleanYourTV frame measurement."""
import unittest
from unittest import mock

from scripts import cleanyourtv_perf_probe as perf


def framestats(durations, *, invalid_rows=()):
    header = "Flags,IntendedVsync,FrameCompleted"
    rows = ["0,1000000000," + str(1000000000 + int(ms * 1000000))
            for ms in durations]
    rows.extend(invalid_rows)
    return ("Android gfxinfo\n" + perf.MARKER + "\n" + header + "\n"
            + "\n".join(rows) + "\n" + perf.MARKER)


class GfxinfoTests(unittest.TestCase):
    def test_completed_frames_are_parsed_and_aggregated(self):
        raw = framestats(range(10, 20), invalid_rows=(
            "1,1000000000,2000000000",  # flagged/dropped record
            "0,0,2000000000",  # invalid intended vsync
            "0,2000000000,1000000000",  # out-of-order
            "not,a,frame",
        ))
        durations = perf.parse_framestats(raw)
        self.assertEqual(durations, [float(i) for i in range(10, 20)])
        self.assertEqual(perf.summarize(durations),
                         "PERF_V1 frames=10 p50_ms=14.0 p95_ms=19.0 slow16_pct=30.0")

    def test_missing_and_insufficient_frames_are_not_reported_as_success(self):
        with self.assertRaisesRegex(perf.FrameProbeError, "did not provide"):
            perf.parse_framestats("No profile data")
        with self.assertRaisesRegex(perf.FrameProbeError, "Too few"):
            perf.summarize([15.0] * 3)

    def test_summary_cannot_include_paths_or_extra_payload(self):
        aggregate = perf.summarize([11.0] * 10)
        self.assertIsNotNone(perf.PUBLIC_SUMMARY.fullmatch(aggregate))
        self.assertIsNone(perf.PUBLIC_SUMMARY.fullmatch(
            aggregate + "\n/device/secret"))
        self.assertIsNone(perf.PUBLIC_SUMMARY.fullmatch(
            aggregate.replace("11.0", "11x0")))

    def test_refuses_input_when_home_is_not_foreground(self):
        guard = mock.Mock()
        adb = mock.Mock()
        focus = mock.Mock(return_value=False)
        with self.assertRaisesRegex(perf.FrameProbeError, "foreground"):
            perf.measure(adb, guard, focus, pause=lambda _: None)
        guard.assert_called_once()
        adb.assert_not_called()

    def test_exits_after_foreground_changes_before_second_key(self):
        guard = mock.Mock()
        adb = mock.Mock(return_value="")
        focus = mock.Mock(side_effect=[True, True, False])
        with self.assertRaisesRegex(perf.FrameProbeError, "Foreground changed"):
            perf.measure(adb, guard, focus, pause=lambda _: None)
        moves = [c.args for c in adb.call_args_list
                 if c.args[:3] == ("shell", "input", "keyevent")]
        self.assertEqual(moves, [("shell", "input", "keyevent", "22")])

    def test_probe_only_resets_stats_and_moves_focus_right_left(self):
        raw = framestats([12.0, 13.0, 14.0, 15.0, 16.0,
                          17.0, 18.0, 19.0, 20.0, 21.0])
        guard = mock.Mock()
        focus = mock.Mock(return_value=True)

        def adb(*args, **kwargs):
            if args == ("shell", "dumpsys", "gfxinfo", perf.PKG, "framestats"):
                return raw
            return ""

        calls = []
        def observed(*args, **kwargs):
            calls.append(args)
            return adb(*args, **kwargs)

        result = perf.measure(observed, guard, focus, pause=lambda _: None)
        self.assertEqual(result,
                         "PERF_V1 frames=10 p50_ms=16.0 p95_ms=21.0 slow16_pct=50.0")
        guard.assert_called_once()
        self.assertEqual(calls[0],
                         ("shell", "dumpsys", "gfxinfo", perf.PKG, "reset"))
        self.assertEqual(calls[-1],
                         ("shell", "dumpsys", "gfxinfo", perf.PKG, "framestats"))
        moves = [c for c in calls if c[:3] == ("shell", "input", "keyevent")]
        self.assertEqual(moves, [
            ("shell", "input", "keyevent", key)
            for _ in range(6) for key in ("22", "21")
        ])
        self.assertFalse(any("monkey" in c or "am" in c or "screencap" in c
                             for c in calls))


if __name__ == "__main__":
    unittest.main()
