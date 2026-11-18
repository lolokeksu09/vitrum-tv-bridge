"""Security boundary for automatic CleanYourTV theme-only GitHub synchronization."""
import base64
import hashlib
import json
import unittest
from unittest import mock

from scripts import cleanyourtv_remote_preset as remote


def example():
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[1] /
                       "presets/cleanyourtv-boxy/config.json").read_text())


class RemoteThemeTests(unittest.TestCase):
    COMMIT = "a" * 40

    def test_current_amoled_v3_is_valid(self):
        cfg = example()
        raw = json.dumps(cfg).encode()
        self.assertEqual(remote.validate(raw), cfg)

    def test_reject_arbitrary_shell_app_or_network_control_fields(self):
        for field, value in [
            ("command", "pm disable-user com.android.systemui"),
            ("hidden_apps", ["com.google.android.tvlauncher"]),
            ("vpn_app", "com.evil.vpn"),
            ("key_filter", True),
            ("wallpapers", ["picture.jpg"]),
            ("app_keys", ["POWER:sleep"]),
        ]:
            cfg = example()
            cfg[field] = value
            with self.subTest(field=field), self.assertRaises(remote.RemotePresetError):
                remote.validate(json.dumps(cfg).encode())

    def test_refuses_missing_grid_or_colored_wallpaper(self):
        for name, value in [
            ("wallpaper", "not-bool"), ("single_row", True), ("rows_below_dock", 0),
            ("background_color", "#220000"), ("ambient_glow", True),
            ("app_glow", True), ("columns", 2),
        ]:
            cfg = example()
            cfg[name] = value
            with self.subTest(name=name), self.assertRaises(remote.RemotePresetError):
                remote.validate(json.dumps(cfg).encode())

    def test_rejects_bool_as_integer_and_non_bool_strings(self):
        cfg = example()
        cfg["columns"] = True
        with self.assertRaises(remote.RemotePresetError):
            remote.validate(json.dumps(cfg).encode())
        cfg = example()
        cfg["dock_row"] = "true"
        with self.assertRaises(remote.RemotePresetError):
            remote.validate(json.dumps(cfg).encode())

    @mock.patch.object(remote, "gh_json")
    def test_fetch_requires_successful_theme_and_bridge_check_runs(self, fetch):
        cfg = example()
        payload = base64.b64encode(json.dumps(cfg).encode()).decode()
        fetch.side_effect = [
            {"sha": self.COMMIT},
            {"check_runs": [{"name": "verify-preset", "status": "completed",
                             "conclusion": "success"}]},
        ]
        with self.assertRaisesRegex(remote.RemotePresetError, "both theme safety"):
            remote.fetch_verified_main()
        self.assertEqual(fetch.call_count, 2)

        fetch.reset_mock()
        fetch.side_effect = [
            {"sha": self.COMMIT},
            {"check_runs": [
                {"name": "verify-preset", "status": "completed",
                 "conclusion": "success", "head_sha": self.COMMIT},
                {"name": "strict-read-only-bridge", "status": "completed",
                 "conclusion": "success", "head_sha": self.COMMIT},
            ]},
            {"encoding": "base64", "content": payload},
        ]
        raw, sha = remote.fetch_verified_main()
        self.assertEqual(sha, self.COMMIT)
        self.assertEqual(json.loads(raw), cfg)
        self.assertEqual(
            fetch.call_args_list[-1].args[0],
            "repos/" + remote.REPO + "/contents/" + remote.PRESET_PATH +
            "?ref=" + self.COMMIT
        )

    @mock.patch.object(remote, "gh_json")
    def test_failed_main_ci_never_fetches_preset_file(self, fetch):
        fetch.side_effect = [
            {"sha": self.COMMIT},
            {"check_runs": [
                {"name": "verify-preset", "status": "completed",
                 "conclusion": "failure", "head_sha": self.COMMIT},
                {"name": "strict-read-only-bridge", "status": "completed",
                 "conclusion": "success", "head_sha": self.COMMIT},
            ]},
        ]
        with self.assertRaises(remote.RemotePresetError):
            remote.fetch_verified_main()
        self.assertEqual(fetch.call_count, 2)

    @mock.patch.object(remote, "gh_json")
    def test_refuses_malformed_response_and_unapproved_config(self, fetch):
        fetch.side_effect = [
            {"sha": self.COMMIT},
            {"check_runs": [
                {"name": name, "status": "completed", "conclusion": "success",
                 "head_sha": self.COMMIT}
                for name in remote.CHECK_RUNS
            ]},
            {"encoding": "base64", "content": "!!!!"},
        ]
        with self.assertRaises(remote.RemotePresetError):
            remote.fetch_verified_main()



    def test_pinned_anime_wallpaper_is_verified_by_git_blob_hash(self):
        jpg = b"\xff\xd8\xff" + b"sample safe pinned picture" * 3
        sha = hashlib.sha1(b"blob " + str(len(jpg)).encode("ascii") +
                           b"\0" + jpg).hexdigest()
        with mock.patch.object(remote, "ART_GIT_SHA", sha), \
             mock.patch.object(remote, "gh_json", return_value={
                 "sha": sha, "encoding": "base64",
                 "content": base64.b64encode(jpg).decode("ascii"),
             }) as fetch:
            self.assertEqual(remote.fetch_verified_anime_wallpaper(), jpg)
            self.assertIn("?ref=" + remote.ART_REF, fetch.call_args.args[0])
            self.assertEqual(fetch.call_args.kwargs["max_chars"], 500_000)

    def test_anime_wallpaper_sha_mismatch_blocks_device_write(self):
        jpg = b"\xff\xd8\xff" + b"untrusted content"
        with mock.patch.object(remote, "gh_json", return_value={
            "sha": remote.ART_GIT_SHA, "encoding": "base64",
            "content": base64.b64encode(jpg).decode("ascii"),
        }):
            with self.assertRaisesRegex(remote.RemotePresetError, "SHA mismatch"):
                remote.fetch_verified_anime_wallpaper()

    def test_anime_wallpaper_source_or_encoding_mismatch_is_rejected(self):
        for entry in (
            {"sha": "0" * 40, "encoding": "base64", "content": "YWJj"},
            {"sha": remote.ART_GIT_SHA, "encoding": "utf-8", "content": "abc"},
            {"sha": remote.ART_GIT_SHA, "encoding": "base64", "content": "!!!"},
        ):
            with self.subTest(entry=entry), \
                 mock.patch.object(remote, "gh_json", return_value=entry), \
                 self.assertRaises(remote.RemotePresetError):
                remote.fetch_verified_anime_wallpaper()

if __name__ == "__main__":
    unittest.main()
