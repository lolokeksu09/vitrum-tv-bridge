"""Official ThemeProvider fallback for Android TV 11 scoped storage.

Touches only the three explicitly allowlisted launcher-owned files:
config.json, wallpaper.jpg and theme_revision.
Never lists, deletes or alters the wallpapers/ collection, system packages or TV settings.
All content (including prior private theme preferences) remains on the phone.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import uuid

BASE_URI = "content://com.gathin.tvhome.theme/"
FILES = ("wallpaper.jpg", "config.json", "theme_revision")


class ProviderError(Exception):
    pass


def invoke(argv, *, timeout=40):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderError("ADB ContentProvider operation failed or timed out") from exc
    return result


class ProviderTheme:
    def __init__(self, device: str, backup: Path):
        if device != "192.168.0.160:5555":
            raise ProviderError("Unexpected target device; refusing theme")
        self.device = device
        self.backup = Path(backup)

    def _uri(self, name):
        if name not in FILES:
            raise ProviderError("Unsupported theme file")
        return BASE_URI + name

    def _adb(self, *args, timeout=40):
        return invoke(["adb", "-s", self.device, *args], timeout=timeout)

    def read(self, name):
        uri = self._uri(name)
        result = self._adb("exec-out", "content", "read", "--uri", uri)
        error = (result.stderr + (result.stdout[:500] if result.returncode else b"")).decode(
            "utf-8", errors="replace")
        if "Permission Denial" in error or "SecurityException" in error:
            raise ProviderError("ThemeProvider read is not authorized")
        if ("FileNotFoundException" in error or
                "No such file or directory" in error) and result.returncode:
            return None
        if result.returncode:
            raise ProviderError("ThemeProvider read status is unknown; no changes")
        if (b"Error while accessing provider" in result.stdout or
                b"Unsupported operation" in result.stdout):
            # Older Android content CLIs can print an error yet return exit 0.
            if b"FileNotFoundException" in result.stdout:
                return None
            raise ProviderError("ThemeProvider read reported a non-file error")
        limit = 8_000_000 if name == "wallpaper.jpg" else 512000
        if len(result.stdout) > limit:
            raise ProviderError("Existing theme file too large to back up safely")
        if len(result.stdout) == 0 and name == "config.json":
            raise ProviderError("Empty existing theme config cannot be classified")
        return result.stdout

    def backup_files(self):
        self.backup.mkdir(parents=True, exist_ok=True, mode=0o700)
        status = {}
        for name in FILES:
            prior = self.read(name)
            status[name] = prior is not None
            if prior is not None:
                file = self.backup / ("original-" + name)
                file.write_bytes(prior)
                file.chmod(0o600)
        path = self.backup / "provider-original-state.json"
        path.write_text(json.dumps(status), encoding="utf-8")
        path.chmod(0o600)
        return status

    def _original(self):
        state = self.backup / "provider-original-state.json"
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProviderError("Provider theme backup state is missing") from exc
        if set(data) != set(FILES) or not all(type(value) is bool for value in data.values()):
            raise ProviderError("Provider theme backup state invalid")
        for name in FILES:
            if data[name] and not (self.backup / ("original-" + name)).is_file():
                raise ProviderError("Missing original theme bytes; refusing modification")
        return data

    def write(self, name, content):
        uri = self._uri(name)
        limit = 8_000_000 if name == "wallpaper.jpg" else 512000
        if (not isinstance(content, bytes) or len(content) > limit
                or (len(content) == 0 and name != "theme_revision")):
            raise ProviderError("Invalid bounded theme payload")
        if name == "wallpaper.jpg" and not (
            content.startswith(b"\x89PNG\r\n\x1a\n")
            or content.startswith(b"\xff\xd8\xff")
            or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
        ):
            raise ProviderError("Wallpaper bytes must be a supported image format")
        unique = uuid.uuid4().hex[:12]
        remote = "/data/local/tmp/cyt-boxy-" + unique + "-" + name
        source = self.backup / ("stage-" + unique + "-" + name)
        source.write_bytes(content)
        source.chmod(0o600)
        try:
            pushed = self._adb("push", str(source), remote, timeout=70)
            if pushed.returncode:
                raise ProviderError("Cannot stage theme bytes on the TV")
            command = "content write --uri " + uri + " < " + remote
            result = self._adb("shell", command)
            if (result.returncode or b"Error while accessing provider" in result.stdout
                    or b"Unsupported operation" in result.stdout):
                raise ProviderError("ThemeProvider rejected theme write")
            if self.read(name) != content:
                raise ProviderError("ThemeProvider readback mismatch after write")
        finally:
            try:
                self._adb("shell", "rm -f " + remote, timeout=12)
            finally:
                source.unlink(missing_ok=True)

    def delete(self, name):
        uri = self._uri(name)
        result = self._adb("shell", "content delete --uri " + uri)
        if result.returncode or b"Error while accessing provider" in result.stdout:
            raise ProviderError("ThemeProvider refused original-file removal")
        if self.read(name) is not None:
            raise ProviderError("Previously absent theme file still exists after delete")

    def restore(self):
        before = self._original()
        errors = []
        # Attempt both even if one fails, so no partial restoration is hidden.
        for name in FILES:
            try:
                if before[name]:
                    self.write(name, (self.backup / ("original-" + name)).read_bytes())
                else:
                    self.delete(name)
            except (OSError, ProviderError) as exc:
                errors.append(name + ": " + str(exc))
        if errors:
            raise ProviderError("Provider rollback incomplete: " + "; ".join(errors))

    def apply(self, config: bytes, wallpaper: bytes | None = None):
        self._original()  # No mutation until ALL original files were captured.
        new_config = json.loads(config)
        if not isinstance(new_config, dict):
            raise ProviderError("New theme config is not a JSON object")
        if new_config.get("wallpaper") is True and wallpaper is None:
            raise ProviderError("Theme references a wallpaper but none was supplied")
        # Write background first so it exists before the new config enables it.
        if wallpaper is not None:
            self.write("wallpaper.jpg", wallpaper)
        self.write("config.json", config)
        self.write("theme_revision", uuid.uuid4().hex.encode("ascii"))
