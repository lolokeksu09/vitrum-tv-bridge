"""Contract tests for the optional v2 bridge; no real GitHub or ADB calls."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tv_bridge_v2 as bridge

NOW = dt.datetime(2026, 11, 13, 8, 0, tzinfo=dt.timezone.utc)


def issue(op, args=None, title=None, body=None, author="lolokeksu09", created=None):
    return {
        "number": 42,
        "author": {"login": author},
        "createdAt": (created or NOW).isoformat(),
        "title": title if title is not None else "TVBRIDGE/v2 " + op,
        "body": body if body is not None else __import__("json").dumps(
            {"v": 2, "op": op, "args": args if args is not None else {}}
        ),
    }


class ProtocolTests(unittest.TestCase):
    def test_core_ops_accepted(self):
        for op in ["device_summary", "vitrum_status", "display_status",
                   "focus_status", "app_list", "vitrum_memory",
                   "launch_vitrum", "stop_vitrum", "screenshot"]:
            r = bridge.parse_issue(issue(op), now=NOW)
            self.assertEqual(op, r["op"])

    def test_key_args_validated(self):
        r = bridge.parse_issue(issue("key", {"key": "UP"}), now=NOW)
        self.assertEqual("UP", r["args"]["key"])
        self.assertIsNone(bridge.parse_issue(issue("key", {"key": "POWER"}), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue("key", {"key": "0; reboot"}), now=NOW))

    def test_no_arbitrary_shell(self):
        self.assertIsNone(bridge.parse_issue(issue("shell", {"command": "rm -rf /"}), now=NOW))

    def test_package_is_syntactically_constrained(self):
        self.assertIsNotNone(bridge.parse_issue(
            issue("app_info", {"package": "com.example.app"}), now=NOW))
        for value in ["com.x;reboot", "com.x/../../", "android", "com.x\nrun", ""]:
            self.assertIsNone(bridge.parse_issue(
                issue("launch_app", {"package": value}), now=NOW))

    def test_install_requires_sha256_and_safe_filename(self):
        good = {"filename": "Vitrum-TV-BOXY-0.1.0-dev.apk", "sha256": "a" * 64}
        self.assertIsNotNone(bridge.parse_issue(issue("install_vitrum", good), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "install_vitrum", {"filename": "../evil.apk", "sha256": "a"*64}), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "install_vitrum", {"filename": "Vitrum-TV.apk", "sha256": "bad"}), now=NOW))

    def test_invalid_request_shapes(self):
        self.assertIsNone(bridge.parse_issue(issue("app_list", {"x": 1}), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "app_list", body='{"v":true,"op":"app_list","args":{}}'), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "app_list", body='{"v":2,"op":"app_list","args":{},"extra":"x"}'), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "app_list", body="garbage"), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "app_list", author="not-owner"), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "app_list", title="TVBRIDGE/v2 stop_vitrum"), now=NOW))

    def test_expired_and_future_request_rejected(self):
        self.assertIsNone(bridge.parse_issue(issue(
            "launch_vitrum", created=NOW - dt.timedelta(hours=3)), now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "launch_vitrum", created=NOW + dt.timedelta(minutes=10)), now=NOW))

    def test_v1_read_only_request_kept(self):
        old = {
            "number": 41,
            "author": {"login": "lolokeksu09"},
            "title": "TVBRIDGE/v1 device_summary",
            "body": '{"v":1,"op":"device_summary"}',
        }
        self.assertEqual("device_summary", bridge.parse_issue(old, now=NOW)["op"])


class ActionAuthorization(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"

    def req(self, op, args=None):
        return {"number": 42, "op": op, "args": args or {}}

    def test_control_denied_by_default(self):
        for op, args in [
            ("key", {"key": "HOME"}), ("launch_vitrum", {}),
            ("stop_vitrum", {}), ("launch_app", {"package": "com.example.app"})
        ]:
            with self.assertRaises(bridge.ActionDenied):
                bridge.run_action(self.DEVICE, self.req(op, args), bridge.Permissions())

    @mock.patch.object(bridge.base, "adb", return_value=("Starting: Intent", 0))
    def test_launch_uses_constant_component(self, adb):
        p = bridge.Permissions(control=True)
        bridge.run_action(self.DEVICE, self.req("launch_vitrum"), p)
        adb.assert_called_once_with(
            self.DEVICE, "am", "start", "-n", "app.rayclient.tv/.TvActivity"
        )

    @mock.patch.object(bridge.base, "adb", return_value=("", 0))
    def test_remote_key_uses_fixed_keycode(self, adb):
        bridge.run_action(self.DEVICE, self.req("key", {"key": "LEFT"}),
                          bridge.Permissions(control=True))
        adb.assert_called_once_with(self.DEVICE, "input", "keyevent", "21")

    @mock.patch.object(bridge.base, "adb", return_value=("", 0))
    def test_stop_is_scoped_to_vitrum(self, adb):
        bridge.run_action(self.DEVICE, self.req("stop_vitrum"),
                          bridge.Permissions(control=True))
        adb.assert_called_once_with(self.DEVICE, "am", "force-stop", "app.rayclient.tv")

    def test_screenshot_requires_explicit_flag(self):
        with self.assertRaises(bridge.ActionDenied):
            bridge.run_action(self.DEVICE, self.req("screenshot"),
                              bridge.Permissions(control=True))

    def test_install_requires_opt_in_and_valid_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "Vitrum-TV-test.apk"
            file.write_bytes(b"test-APK")
            request = self.req("install_vitrum", {
                "filename": file.name, "sha256": "a"*64
            })
            with self.assertRaises(bridge.ActionDenied):
                bridge.run_action(self.DEVICE, request, bridge.Permissions(),
                                  downloads=Path(folder))
            with self.assertRaises(bridge.BridgeError):
                bridge.run_action(self.DEVICE, request,
                                  bridge.Permissions(install=True),
                                  downloads=Path(folder))

    @mock.patch.object(bridge.base, "adb", return_value=("", 0))
    def test_list_app_packages_has_no_injected_commands(self, adb):
        bridge.run_action(self.DEVICE, self.req("app_list"),
                          bridge.Permissions())
        adb.assert_called_once_with(self.DEVICE, "pm", "list", "packages", "-3")


if __name__ == "__main__":
    unittest.main()
