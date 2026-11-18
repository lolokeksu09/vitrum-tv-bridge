"""Guardrails for fixed CleanYourTV BOXY maintenance actions; no real TV commands."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import cleanyourtv_boxy_maintenance as cm


class SafetyTests(unittest.TestCase):
    def test_preset_is_exact_expected_dock_and_opaque_black(self):
        config, digest = cm.check_preset()
        self.assertEqual(config["dock_apps"], cm.DOCK)
        self.assertEqual(config["background_color"], "#000000")
        self.assertEqual(config["rows_below_dock"], 0)
        self.assertEqual(len(digest), 64)

    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "adb")
    def test_device_guard_accepts_only_boxy_and_current_home(self, adb, home):
        adb.side_effect = [
            "device", "4K Android TV Box", "SkyworthDigital", "30", "package:/path/base.apk"
        ]
        self.assertEqual(cm.device_guard()["model"], "4K Android TV Box")
        self.assertEqual(adb.call_count, 5)

    @mock.patch.object(cm, "home_resolver")
    @mock.patch.object(cm, "adb")
    def test_device_guard_refuses_unknown_vendor_without_home_mutation(self, adb, home):
        adb.side_effect = ["device", "4K Android TV Box", "UnknownVendor", "30"]
        with self.assertRaisesRegex(cm.MaintenanceError, "Target mismatch"):
            cm.device_guard()
        home.assert_not_called()
        self.assertFalse(any("disable-user" in str(c) for c in adb.call_args_list))

    @mock.patch.object(cm, "device_guard")
    @mock.patch.object(cm, "adb")
    def test_reboot_refuses_without_theme_receipt(self, adb, guard):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(cm, "RECEIPT", Path(folder) / "absent.json"):
                with self.assertRaisesRegex(cm.MaintenanceError, "No completed"):
                    cm.reboot_check()
        adb.assert_not_called()

    @mock.patch.object(cm, "prepare_upstream")
    @mock.patch.object(cm, "backup_theme", side_effect=cm.MaintenanceError("backup refused"))
    @mock.patch.object(cm, "disabled_packages", return_value=[])
    @mock.patch.object(cm, "device_guard")
    def test_theme_cannot_mutate_if_backup_failed(self, guard, disabled, backup, source):
        with self.assertRaisesRegex(cm.MaintenanceError, "backup refused"):
            cm.theme()
        source.assert_not_called()

    @mock.patch.object(cm, "restore_theme")
    @mock.patch.object(cm, "theme_command", side_effect=cm.MaintenanceError("partial write"))
    @mock.patch.object(cm, "prepare_upstream", return_value=Path("/tmp/official-theme.sh"))
    @mock.patch.object(cm, "backup_theme", return_value=Path("/tmp/backup"))
    @mock.patch.object(cm, "disabled_packages", return_value=["package:stock"])
    @mock.patch.object(cm, "device_guard")
    def test_partial_official_theme_failure_attempts_restore(
        self, guard, disabled, backup, source, apply, restore
    ):
        with self.assertRaisesRegex(cm.MaintenanceError, "previous theme restored"):
            cm.theme()
        restore.assert_called_once_with(Path("/tmp/official-theme.sh"), Path("/tmp/backup"))

    @mock.patch.object(cm, "ProviderTheme")
    @mock.patch.object(cm, "run")
    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "disabled_packages", return_value=[])
    @mock.patch.object(cm, "adb")
    @mock.patch.object(cm, "remote_directory_state", return_value="unknown")
    def test_scoped_storage_falls_back_to_provider_backup_without_touching_wallpapers(
        self, state, adb, disabled, home, run, provider
    ):
        with tempfile.TemporaryDirectory() as temp:
            def answer(*args, **kwargs):
                if args[:3] == ("exec-out", "screencap", "-p"):
                    return b"\\x89PNG\\r\\n\\x1a\\n" + b"test"
                raise AssertionError("Unexpected ADB call: " + str(args))
            adb.side_effect = answer
            with mock.patch.object(cm, "BACKUPS", Path(temp) / "backups"):
                folder = cm.backup_theme()
                self.assertEqual((folder / "mode.txt").read_text(), "provider-only")
        provider.return_value.backup_files.assert_called_once()
        run.assert_not_called()

    @mock.patch.object(cm, "restart_home_simple")
    @mock.patch.object(cm, "ensure_safe_adb_restart")
    @mock.patch.object(cm, "ProviderTheme")
    @mock.patch.object(cm, "prepare_upstream", return_value=Path("/tmp/official-theme.sh"))
    @mock.patch.object(cm, "backup_theme")
    @mock.patch.object(cm, "disabled_packages", return_value=["package:stock"])
    @mock.patch.object(cm, "device_guard")
    def test_provider_theme_partial_failure_restores_prior_config_and_revision(
        self, guard, disabled, backup, source, provider, safe, restart
    ):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "mode.txt").write_text("provider-only")
            backup.return_value = folder
            provider.return_value.apply.side_effect = cm.ProviderError("partial write")
            with self.assertRaisesRegex(cm.MaintenanceError, "previous theme restored"):
                cm.theme()
            provider.return_value.restore.assert_called_once()
            restart.assert_called_once()


    @mock.patch.object(cm, "adb")
    def test_simple_restart_denied_when_clean_launcher_accessibility_helpers_active(self, adb):
        adb.side_effect = [
            "com.gathin.tvhome/.KeyFilterService:com.other/.Service",
            "1",
        ]
        with self.assertRaisesRegex(cm.MaintenanceError, "accessibility"):
            cm.ensure_safe_adb_restart()
        self.assertEqual(adb.call_count, 2)
        self.assertFalse(any("force-stop" in str(c) for c in adb.call_args_list))

    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "adb")
    def test_simple_restart_only_uses_adb_when_no_special_key_helper(self, adb, home):
        adb.side_effect = [
            "com.other/.Service", "1",
            "", "Status: ok",
        ]
        cm.restart_home_simple()
        calls = [str(c) for c in adb.call_args_list]
        self.assertTrue(any("force-stop" in c for c in calls))
        self.assertTrue(any("am" in c and "start" in c for c in calls))
        self.assertFalse(any("settings put" in c for c in calls))
        self.assertFalse(any("disable-user" in c for c in calls))

    @mock.patch.object(cm, "ensure_safe_adb_restart")
    @mock.patch.object(cm, "prepare_upstream")
    @mock.patch.object(cm, "restart_home_simple")
    @mock.patch.object(cm, "ProviderTheme")
    @mock.patch.object(cm, "backup_theme")
    @mock.patch.object(cm, "disabled_packages", return_value=["package:stock"])
    @mock.patch.object(cm, "device_guard")
    def test_provider_only_mode_skips_cryptography_dependencies(
        self, guard, disabled, backup, provider, restart, upstream, safe
    ):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "mode.txt").write_text("provider-only")
            backup.return_value = folder
            provider.return_value.apply.side_effect = cm.ProviderError("partial write")
            with self.assertRaisesRegex(cm.MaintenanceError, "previous theme restored"):
                cm.theme()
            upstream.assert_not_called()
            provider.return_value.restore.assert_called_once()
            restart.assert_called_once()


    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "home_focus", side_effect=[False, False, True])
    @mock.patch.object(cm, "adb")
    def test_home_focus_wait_retries_after_transient_android_launch(self, adb, focus, resolver):
        pauses = []
        cm.verify_home_after_theme(pause=lambda n: pauses.append(n), tries=5)
        self.assertEqual(focus.call_count, 3)
        self.assertGreaterEqual(len(pauses), 2)
        self.assertTrue(all(c.args[:3] == ("shell", "input", "keyevent")
                            for c in adb.call_args_list))
        self.assertTrue(all(c.args[3] == "3" for c in adb.call_args_list))

    @mock.patch.object(cm, "home_resolver", return_value="com.google.android.tvlauncher/.Home")
    @mock.patch.object(cm, "home_focus")
    @mock.patch.object(cm, "adb")
    def test_home_focus_wait_rejects_wrong_system_default_without_key_events(self, adb, focus, resolver):
        with self.assertRaisesRegex(cm.MaintenanceError, "default HOME"):
            cm.verify_home_after_theme(pause=lambda _: None, tries=3)
        adb.assert_not_called()
        focus.assert_not_called()

    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "home_focus", return_value=False)
    @mock.patch.object(cm, "adb")
    def test_home_focus_wait_fails_closed_after_retry_limit(self, adb, focus, resolver):
        pauses = []
        with self.assertRaisesRegex(cm.MaintenanceError, "not confirmed"):
            cm.verify_home_after_theme(pause=lambda n: pauses.append(n), tries=4)
        self.assertEqual(focus.call_count, 4)
        self.assertEqual(len(pauses), 3)


    @mock.patch.object(cm, "adb")
    def test_theme_failure_records_window_and_running_process_without_dumping_logs(self, adb):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            def answer(*args, **kwargs):
                if args[:3] == ("shell", "dumpsys", "window"):
                    return "mCurrentFocus=Window{1 u0 com.android.tv.settings/.MainSettings}\\nTOKEN_PRIVATE"
                if args[:4] == ("shell", "dumpsys", "activity", "activities"):
                    return "topResumedActivity: ActivityRecord{2 u0 com.android.tv.settings/.MainSettings}"
                if args[:2] == ("shell", "pidof"):
                    return "12345"
                if args[:3] == ("exec-out", "screencap", "-p"):
                    return b"\\x89PNG\\r\\n\\x1a\\n" + b"image"
                raise AssertionError(args)
            adb.side_effect = answer
            info = cm.capture_theme_failure_state(folder)
            self.assertIn("com.android.tv.settings", info)
            self.assertIn("process=running", info)
            self.assertNotIn("TOKEN_PRIVATE", info)
            self.assertTrue((folder / "screen-failed-before-rollback.png").is_file())

    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "home_focus", return_value=False)
    @mock.patch.object(cm, "adb")
    def test_home_verify_attempts_direct_activity_restart_before_failing(self, adb, focus, resolver):
        adb.return_value = "Status: ok"
        with self.assertRaisesRegex(cm.MaintenanceError, "not confirmed"):
            cm.verify_home_after_theme(pause=lambda _: None, tries=8)
        direct = [c.args for c in adb.call_args_list
                  if c.args[:4] == ("shell", "am", "start", "-W")]
        self.assertEqual(len(direct), 1)
        self.assertIn(cm.HOME, direct[0])
        self.assertEqual(focus.call_count, 8)


    @mock.patch.object(cm, "adb")
    def test_real_boxy_window_dump_reports_home_focus(self, adb):
        adb.return_value = (
            "WINDOW MANAGER\n"
            "  mCurrentFocus=Window{c27cacf u0 "
            "com.gathin.tvhome/com.gathin.tvhome.MainActivity}\n"
            "  mFocusedApp=ActivityRecord{b4cd9f6 u0 "
            "com.gathin.tvhome/.MainActivity t1700}\n"
        )
        self.assertTrue(cm.home_focus())
        adb.assert_called_once_with("shell", "dumpsys", "window", timeout=30)

    @mock.patch.object(cm, "adb")
    def test_fallback_requires_both_focused_app_and_resumed_home(self, adb):
        adb.side_effect = [
            "WINDOW MANAGER\n"
            "  mFocusedApp=ActivityRecord{b4cd9f6 u0 "
            "com.gathin.tvhome/.MainActivity t1700}\n",
            "topResumedActivity=ActivityRecord{a1 u0 "
            "com.gathin.tvhome/.MainActivity t1700}",
        ]
        self.assertTrue(cm.home_focus())
        self.assertEqual(adb.call_args_list[1].args,
                         ("shell", "dumpsys", "activity", "activities"))

    @mock.patch.object(cm, "adb")
    def test_other_foreground_window_is_not_accepted(self, adb):
        adb.return_value = (
            "mCurrentFocus=Window{1 u0 com.android.tv.settings/.MainSettings}\n"
            "mFocusedApp=ActivityRecord{2 u0 com.gathin.tvhome/.MainActivity}\n"
        )
        self.assertFalse(cm.home_focus())
        adb.assert_called_once()

    @mock.patch.object(cm, "adb")
    def test_mismatched_resumed_activity_is_not_accepted(self, adb):
        adb.side_effect = [
            "mFocusedApp=ActivityRecord{2 u0 com.gathin.tvhome/.MainActivity}",
            "topResumedActivity=ActivityRecord{3 u0 "
            "com.android.tv.settings/.MainSettings}",
        ]
        self.assertFalse(cm.home_focus())

    @mock.patch.object(cm, "adb")
    def test_no_focus_information_fails_closed(self, adb):
        adb.side_effect = ["WINDOW MANAGER", "no activity information"]
        self.assertFalse(cm.home_focus())

    @mock.patch.object(cm, "adb")
    def test_theme_directory_probe_reports_definite_absence(self, adb):
        adb.return_value = (
            "ls: /sdcard/Android/data/com.gathin.tvhome/files: "
            "No such file or directory\\nCYT_LS_EXIT:1"
        )
        self.assertEqual(cm.remote_directory_state(), "absent")
        self.assertEqual(adb.call_args.args[0], "shell")
        self.assertEqual(len(adb.call_args.args), 2)
        self.assertIn("ls -ld", adb.call_args.args[1])
        self.assertIn("CYT_LS_EXIT", adb.call_args.args[1])

    @mock.patch.object(cm, "adb")
    def test_theme_directory_probe_refuses_scoped_storage_permission_denied(self, adb):
        adb.return_value = (
            "ls: /sdcard/Android/data/com.gathin.tvhome/files: "
            "Permission denied\\nCYT_LS_EXIT:1"
        )
        self.assertEqual(cm.remote_directory_state(), "unknown")

    @mock.patch.object(cm, "adb")
    def test_theme_directory_probe_accepts_listing_only_on_exit_zero(self, adb):
        adb.return_value = (
            "drwxrwx--- 3 u0_a123 ext_data_rw 4096 ...\\nCYT_LS_EXIT:0"
        )
        self.assertEqual(cm.remote_directory_state(), "exists")
        adb.return_value = "CYT_LS_EXIT:1"
        self.assertEqual(cm.remote_directory_state(), "unknown")

    @mock.patch.object(cm, "run")
    def test_only_exact_fixed_cli_operations_are_allowed(self, run):
        with mock.patch.object(cm.sys, "argv", ["maintenance", "shell", "pm disable-user"]):
            with self.assertRaisesRegex(cm.MaintenanceError, "Fixed operations only"):
                cm.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
