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

    @mock.patch.object(cm, "restart_official_theme_home")
    @mock.patch.object(cm, "ProviderTheme")
    @mock.patch.object(cm, "prepare_upstream", return_value=Path("/tmp/official-theme.sh"))
    @mock.patch.object(cm, "backup_theme")
    @mock.patch.object(cm, "disabled_packages", return_value=["package:stock"])
    @mock.patch.object(cm, "device_guard")
    def test_provider_theme_partial_failure_restores_prior_config_and_revision(
        self, guard, disabled, backup, source, provider, restart
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

    @mock.patch.object(cm, "prepare_upstream")
    @mock.patch.object(cm, "restart_home_simple")
    @mock.patch.object(cm, "ProviderTheme")
    @mock.patch.object(cm, "backup_theme")
    @mock.patch.object(cm, "disabled_packages", return_value=["package:stock"])
    @mock.patch.object(cm, "device_guard")
    def test_provider_only_mode_skips_cryptography_dependencies(
        self, guard, disabled, backup, provider, restart, upstream
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
