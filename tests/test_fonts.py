"""Tests for Windows Terminal font configuration (yate.services.fonts)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from yate.services import fonts


class ConfigureWindowsTerminalTests(unittest.TestCase):
    def _settings(self, tmp: str, data: dict[str, object]) -> Path:
        path = Path(tmp) / "settings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _run(self, settings: Path) -> tuple[bool, str]:
        with patch.object(fonts, "windows_terminal_settings_path",
                          return_value=settings):
            return fonts.configure_windows_terminal()

    def test_profile_override_is_rewritten(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = self._settings(tmp, {
                "profiles": {
                    "defaults": {"font": {"face": fonts.FAMILY}},
                    "list": [
                        {"name": "PowerShell",
                         "font": {"face": "Cascadia Mono", "size": 10}},
                        {"name": "cmd"},
                    ],
                },
            })
            ok, message = self._run(settings)
            self.assertTrue(ok)
            self.assertIn("1 profile(s)", message)
            data = json.loads(settings.read_text(encoding="utf-8"))
            power_shell = data["profiles"]["list"][0]
            self.assertEqual(power_shell["font"]["face"], fonts.FAMILY)
            self.assertEqual(power_shell["font"]["size"], 10)
            cmd = data["profiles"]["list"][1]
            self.assertNotIn("font", cmd)
            self.assertEqual(
                data["profiles"]["defaults"]["font"]["face"], fonts.FAMILY)

    def test_no_overrides_and_matching_defaults_is_noop(self) -> None:
        with TemporaryDirectory() as tmp:
            raw = json.dumps({
                "profiles": {
                    "defaults": {"font": {"face": fonts.FAMILY}},
                    "list": [{"name": "cmd"}],
                },
            })
            settings = Path(tmp) / "settings.json"
            settings.write_text(raw, encoding="utf-8")
            ok, message = self._run(settings)
            self.assertTrue(ok)
            self.assertIn("already uses", message)
            self.assertEqual(settings.read_text(encoding="utf-8"), raw)
            self.assertFalse((Path(tmp) / "settings.json.yate-bak").exists())

    def test_defaults_are_set_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = self._settings(tmp, {
                "profiles": {"list": [{"name": "cmd"}]},
            })
            ok, _ = self._run(settings)
            self.assertTrue(ok)
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(
                data["profiles"]["defaults"]["font"]["face"], fonts.FAMILY)

    def test_legacy_string_font_schema_is_upgraded(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = self._settings(tmp, {
                "profiles": {
                    "defaults": {"font": "Cascadia Mono"},
                    "list": [{"name": "PowerShell", "font": "Cascadia Mono"}],
                },
            })
            ok, message = self._run(settings)
            self.assertTrue(ok)
            self.assertIn("1 profile(s)", message)
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(
                data["profiles"]["defaults"]["font"]["face"], fonts.FAMILY)
            self.assertEqual(
                data["profiles"]["list"][0]["font"]["face"], fonts.FAMILY)

    def test_backup_is_left_behind(self) -> None:
        with TemporaryDirectory() as tmp:
            settings = self._settings(tmp, {
                "profiles": {
                    "defaults": {"font": {"face": "Cascadia Mono"}},
                },
            })
            ok, _ = self._run(settings)
            self.assertTrue(ok)
            backup = Path(tmp) / "settings.json.yate-bak"
            self.assertTrue(backup.is_file())
            self.assertEqual(
                json.loads(backup.read_text(encoding="utf-8")),
                {"profiles": {"defaults": {"font": {"face": "Cascadia Mono"}}}},
            )


if __name__ == "__main__":
    unittest.main()
