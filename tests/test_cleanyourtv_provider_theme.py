"""Official ThemeProvider config-only deployment guards. No real ADB calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from scripts.cleanyourtv_provider_files import ProviderTheme, ProviderError, BASE_URI


def reply(code=0, out=b"", err=b""):
    return SimpleNamespace(returncode=code, stdout=out, stderr=err)


class ProviderThemeTests(unittest.TestCase):
    def test_only_known_theme_files_and_known_boxy_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ProviderError, "Unexpected target"):
                ProviderTheme("192.168.1.5:5555", Path(folder))
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            for invalid in ("wallpapers/secret.jpg", "../../config.json"):
                with self.assertRaisesRegex(ProviderError, "Unsupported"):
                    t._uri(invalid)

    @mock.patch("scripts.cleanyourtv_provider_files.invoke")
    def test_read_uses_official_content_provider_and_returns_original_bytes(self, invoke):
        invoke.return_value = reply(out=b'{"dock_apps":["original"]}')
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            self.assertEqual(t.read("config.json"), b'{"dock_apps":["original"]}')
            self.assertEqual(invoke.call_args.args[0],
                             ["adb", "-s", t.device, "exec-out", "content", "read",
                              "--uri", BASE_URI + "config.json"])

    @mock.patch("scripts.cleanyourtv_provider_files.invoke")
    def test_absent_file_is_not_confused_with_permission_denial(self, invoke):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            invoke.return_value = reply(1, err=b"java.io.FileNotFoundException: config.json")
            self.assertIsNone(t.read("config.json"))
            invoke.return_value = reply(1, err=b"Permission Denial: security")
            with self.assertRaisesRegex(ProviderError, "not authorized"):
                t.read("config.json")
            invoke.return_value = reply(1, err=b"Unknown content provider error")
            with self.assertRaisesRegex(ProviderError, "unknown"):
                t.read("config.json")

    @mock.patch.object(ProviderTheme, "read")
    def test_backups_are_complete_before_modification(self, read):
        read.side_effect = [b"\x89PNG\r\n\x1a\nORIGINAL", b'{"columns":6}', b"prior-revision"]
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            state = t.backup_files()
            self.assertEqual(state, {"wallpaper.jpg": True, "config.json": True, "theme_revision": True})
            self.assertEqual((Path(folder) / "original-wallpaper.jpg").read_bytes(), b"\x89PNG\r\n\x1a\nORIGINAL")
            self.assertEqual((Path(folder) / "original-config.json").read_bytes(),
                             b'{"columns":6}')
            self.assertEqual((Path(folder) / "original-theme_revision").read_bytes(),
                             b"prior-revision")
            self.assertEqual(json.loads((Path(folder) / "provider-original-state.json").read_text()),
                             state)

    @mock.patch.object(ProviderTheme, "write")
    @mock.patch.object(ProviderTheme, "delete")
    def test_restore_exact_files_or_remove_only_new_configs(self, delete, write):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            (Path(folder) / "provider-original-state.json").write_text(
                '{"wallpaper.jpg":false,"config.json":true,"theme_revision":false}')
            (Path(folder) / "original-config.json").write_bytes(b'{"prior":true}')
            t.restore()
            write.assert_called_once_with("config.json", b'{"prior":true}')
            self.assertEqual([c.args[0] for c in delete.call_args_list],
                             ["wallpaper.jpg", "theme_revision"])
            self.assertNotIn("wallpaper.jpg", str(write.call_args_list))
            self.assertNotIn("wallpapers/", str(delete.call_args_list))

    @mock.patch.object(ProviderTheme, "write")
    def test_apply_only_touches_config_and_theme_revision(self, write):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            (Path(folder) / "provider-original-state.json").write_text(
                '{"wallpaper.jpg":false,"config.json":false,"theme_revision":false}')
            t.apply(b'{"background_color":"#000000","wallpaper":false}')
            self.assertEqual(write.call_count, 2)
            self.assertEqual(write.call_args_list[0].args[0], "config.json")
            self.assertEqual(write.call_args_list[1].args[0], "theme_revision")
            self.assertNotIn("wallpaper.jpg", str(write.call_args_list))
            self.assertNotIn("wallpapers/", str(write.call_args_list))

    @mock.patch.object(ProviderTheme, "write")
    def test_wallpaper_theme_changes_only_three_allowlisted_files(self, write):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            (Path(folder) / "provider-original-state.json").write_text(
                '{"wallpaper.jpg":false,"config.json":false,"theme_revision":false}')
            config = b'{"wallpaper":true,"single_row":true}'
            art = b"\\x89PNG\\r\\n\\x1a\\nART"
            t.apply(config, wallpaper=art)
            self.assertEqual([c.args[0] for c in write.call_args_list],
                             ["wallpaper.jpg", "config.json", "theme_revision"])
            self.assertEqual(write.call_args_list[0].args[1], art)
            self.assertFalse(any("wallpapers/" in str(call) for call in write.call_args_list))

    @mock.patch.object(ProviderTheme, "_adb")
    def test_rejects_unrecognized_wallpaper_bytes_before_any_adb_write(self, adb):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            with self.assertRaisesRegex(ProviderError, "supported image format"):
                t.write("wallpaper.jpg", b"GIF89aBAD")
            adb.assert_not_called()

    @mock.patch.object(ProviderTheme, "write")
    def test_cannot_enable_wallpaper_without_supplied_asset(self, write):
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            (Path(folder) / "provider-original-state.json").write_text(
                '{"wallpaper.jpg":false,"config.json":false,"theme_revision":false}')
            with self.assertRaisesRegex(ProviderError, "none was supplied"):
                t.apply(b'{"wallpaper":true}')
            write.assert_not_called()

    @mock.patch.object(ProviderTheme, "read")
    @mock.patch.object(ProviderTheme, "_adb")
    def test_write_pushes_verified_bytes_and_deletes_only_own_tmp_file(self, adb, read):
        read.return_value = b'{"safe":true}'
        adb.return_value = reply()
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            t.write("config.json", b'{"safe":true}')
            cmds = [call.args for call in adb.call_args_list]
            self.assertTrue(any(c[0] == "push" for c in cmds))
            self.assertTrue(any(c[0] == "shell" and "content write --uri " in c[1]
                                for c in cmds))
            self.assertTrue(any(c[0] == "shell" and c[1].startswith("rm -f /data/local/tmp/cyt-boxy-")
                                for c in cmds))
            self.assertFalse(any("wallpaper" in str(c) for c in cmds))

    @mock.patch.object(ProviderTheme, "read", side_effect=ProviderError("cannot verify"))
    @mock.patch.object(ProviderTheme, "_adb")
    def test_readback_failure_never_leaves_local_staging_bytes(self, adb, read):
        adb.return_value = reply()
        with tempfile.TemporaryDirectory() as folder:
            t = ProviderTheme("192.168.0.160:5555", Path(folder))
            with self.assertRaises(ProviderError):
                t.write("config.json", b'{"safe":true}')
            self.assertEqual(list(Path(folder).glob("stage-*")), [])


if __name__ == "__main__":
    unittest.main()
