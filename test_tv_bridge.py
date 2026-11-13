import importlib.util
import unittest
from unittest import mock
from pathlib import Path

path = Path(__file__).with_name("tv_bridge.py")
spec = importlib.util.spec_from_file_location("tv_bridge", path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def issue(op, login="lolokeksu09", title=None, body=None):
    return {
        "number": 123,
        "author": {"login": login},
        "title": title if title is not None else "TVBRIDGE/v1 " + op,
        "body": body if body is not None else '{"v":1,"op":"' + op + '"}',
    }


class RequestValidation(unittest.TestCase):
    def test_allowed(self):
        for op in bridge.OPERATIONS:
            self.assertEqual((123, op), bridge.parse_issue(issue(op)))

    def test_arbitrary_shell_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue("shell")))

    def test_other_author_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue("device_summary", login="other")))

    def test_title_mismatch_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue("device_summary", title="anything")))

    def test_extra_arguments_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue(
            "device_summary", body='{"v":1,"op":"device_summary","args":["rm","-rf"]}'
        )))

    def test_malformed_json_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue("device_summary", body="{")))

    def test_boolean_version_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue(
            "device_summary", body='{"v":true,"op":"device_summary"}'
        )))

    def test_oversized_body_disallowed(self):
        self.assertIsNone(bridge.parse_issue(issue("device_summary", body="x" * 151)))


class FocusStatusTests(unittest.TestCase):
    @mock.patch.object(bridge, "adb")
    def test_window_focus_is_preferred(self, adb):
        adb.return_value = ("mCurrentFocus=Window{1 u0 dev.monolith.tv.preview}", 0)
        result = bridge.perform("test-device", "focus_status")
        self.assertIn("dev.monolith.tv.preview", result)
        adb.assert_called_once_with("test-device", "dumpsys", "window")

    @mock.patch.object(bridge, "adb")
    def test_activity_fallback_when_tv_firmware_omits_window_focus(self, adb):
        adb.side_effect = [
            ("Window service returned no focus details", 0),
            ("topResumedActivity=ActivityRecord{0 u0 dev.monolith.tv.preview/.MainActivity}", 0),
        ]
        result = bridge.perform("test-device", "focus_status")
        self.assertIn("topResumedActivity", result)
        self.assertIn("dev.monolith.tv.preview", result)
        self.assertEqual(adb.call_args_list, [
            mock.call("test-device", "dumpsys", "window"),
            mock.call("test-device", "dumpsys", "activity", "activities"),
        ])


if __name__ == "__main__":
    unittest.main()
