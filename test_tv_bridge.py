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


class ADBConnectionRecoveryTests(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"

    @mock.patch.object(bridge, "execute")
    @mock.patch.object(bridge, "gh", return_value="lolokeksu09")
    def test_reconnects_known_tcp_device_after_lost_state(self, gh, execute):
        execute.side_effect = [
            ("", 1),
            ("connected to 192.168.0.160:5555", 0),
            ("device", 0),
        ]
        bridge.verify_access(self.DEVICE)
        self.assertEqual([c.args[0] for c in execute.call_args_list], [
            ["adb", "-s", self.DEVICE, "get-state"],
            ["adb", "connect", self.DEVICE],
            ["adb", "-s", self.DEVICE, "get-state"],
        ])

    @mock.patch.object(bridge, "execute")
    @mock.patch.object(bridge, "gh", return_value="lolokeksu09")
    def test_does_not_reconnect_when_already_online(self, gh, execute):
        execute.return_value = ("device", 0)
        bridge.verify_access(self.DEVICE)
        execute.assert_called_once_with(
            ["adb", "-s", self.DEVICE, "get-state"], timeout=8,
            allow_failure=True)

    @mock.patch.object(bridge, "execute")
    @mock.patch.object(bridge, "gh", return_value="lolokeksu09")
    def test_offline_after_reconnect_reports_actionable_error(self, gh, execute):
        execute.side_effect = [
            ("", 1),
            ("failed to connect to 192.168.0.160:5555", 1),
            ("", 1),
        ]
        with self.assertRaisesRegex(bridge.BridgeError, "adb connect"):
            bridge.verify_access(self.DEVICE)
        self.assertEqual(len(execute.call_args_list), 3)

    @mock.patch.object(bridge, "execute")
    @mock.patch.object(bridge, "gh", return_value="unexpected-owner")
    def test_wrong_owner_never_touches_adb(self, gh, execute):
        with self.assertRaisesRegex(bridge.BridgeError, "owner"):
            bridge.verify_access(self.DEVICE)
        execute.assert_not_called()



if __name__ == "__main__":
    unittest.main()
