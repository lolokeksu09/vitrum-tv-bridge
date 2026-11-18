#!/usr/bin/env python3
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "audit-cleanyourtv-boxy.py"
spec = importlib.util.spec_from_file_location("boxy_audit", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class InventoryTests(unittest.TestCase):
    def test_package_parsing(self):
        self.assertEqual(
            audit.package_ids("package:com.gathin.tvhome\npackage:bad name\npackage:com.skyworth.tv\n"),
            {"com.gathin.tvhome", "com.skyworth.tv"},
        )

    def test_vendor_packages_are_not_auto_approved(self):
        self.assertTrue(audit.is_protected("com.android.systemui"))
        self.assertTrue(audit.is_protected("com.skyworth.foo"))
        self.assertTrue(audit.is_protected("com.google.android.gms"))
        self.assertFalse(audit.is_protected("com.example.analytics"))

    def test_read_only_audit_keeps_sensitive_settings_private(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            downloads = home / "storage" / "downloads"
            downloads.mkdir(parents=True)
            commands = []

            def fake_run(*args, **kwargs):
                return mock.Mock(returncode=0)

            def fake_execute(*parts, timeout=25, binary=False):
                commands.append(parts)
                if parts == ("get-state",):
                    return "device"
                if parts == ("shell", "getprop", "ro.product.model"):
                    return "4K Android TV Box"
                if parts == ("shell", "getprop", "ro.product.manufacturer"):
                    return "SkyworthDigital"
                if parts == ("shell", "getprop", "ro.build.version.sdk"):
                    return "30"
                if parts == ("shell", "getprop", "ro.board.platform"):
                    return "HP44H"
                if parts[:3] == ("shell", "pm", "list"):
                    if parts[-1] == "-d":
                        return "package:com.google.android.tvlauncher\n"
                    if parts[-1] == "-s":
                        return "package:com.skyworth.tv\npackage:com.android.systemui\n"
                    if parts[-1] == "-3":
                        return "package:com.gathin.tvhome\npackage:app.rayclient.tv\n"
                    return "package:com.skyworth.tv\npackage:com.android.systemui\npackage:com.gathin.tvhome\npackage:app.rayclient.tv\n"
                if parts[:3] == ("shell", "settings", "list"):
                    return "secret-token=PRIVATE_DO_NOT_SHARE\n"
                if parts[:4] == ("shell", "cmd", "package", "resolve-activity"):
                    return "com.gathin.tvhome/.MainActivity\n"
                if parts == ("exec-out", "screencap", "-p"):
                    return b"not-a-png"
                return "mocked system details\n"

            with mock.patch.object(audit.Path, "home", return_value=home), \
                 mock.patch.object(audit.subprocess, "run", side_effect=fake_run), \
                 mock.patch.object(audit, "execute", side_effect=fake_execute), \
                 mock.patch.object(audit.sys, "argv", ["audit-cleanyourtv-boxy.py"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = audit.main()

            self.assertEqual(status, 0)
            report = (downloads / "BOXY-CleanYourTV-audit.txt").read_text()
            self.assertIn("com.skyworth.tv", report)
            self.assertIn("com.gathin.tvhome", report)
            self.assertNotIn("PRIVATE_DO_NOT_SHARE", report)
            self.assertIn("NOT APPROVED TO DISABLE", report)
            saved = list((home / "cleanyourtv-backups").glob("audit-*"))
            self.assertEqual(len(saved), 1)
            self.assertIn("PRIVATE_DO_NOT_SHARE",
                          (saved[0] / "settings-secure.txt").read_text())
            self.assertFalse(any(
                any(forbidden in " ".join(cmd) for forbidden in
                    ("disable-user", "uninstall", "settings put", "set-home-activity", "reboot"))
                for cmd in commands
            ))


if __name__ == "__main__":
    unittest.main()
