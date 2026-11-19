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


class SingleAgentLockTests(unittest.TestCase):
    def test_parallel_agent_rejected_and_lock_released(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / "tv-bridge.lock"
            with bridge.single_agent_lock(lock):
                with self.assertRaisesRegex(bridge.BridgeError, "already running"):
                    with bridge.single_agent_lock(lock):
                        self.fail("Duplicate agent acquired lock")
            with bridge.single_agent_lock(lock):
                self.assertTrue(lock.is_file())


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

    @mock.patch.object(bridge.subprocess, "run")
    @mock.patch.object(bridge.base, "gh", return_value='{"private":false}')
    def test_public_repo_denies_capture_before_reading_screen(self, gh, run):
        with self.assertRaisesRegex(bridge.ActionDenied, "public"):
            bridge.capture_screenshot(self.DEVICE, 501)
        gh.assert_called_once_with("api", "repos/" + bridge.REPO)
        run.assert_not_called()

    @mock.patch.object(bridge.base, "adb")
    @mock.patch.object(bridge.base, "gh", return_value='{"private":false}')
    def test_public_repo_denies_ui_sweep_before_navigation(self, gh, adb):
        with self.assertRaises(bridge.ActionDenied):
            bridge.audit_five_pages(self.DEVICE, 501)
        adb.assert_not_called()

    @mock.patch.object(bridge.base, "gh", return_value='{"private":true}')
    def test_only_confirmed_private_repo_allows_capture_path(self, gh):
        bridge.require_private_capture_repo()
        gh.assert_called_once_with("api", "repos/" + bridge.REPO)

    @mock.patch.object(bridge.base, "gh", return_value='{"visibility":"public"}')
    def test_missing_private_visibility_fails_closed(self, gh):
        with self.assertRaisesRegex(bridge.ActionDenied, "visibility"):
            bridge.require_private_capture_repo()

    def test_public_issue_comments_withhold_device_output(self):
        private_data = "Private backup: /data/data/com.termux/files/home/private"
        self.assertEqual(bridge.public_safe_result(private_data, True), private_data)
        safe = bridge.public_safe_result(private_data, False)
        self.assertNotIn("/data/data", safe)
        self.assertIn("withheld", safe)


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




class ForegroundGuard(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"

    def test_ui_sweep_is_a_strictly_parsed_operation(self):
        self.assertEqual("ui_sweep", bridge.parse_issue(
            issue("ui_sweep"), now=NOW)["op"])
        self.assertIsNone(bridge.parse_issue(
            issue("ui_sweep", {"shell": "reboot"}), now=NOW))

    def test_ui_sweep_requires_local_control_and_screenshot_consent(self):
        task = {"number": 50, "op": "ui_sweep", "args": {}}
        for flags in [bridge.Permissions(),
                      bridge.Permissions(control=True),
                      bridge.Permissions(screenshot=True)]:
            with self.assertRaises(bridge.ActionDenied):
                bridge.run_action(self.DEVICE, task, flags)

    @mock.patch.object(bridge, "capture_screenshot")
    @mock.patch.object(bridge.base, "adb")
    def test_ui_sweep_fails_closed_before_keys_if_other_app_is_foreground(self, adb, capture):
        adb.return_value = (
            "topResumedActivity=ActivityRecord{123 u0 com.android.vending/.MainActivity t1}", 0
        )
        task = {"number": 50, "op": "ui_sweep", "args": {}}
        with self.assertRaises(bridge.BridgeError):
            bridge.run_action(self.DEVICE, task,
                              bridge.Permissions(control=True, screenshot=True))
        capture.assert_not_called()
        self.assertFalse(any(call.args[1] == "input" for call in adb.call_args_list))

    @mock.patch.object(bridge, "require_private_capture_repo")
    @mock.patch.object(bridge, "capture_screenshot", return_value="private capture")
    @mock.patch.object(bridge.base, "adb")
    def test_ui_sweep_records_all_five_pages_only_with_verified_foreground(self, adb, capture, private_guard):
        def reply(device, *arguments, **kwargs):
            if arguments[:3] == ("dumpsys", "activity", "activities"):
                return ("topResumedActivity=ActivityRecord{123 u0 app.rayclient.tv/.TvActivity t9}", 0)
            return ("ok", 0)
        adb.side_effect = reply
        result = bridge.run_action(
            self.DEVICE, {"number": 50, "op": "ui_sweep", "args": {}},
            bridge.Permissions(control=True, screenshot=True)
        )
        private_guard.assert_called_once()
        self.assertEqual(5, capture.call_count)
        self.assertIn("home", result)
        self.assertIn("settings", result)
        self.assertIn("Returned to Home", result)



class VerifiedArtifactInstall(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"

    def test_ci_install_requires_strict_run_id_and_sha(self):
        args = {"run_id": 43376055711, "sha256": "a" * 64}
        self.assertIsNotNone(bridge.parse_issue(
            issue("install_vitrum_ci", args), now=NOW))
        for invalid in [
            {"run_id": True, "sha256": "a" * 64},
            {"run_id": -1, "sha256": "a" * 64},
            {"run_id": "43376055711", "sha256": "a" * 64},
            {"run_id": 43376055711, "sha256": "invalid"},
            {"run_id": 43376055711, "sha256": "a"*64, "repo": "other/evil"},
        ]:
            self.assertIsNone(bridge.parse_issue(
                issue("install_vitrum_ci", invalid), now=NOW))

    def test_ci_install_is_denied_without_local_install_flag(self):
        task = {"number": 51, "op": "install_vitrum_ci",
                "args": {"run_id": 43376055711, "sha256": "a" * 64}}
        with self.assertRaises(bridge.ActionDenied):
            bridge.run_action(self.DEVICE, task, bridge.Permissions())

    @mock.patch.object(bridge.base, "gh")
    @mock.patch.object(bridge.subprocess, "run")
    def test_ci_install_rejects_non_tv_or_failed_workflow_without_download(self, run, gh):
        task = {"number": 51, "op": "install_vitrum_ci",
                "args": {"run_id": 43376055711, "sha256": "a" * 64}}
        import json
        for meta in [
            {"name": "Deploy", "conclusion": "success",
             "head_branch": "feature/vitrum-tv-foundation"},
            {"name": "Vitrum TV developer shell verification", "conclusion": "failure",
             "head_branch": "feature/vitrum-tv-foundation"},
            {"name": "Vitrum TV developer shell verification", "conclusion": "success",
             "head_branch": "main"},
        ]:
            gh.return_value = json.dumps(meta)
            with self.assertRaises(bridge.BridgeError):
                bridge.run_action(self.DEVICE, task,
                                  bridge.Permissions(install=True))
        run.assert_not_called()


class MonolithVerifiedInstall(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"
    CI_RUN = 43482516803
    APK_CONTENT = b"synthetic-monolith-apk-bytes"
    REPO = "lolokeksu09/MONOLITH-TV"

    def request(self, digest):
        return {"number": 123, "op": "install_monolith_ci", "args": {
            "run_id": self.CI_RUN, "sha256": digest,
        }}

    def metadata(self, **overrides):
        d = {
            "name": "Android TV CI", "head_branch": "main",
            "event": "push", "status": "completed",
            "conclusion": "success",
            "repository": {"full_name": self.REPO}
        }
        d.update(overrides)
        return d

    def test_request_strictly_validated(self):
        args = {"run_id": self.CI_RUN, "sha256": "a" * 64}
        self.assertIsNotNone(bridge.parse_issue(
            issue("install_monolith_ci", args), now=NOW
        ))
        for bad in [
            {"run_id": True, "sha256": "a" * 64},
            {"run_id": self.CI_RUN, "sha256": "invalid"},
            {"run_id": self.CI_RUN, "sha256": "a" * 64, "repo": "bad/repo"},
            {"run_id": str(self.CI_RUN), "sha256": "a" * 64},
        ]:
            self.assertIsNone(bridge.parse_issue(
                issue("install_monolith_ci", bad), now=NOW
            ))

    @mock.patch.object(bridge.base, "gh")
    @mock.patch.object(bridge.subprocess, "run")
    def test_denied_without_local_install_opt_in(self, run, gh):
        with self.assertRaises(bridge.ActionDenied):
            bridge.run_action(self.DEVICE, self.request("a" * 64),
                              bridge.Permissions(control=True, screenshot=True))
        gh.assert_not_called()
        run.assert_not_called()

    @mock.patch.object(bridge.base, "execute")
    @mock.patch.object(bridge.subprocess, "run")
    @mock.patch.object(bridge.base, "gh")
    def test_refuses_non_main_or_untrusted_ci(self, gh, run, execute):
        import json
        variants = [
            self.metadata(name="Other workflow"),
            self.metadata(head_branch="feature/test"),
            self.metadata(event="pull_request"),
            self.metadata(status="in_progress"),
            self.metadata(conclusion="failure"),
            self.metadata(repository={"full_name": "another/repo"}),
        ]
        for variant in variants:
            gh.return_value = json.dumps(variant)
            with self.assertRaisesRegex(bridge.BridgeError, "provenance"):
                bridge.run_action(self.DEVICE, self.request("a" * 64),
                                  bridge.Permissions(install=True))
        run.assert_not_called()
        execute.assert_not_called()

    @mock.patch.object(bridge.base, "execute")
    @mock.patch.object(bridge.subprocess, "run")
    @mock.patch.object(bridge.base, "gh")
    def test_sha_match_installs_once_without_data_clear(self, gh, run, execute):
        import hashlib
        import json
        gh.return_value = json.dumps(self.metadata())

        def create_downloaded_apk(argv, **_kwargs):
            folder = Path(argv[argv.index("-D") + 1])
            (folder / "app-debug.apk").write_bytes(self.APK_CONTENT)
            return mock.Mock(returncode=0)

        run.side_effect = create_downloaded_apk
        execute.return_value = ("Success", 0)
        digest = hashlib.sha256(self.APK_CONTENT).hexdigest()
        result = bridge.run_action(
            self.DEVICE, self.request(digest), bridge.Permissions(install=True)
        )
        self.assertIn("Installed verified MONOLITH TV", result)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:4], [
            "gh", "run", "download", str(self.CI_RUN)
        ])
        cmd = execute.call_args.args[0]
        self.assertEqual(cmd[:5], [
            "adb", "-s", self.DEVICE, "install", "-r"
        ])
        self.assertEqual(Path(cmd[-1]).name, "app-debug.apk")
        self.assertNotIn("uninstall", cmd)
        self.assertNotIn("pm clear", " ".join(cmd))

    @mock.patch.object(bridge.base, "execute")
    @mock.patch.object(bridge.subprocess, "run")
    @mock.patch.object(bridge.base, "gh")
    def test_sha_mismatch_never_installs(self, gh, run, execute):
        import json
        gh.return_value = json.dumps(self.metadata())

        def download(argv, **_kwargs):
            folder = Path(argv[argv.index("-D") + 1])
            (folder / "app-debug.apk").write_bytes(self.APK_CONTENT)
            return mock.Mock(returncode=0)

        run.side_effect = download
        with self.assertRaisesRegex(bridge.BridgeError, "SHA-256 mismatch"):
            bridge.run_action(
                self.DEVICE, self.request("0" * 64),
                bridge.Permissions(install=True)
            )
        execute.assert_not_called()



class CleanYourTVMaintenanceContract(unittest.TestCase):
    DEVICE = "192.168.0.160:5555"

    def task(self, op, args=None):
        return {"number": 47, "op": op, "args": args or {}}

    def test_schema_rejects_shell_and_arbitrary_maintenance_parameters(self):
        for op in ("cleanyourtv_probe", "cleanyourtv_apply_theme",
                   "cleanyourtv_reboot_check", "cleanyourtv_perf_probe"):
            self.assertIsNotNone(bridge.parse_issue(issue(op), now=NOW))
            self.assertIsNone(bridge.parse_issue(
                issue(op, {"command": "pm disable-user com.android.systemui"}),
                now=NOW))
        self.assertIsNone(bridge.parse_issue(issue(
            "system_shell", {"command": "reboot"}), now=NOW))

    def test_maintenance_and_reboot_require_distinct_local_opt_in(self):
        for op in ("cleanyourtv_apply_theme", "cleanyourtv_reboot_check"):
            with self.assertRaises(bridge.ActionDenied):
                bridge.run_action(self.DEVICE, self.task(op),
                                  bridge.Permissions(control=True, screenshot=True))
        with self.assertRaises(bridge.ActionDenied):
            bridge.run_action(self.DEVICE,
                              self.task("cleanyourtv_reboot_check"),
                              bridge.Permissions(maintenance=True))

    def test_perf_sampling_requires_both_maintenance_and_control(self):
        for permissions in (bridge.Permissions(),
                            bridge.Permissions(control=True),
                            bridge.Permissions(maintenance=True)):
            with self.subTest(permissions=permissions), \\
                 self.assertRaises(bridge.ActionDenied):
                bridge.run_action(self.DEVICE,
                                  self.task("cleanyourtv_perf_probe"), permissions)

    def test_only_anonymous_perf_metrics_may_appear_in_public_issues(self):
        safe = ("PERF_V1 frames=25 p50_ms=11.4 "
                "p95_ms=22.1 slow16_pct=16.0")
        self.assertEqual(bridge.public_safe_result(
            safe, False, "cleanyourtv_perf_probe", "SUCCESS"), safe)
        for candidate, op, status in (
            (safe + "\\nPrivate backup: /sdcard/secret", "cleanyourtv_perf_probe", "SUCCESS"),
            (safe, "app_info", "SUCCESS"),
            (safe, "cleanyourtv_perf_probe", "ERROR"),
            (safe.replace("11.4", "11x4"), "cleanyourtv_perf_probe", "SUCCESS"),
        ):
            with self.subTest(candidate=candidate, op=op, status=status):
                sanitized = bridge.public_safe_result(candidate, False, op, status)
                self.assertIn("withheld", sanitized)
                self.assertNotIn("/sdcard/", sanitized)

    @mock.patch.object(bridge, "invoke_cleanyourtv_maintenance")
    def test_ops_dispatch_only_fixed_internal_actions(self, invoke):
        invoke.return_value = "VERIFIED"
        permissions = bridge.Permissions(maintenance=True, reboot=True, control=True)
        expected = (
            ("cleanyourtv_probe", "probe"),
            ("cleanyourtv_apply_theme", "theme"),
            ("cleanyourtv_reboot_check", "reboot"),
            ("cleanyourtv_perf_probe", "perf"),
        )
        for op, internal in expected:
            output = bridge.run_action(self.DEVICE, self.task(op), permissions)
            self.assertEqual(output, "VERIFIED")
            invoke.assert_called_with(self.DEVICE, internal)


if __name__ == "__main__":
    unittest.main()
