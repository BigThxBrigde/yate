"""Tests for Windows Terminal font configuration (yate.services.fonts)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yate.services import fonts


def _settings(tmp: Path, data: dict[str, object]) -> Path:
    path = tmp / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run(settings: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[bool, str]:
    monkeypatch.setattr(
        fonts, "windows_terminal_settings_path", lambda: settings
    )
    return fonts.configure_windows_terminal()


# --- profile rewriting ------------------------------------------------------


def test_profile_override_is_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, {
        "profiles": {
            "defaults": {"font": {"face": fonts.FAMILY}},
            "list": [
                {"name": "PowerShell",
                 "font": {"face": "Cascadia Mono", "size": 10}},
                {"name": "cmd"},
            ],
        },
    })
    ok, message = _run(settings, monkeypatch)
    assert ok
    assert "1 profile(s)" in message
    data = json.loads(settings.read_text(encoding="utf-8"))
    power_shell = data["profiles"]["list"][0]
    assert power_shell["font"]["face"] == fonts.FAMILY
    assert power_shell["font"]["size"] == 10
    cmd = data["profiles"]["list"][1]
    assert "font" not in cmd
    assert data["profiles"]["defaults"]["font"]["face"] == fonts.FAMILY


def test_no_overrides_and_matching_defaults_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = json.dumps({
        "profiles": {
            "defaults": {"font": {"face": fonts.FAMILY}},
            "list": [{"name": "cmd"}],
        },
    })
    settings = tmp_path / "settings.json"
    settings.write_text(raw, encoding="utf-8")
    ok, message = _run(settings, monkeypatch)
    assert ok
    assert "already uses" in message
    assert settings.read_text(encoding="utf-8") == raw
    assert not (tmp_path / "settings.json.yate-bak").exists()


def test_defaults_are_set_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, {
        "profiles": {"list": [{"name": "cmd"}]},
    })
    ok, _ = _run(settings, monkeypatch)
    assert ok
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["profiles"]["defaults"]["font"]["face"] == fonts.FAMILY


def test_legacy_string_font_schema_is_upgraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, {
        "profiles": {
            "defaults": {"font": "Cascadia Mono"},
            "list": [{"name": "PowerShell", "font": "Cascadia Mono"}],
        },
    })
    ok, message = _run(settings, monkeypatch)
    assert ok
    assert "1 profile(s)" in message
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["profiles"]["defaults"]["font"]["face"] == fonts.FAMILY
    assert data["profiles"]["list"][0]["font"]["face"] == fonts.FAMILY


# --- backup -----------------------------------------------------------------


def test_backup_is_left_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, {
        "profiles": {
            "defaults": {"font": {"face": "Cascadia Mono"}},
        },
    })
    ok, _ = _run(settings, monkeypatch)
    assert ok
    backup = tmp_path / "settings.json.yate-bak"
    assert backup.is_file()
    assert json.loads(backup.read_text(encoding="utf-8")) == {
        "profiles": {"defaults": {"font": {"face": "Cascadia Mono"}}},
    }
