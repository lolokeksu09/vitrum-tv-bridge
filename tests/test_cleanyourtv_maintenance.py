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

    @mock.patch.object(cm, "run")
    @mock.patch.object(cm, "home_resolver", return_value=cm.HOME)
    @mock.patch.object(cm, "disabled_packages", return_value=[])
    @mock.patch.object(cm, "adb")
    def test_provider_overlay_inaccessible_to_shell_fails_closed(
        self, adb, disabled, home, run
    ):
        with tempfile.TemporaryDirectory() as temp:
            def answer(*args, **kwargs):
                if args[:3] == ("exec-out", "screencap", "-p"):
                    return b"\\x89PNG\\r\\n\\x1a\\n" + b"test"
                if args[:3] == ("shell", "ls", "-d"):
                    return ""
                if args[:3] == ("exec-out", "content", "read"):
                    return b'{"columns":4}'
                raise AssertionError("Unexpected ADB command: " + str(args))
            adb.side_effect = answer
            with mock.patch.object(cm, "BACKUPS", Path(temp) / "backups"):
                with self.assertRaisesRegex(cm.MaintenanceError, "inaccessible for backup"):
                    cm.backup_theme()
        run.assert_not_called()

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
