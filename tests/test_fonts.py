"""Tests for the bundled Nerd Font service (yate.services.fonts).

The registry is never touched for real: writing font entries into the HKCU of
the machine running the tests would be destructive and unrepeatable, so
:class:`_FakeWinreg` is inserted into ``sys.modules`` and the Windows-only code
paths run identically on both CI legs.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Optional, cast

import pytest

from yate.services import fonts


def _private(name: str) -> Any:
    """Reach a module-private helper on purpose (they carry the logic)."""
    return getattr(fonts, name)


class _FakeKey:
    """Just enough of a winreg key: a context manager over a value store."""

    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    def __enter__(self) -> "_FakeKey":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeWinreg(types.ModuleType):
    """In-memory stand-in for :mod:`winreg` (values keyed by hive)."""

    HKEY_LOCAL_MACHINE = 0x80000002
    HKEY_CURRENT_USER = 0x80000001
    REG_SZ = 1

    def __init__(self) -> None:
        super().__init__("winreg")
        self.stores: dict[int, dict[str, str]] = {}
        self.written: list[str] = []
        self.deleted: list[str] = []
        #: When set, DeleteValue refuses (an ACL or a locked hive).
        self.fail_delete = False

    def store(self, hive: int) -> dict[str, str]:
        """The value store of *hive*, created on first use."""
        return self.stores.setdefault(hive, {})

    def OpenKey(self, hive: int, path: str) -> _FakeKey:  # noqa: N802 - mirrors winreg
        if hive not in self.stores:
            raise FileNotFoundError(path)
        return _FakeKey(self.stores[hive])

    def CreateKey(self, hive: int, path: str) -> _FakeKey:  # noqa: N802
        return _FakeKey(self.store(hive))

    def EnumValue(self, key: _FakeKey, index: int) -> tuple[str, str, int]:  # noqa: N802
        items = list(key.store.items())
        if index >= len(items):
            raise OSError("no more values")
        name, value = items[index]
        return name, value, self.REG_SZ

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[str, int]:  # noqa: N802
        if name not in key.store:
            raise FileNotFoundError(name)
        return key.store[name], self.REG_SZ

    def SetValueEx(  # noqa: N802
        self, key: _FakeKey, name: str, reserved: int, kind: int, value: str
    ) -> None:
        key.store[name] = value
        self.written.append(name)

    def DeleteValue(self, key: _FakeKey, name: str) -> None:  # noqa: N802
        if self.fail_delete or name not in key.store:
            raise OSError(f"cannot delete {name}")
        del key.store[name]
        self.deleted.append(name)


class _SubprocessRecorder:
    """Records ``subprocess.run`` calls and replays a scripted stdout."""

    #: fonts.py catches this next to OSError, so the stand-in needs it too.
    SubprocessError = subprocess.SubprocessError

    def __init__(self, stdout: str = "", error: Optional[BaseException] = None) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []
        self.stdout = stdout
        self.error = error

    def run(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return types.SimpleNamespace(stdout=self.stdout, returncode=0)


def _module(**attributes: Any) -> Any:
    """A stub module object, cast so it can stand in for a real one."""
    return cast(Any, types.SimpleNamespace(**attributes))


@pytest.fixture
def fake_winreg(monkeypatch: pytest.MonkeyPatch) -> _FakeWinreg:
    """Make ``import winreg`` inside fonts.py resolve to the fake."""
    fake = _FakeWinreg()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


# --- bundled files and registry entries -------------------------------------


def test_bundled_font_files_lists_the_shipped_ttfs() -> None:
    """The package ships two OFL TTFs, reported in sorted order."""
    assert [f.name for f in fonts.bundled_font_files()] == [
        "JetBrainsMonoNerdFontMono-Bold.ttf",
        "JetBrainsMonoNerdFontMono-Regular.ttf",
    ]


def test_bundled_font_files_is_empty_without_a_fonts_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A package without resources/fonts reports nothing instead of raising."""
    monkeypatch.setattr(fonts, "package_root", lambda: tmp_path)
    assert fonts.bundled_font_files() == []


def test_expected_font_entries_map_each_style_to_a_full_path(tmp_path: Path) -> None:
    """Each TTF becomes "<family> <style> (TrueType)" -> its full path."""
    entries = _private("_expected_font_entries")(tmp_path)
    assert set(entries) == {
        f"{fonts.FAMILY} Bold (TrueType)",
        f"{fonts.FAMILY} Regular (TrueType)",
    }
    assert entries[f"{fonts.FAMILY} Bold (TrueType)"] == str(
        tmp_path / "JetBrainsMonoNerdFontMono-Bold.ttf"
    )


def test_expected_font_entries_expand_semibold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SemiBold is spelled with a space, as GDI reports the style."""
    ttf = tmp_path / "JetBrainsMonoNerdFontMono-SemiBold.ttf"
    ttf.write_bytes(b"")
    monkeypatch.setattr(fonts, "bundled_font_files", lambda: [ttf])
    assert list(_private("_expected_font_entries")(tmp_path)) == [
        f"{fonts.FAMILY} Semi Bold (TrueType)"
    ]


# --- detection --------------------------------------------------------------


def test_font_value_resolves_absolute_and_bare_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_winreg: _FakeWinreg
) -> None:
    """Absolute values must exist; bare names only resolve per-machine."""
    absolute = tmp_path / "Some.ttf"
    absolute.write_bytes(b"")
    system_fonts = tmp_path / "Windows" / "Fonts"
    system_fonts.mkdir(parents=True)
    (system_fonts / "arial.ttf").write_bytes(b"")
    monkeypatch.setenv("WINDIR", str(tmp_path / "Windows"))
    resolve = _private("_font_value_resolves")
    assert resolve(fake_winreg.HKEY_CURRENT_USER, str(absolute)) is True
    assert resolve(fake_winreg.HKEY_CURRENT_USER, str(tmp_path / "gone.ttf")) is False
    assert resolve(fake_winreg.HKEY_LOCAL_MACHINE, "arial.ttf") is True
    assert resolve(fake_winreg.HKEY_LOCAL_MACHINE, "gone.ttf") is False
    assert resolve(fake_winreg.HKEY_CURRENT_USER, "arial.ttf") is False


def test_scan_windows_registry_keeps_only_loadable_nerd_values(
    tmp_path: Path, fake_winreg: _FakeWinreg
) -> None:
    """Only Nerd Font values that resolve to a real file are reported."""
    real = tmp_path / "JetBrainsMonoNerdFontMono-Regular.ttf"
    real.write_bytes(b"")
    store = fake_winreg.store(fake_winreg.HKEY_CURRENT_USER)
    store["NerdFont Bold (TrueType)"] = str(real)
    store["NerdFont Ghost (TrueType)"] = str(tmp_path / "ghost.ttf")
    store["Cascadia Mono (TrueType)"] = "cascadia.ttf"
    assert _private("_scan_windows_registry")() == ["NerdFont Bold (TrueType)"]


def test_scan_windows_registry_ignores_a_missing_hive(fake_winreg: _FakeWinreg) -> None:
    """A hive that cannot be opened is skipped, the other one still scanned."""
    fake_winreg.store(fake_winreg.HKEY_LOCAL_MACHINE)["Some Nerd Font"] = "missing.ttf"
    assert _private("_scan_windows_registry")() == []


def test_scan_fontconfig_filters_and_sorts_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fc-list output is filtered for nerd families, deduplicated and sorted."""
    recorder = _SubprocessRecorder(
        stdout="JetBrainsMono Nerd Font\nJetBrainsMono Nerd Font\nCascadia Nerd\nDejaVu\n"
    )
    monkeypatch.setattr(fonts, "subprocess", recorder)
    assert _private("_scan_fontconfig")() == ["Cascadia Nerd", "JetBrainsMono Nerd Font"]
    assert recorder.calls[0][0][0] == ["fc-list", "--format=%{family}\n"]


def test_scan_fontconfig_survives_a_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host without fc-list reports no fonts instead of raising."""
    monkeypatch.setattr(fonts, "subprocess", _SubprocessRecorder(error=OSError("gone")))
    assert _private("_scan_fontconfig")() == []


def _detect(monkeypatch: pytest.MonkeyPatch, env: dict[str, str], platform: str) -> str:
    """Run detect_terminal with a scrubbed environment and a fake platform."""
    for name in ("WT_SESSION", "TERM_PROGRAM"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(fonts, "sys", _module(platform=platform))
    return fonts.detect_terminal()


@pytest.mark.parametrize(
    "env, platform, expected",
    [
        ({"WT_SESSION": "abc"}, "win32", "windows_terminal"),
        ({"TERM_PROGRAM": "vscode"}, "linux", "vscode"),
        ({"TERM_PROGRAM": "iTerm.app"}, "darwin", "iterm2"),
        ({"TERM_PROGRAM": "Apple_Terminal"}, "darwin", "apple_terminal"),
        ({"TERM_PROGRAM": "Terminal.app"}, "darwin", "apple_terminal"),
        ({}, "win32", "conhost"),
        ({}, "linux", "unknown"),
    ],
    ids=["wt", "vscode", "iterm", "apple", "terminal-app", "conhost", "plain"],
)
def test_detect_terminal_follows_env_then_platform(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], platform: str, expected: str
) -> None:
    """The environment decides first, the platform is only the fallback."""
    assert _detect(monkeypatch, env, platform) == expected


def test_find_installed_fonts_picks_the_platform_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows scans the registry, every other platform asks fontconfig."""
    seen: list[str] = []
    monkeypatch.setattr(
        fonts, "_scan_windows_registry", lambda: seen.append("win") or ["Win"]
    )
    monkeypatch.setattr(fonts, "_scan_fontconfig", lambda: seen.append("nix") or ["Nix"])
    monkeypatch.setattr(fonts, "sys", _module(platform="win32"))
    assert fonts.find_installed_nerd_fonts() == ["Win"]
    monkeypatch.setattr(fonts, "sys", _module(platform="linux"))
    assert fonts.find_installed_nerd_fonts() == ["Nix"]
    assert seen == ["win", "nix"]


def test_font_status_points_at_the_installers_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a Nerd Font the detail tells the user how to install one."""
    monkeypatch.setattr(fonts, "find_installed_nerd_fonts", list)
    monkeypatch.setattr(fonts, "detect_terminal", lambda: "conhost")
    status = fonts.font_status()
    assert status.has_nerd_font is False
    assert status.installed_fonts == []
    assert "--install-font" in status.detail


def test_font_status_summarises_the_first_three_fonts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With fonts present the detail lists up to three of them."""
    monkeypatch.setattr(fonts, "find_installed_nerd_fonts", lambda: ["a", "b", "c", "d"])
    monkeypatch.setattr(fonts, "detect_terminal", lambda: "vscode")
    status = fonts.font_status()
    assert status.has_nerd_font is True
    assert status.detail == "found Nerd Font(s): a, b, c"
    assert status.terminal == "vscode"


# --- install ----------------------------------------------------------------


def _unix_shutil(which: Optional[str] = None, copy2: Any = shutil.copy2) -> Any:
    """A shutil stand-in: real copying, scripted ``which``."""

    def _which(_name: str) -> Optional[str]:
        return which

    return _module(copy2=copy2, which=_which)


def test_install_unix_copies_then_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """The POSIX install copies the bundled TTFs under ~/.local/share/fonts."""
    monkeypatch.setattr(fonts, "shutil", _unix_shutil())
    target = Path.home() / ".local" / "share" / "fonts" / "yate"
    installed, skipped = _private("_install_unix")()
    assert installed == [
        "JetBrainsMonoNerdFontMono-Bold.ttf",
        "JetBrainsMonoNerdFontMono-Regular.ttf",
    ]
    assert skipped == []
    assert (target / "JetBrainsMonoNerdFontMono-Regular.ttf").is_file()
    installed_again, skipped_again = _private("_install_unix")()
    assert installed_again == []
    assert skipped_again == installed


def test_install_unix_refreshes_the_cache_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With fc-cache on PATH the font cache is refreshed without checking it."""
    recorder = _SubprocessRecorder()
    monkeypatch.setattr(fonts, "subprocess", recorder)
    monkeypatch.setattr(fonts, "shutil", _unix_shutil(which="/usr/bin/fc-cache"))
    _private("_install_unix")()
    assert recorder.calls[0][0][0] == "fc-cache -f ~/.local/share/fonts >/dev/null 2>&1"
    assert recorder.calls[0][1]["shell"] is True


def test_install_bundled_fonts_reports_a_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No bundled TTFs means nothing to install, not an exception."""
    monkeypatch.setattr(fonts, "bundled_font_files", list)
    result = fonts.install_bundled_fonts()
    assert result.ok is False
    assert "no bundled fonts" in result.message


def test_install_bundled_fonts_is_idempotent_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second POSIX install reports the files as already present."""
    monkeypatch.setattr(fonts, "sys", _module(platform="linux"))
    monkeypatch.setattr(fonts, "shutil", _unix_shutil())
    first = fonts.install_bundled_fonts()
    assert first.ok is True
    assert len(first.installed) == 2
    assert "already present" not in first.message
    second = fonts.install_bundled_fonts()
    assert second.ok is True
    assert second.installed == []
    assert "2 already present" in second.message
    assert "restart your terminal" in second.message


def test_install_bundled_fonts_reports_environment_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken font directory is reported in the message, never raised."""
    monkeypatch.setattr(fonts, "sys", _module(platform="linux"))

    def _boom() -> tuple[list[str], list[str]]:
        raise PermissionError("read-only home")

    monkeypatch.setattr(fonts, "_install_unix", _boom)
    result = fonts.install_bundled_fonts()
    assert result.ok is False
    assert "PermissionError: read-only home" in result.message


def test_windows_install_registers_full_paths_and_sweeps_stale_values(
    tmp_path: Path, fake_winreg: _FakeWinreg
) -> None:
    """Per-user entries hold full paths; stale family values are removed."""
    fonts_dir = tmp_path / "Fonts"
    fonts_dir.mkdir()
    store = fake_winreg.store(fake_winreg.HKEY_CURRENT_USER)
    store[f"{fonts.FAMILY} Regular (TrueType)"] = "JetBrainsMonoNerdFontMono-Regular.ttf"
    store[f"{fonts.FAMILY} Reg (TrueType)"] = str(tmp_path / "truncated.ttf")
    store["Cascadia Mono (TrueType)"] = "cascadia.ttf"
    duplicate = fonts_dir / "JetBrainsMonoNerdFontMono-Regular_0.ttf"
    duplicate.write_bytes(b"explorer copy")

    installed, skipped = _private("_register_windows_user_font")(fonts_dir)

    assert installed == [
        "JetBrainsMonoNerdFontMono-Bold.ttf",
        "JetBrainsMonoNerdFontMono-Regular.ttf",
    ]
    assert skipped == []
    assert fake_winreg.deleted == [f"{fonts.FAMILY} Reg (TrueType)"]
    assert set(store) == {
        f"{fonts.FAMILY} Bold (TrueType)",
        f"{fonts.FAMILY} Regular (TrueType)",
        "Cascadia Mono (TrueType)",
    }
    assert store[f"{fonts.FAMILY} Bold (TrueType)"] == str(
        fonts_dir / "JetBrainsMonoNerdFontMono-Bold.ttf"
    )
    assert not duplicate.exists()  # the Explorer duplicate was swept

    installed_again, skipped_again = _private("_register_windows_user_font")(fonts_dir)
    assert installed_again == []
    assert skipped_again == installed


def test_windows_install_keeps_a_duplicate_it_cannot_remove(
    tmp_path: Path, fake_winreg: _FakeWinreg
) -> None:
    """An undeletable duplicate must not abort the install."""
    fonts_dir = tmp_path / "Fonts"
    fonts_dir.mkdir()
    blocker = fonts_dir / "JetBrainsMonoNerdFontMono-Bold_0.ttf"
    blocker.mkdir()  # a directory cannot be unlinked
    installed, _skipped = _private("_register_windows_user_font")(fonts_dir)
    assert installed == [
        "JetBrainsMonoNerdFontMono-Bold.ttf",
        "JetBrainsMonoNerdFontMono-Regular.ttf",
    ]
    assert blocker.is_dir()


def test_windows_install_steps_over_a_stale_value_it_cannot_delete(
    tmp_path: Path, fake_winreg: _FakeWinreg
) -> None:
    """A refused DeleteValue must not spin on the same registry slot."""
    fonts_dir = tmp_path / "Fonts"
    fonts_dir.mkdir()
    stale = f"{fonts.FAMILY} Old (TrueType)"
    fake_winreg.store(fake_winreg.HKEY_CURRENT_USER)[stale] = str(tmp_path / "old.ttf")
    fake_winreg.fail_delete = True
    installed, _skipped = _private("_register_windows_user_font")(fonts_dir)
    assert stale in fake_winreg.stores[fake_winreg.HKEY_CURRENT_USER]
    assert len(installed) == 2


def test_font_change_broadcast_is_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broadcast that fails is swallowed instead of breaking the install."""

    def _boom(*_args: Any) -> None:
        raise OSError("no window station")

    monkeypatch.setattr(
        ctypes,
        "windll",
        _module(user32=_module(SendMessageTimeoutW=_boom)),
        raising=False,
    )
    _private("_broadcast_font_change_windows")()  # must not raise


def test_install_bundled_fonts_uses_localappdata_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_winreg: _FakeWinreg
) -> None:
    """On Windows the target is %LOCALAPPDATA%/Microsoft/Windows/Fonts."""
    monkeypatch.setattr(fonts, "sys", _module(platform="win32"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = fonts.install_bundled_fonts()
    assert result.ok is True
    fonts_dir = tmp_path / "Microsoft" / "Windows" / "Fonts"
    assert sorted(p.name for p in fonts_dir.glob("*.ttf")) == [
        "JetBrainsMonoNerdFontMono-Bold.ttf",
        "JetBrainsMonoNerdFontMono-Regular.ttf",
    ]
    assert f"{fonts.FAMILY} Bold (TrueType)" in fake_winreg.written


# --- Windows Terminal settings path -----------------------------------------


def test_settings_path_is_none_without_localappdata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No LOCALAPPDATA means there is nothing to look for."""
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert fonts.windows_terminal_settings_path() is None


def test_settings_path_finds_the_store_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The existing settings.json inside the Store package is reported."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    state = tmp_path / "Packages" / "Microsoft.WindowsTerminal_8wekyb3d8bbwe" / "LocalState"
    state.mkdir(parents=True)
    settings = state / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    assert fonts.windows_terminal_settings_path() == settings


def test_settings_path_ignores_an_empty_package_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matching directory without settings.json is not reported."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (
        tmp_path / "Packages" / "Microsoft.WindowsTerminal_8wekyb3d8bbwe" / "LocalState"
    ).mkdir(parents=True)
    assert fonts.windows_terminal_settings_path() is None


# --- profile rewriting ------------------------------------------------------


def _settings(tmp: Path, data: dict[str, object]) -> Path:
    path = tmp / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _run(settings: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[bool, str]:
    monkeypatch.setattr(
        fonts, "windows_terminal_settings_path", lambda: settings
    )
    return fonts.configure_windows_terminal()


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
                {"name": "WSL", "font": {"size": 12}},
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
    # a profile that only sets a size inherits the family: left alone
    assert data["profiles"]["list"][2]["font"] == {"size": 12}
    assert data["profiles"]["defaults"]["font"]["face"] == fonts.FAMILY


def test_string_font_matching_the_family_needs_no_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A legacy string face that already matches is left as it is."""
    settings = _settings(tmp_path, {"profiles": {"defaults": {"font": fonts.FAMILY}}})
    ok, message = _run(settings, monkeypatch)
    assert ok
    assert "already uses" in message
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["profiles"]["defaults"]["font"] == fonts.FAMILY


def test_missing_windows_terminal_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No settings.json at all is reported as such."""
    monkeypatch.setattr(fonts, "windows_terminal_settings_path", lambda: None)
    ok, message = fonts.configure_windows_terminal()
    assert ok is False
    assert "not found" in message


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


def test_missing_settings_path_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settings file that is not there is reported, not raised."""
    ok, message = _run(tmp_path / "gone.json", monkeypatch)
    assert ok is False
    assert "cannot read settings.json" in message


def test_unparsable_settings_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settings.json that is not JSON is reported, not raised."""
    settings = tmp_path / "settings.json"
    settings.write_text("{ not json", encoding="utf-8")
    ok, message = _run(settings, monkeypatch)
    assert ok is False
    assert "cannot read settings.json" in message


def test_write_failure_keeps_the_backup_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing write leaves the backup behind and reports the error."""
    settings = _settings(
        tmp_path, {"profiles": {"defaults": {"font": {"face": "Cascadia Mono"}}}}
    )

    def _boom(*_args: Any, **_kwargs: Any) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(fonts, "json", _module(loads=json.loads, dumps=_boom))
    ok, message = _run(settings, monkeypatch)
    assert ok is False
    assert "cannot write settings.json: disk full" in message
    backup = tmp_path / "settings.json.yate-bak"
    assert json.loads(backup.read_text(encoding="utf-8")) == {
        "profiles": {"defaults": {"font": {"face": "Cascadia Mono"}}},
    }


def test_an_older_backup_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A backup from an earlier run survives the next configuration."""
    settings = _settings(
        tmp_path, {"profiles": {"defaults": {"font": {"face": "Cascadia Mono"}}}}
    )
    backup = tmp_path / "settings.json.yate-bak"
    backup.write_text("previous", encoding="utf-8")
    ok, _ = _run(settings, monkeypatch)
    assert ok
    assert backup.read_text(encoding="utf-8") == "previous"


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


# --- ensure_font ------------------------------------------------------------


def test_ensure_font_installs_when_none_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a Nerd Font the bundled one is installed and re-detected."""
    detected: list[list[str]] = [[], [f"{fonts.FAMILY} Regular"]]
    calls: list[str] = []

    def _install() -> fonts.InstallResult:
        calls.append("install")
        return fonts.InstallResult(True, message="installed 2 font file(s)")

    monkeypatch.setattr(fonts, "detect_terminal", lambda: "conhost")
    monkeypatch.setattr(fonts, "find_installed_nerd_fonts", lambda: detected.pop(0))
    monkeypatch.setattr(fonts, "install_bundled_fonts", _install)
    status = fonts.ensure_font(configure_terminal=False)
    assert calls == ["install"]
    assert status.has_nerd_font is True
    assert status.detail == "installed 2 font file(s)"


def test_ensure_font_configures_windows_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Nerd Font inside Windows Terminal also rewrites settings.json."""
    calls: list[str] = []
    monkeypatch.setattr(fonts, "detect_terminal", lambda: "windows_terminal")
    monkeypatch.setattr(fonts, "find_installed_nerd_fonts", lambda: [fonts.FAMILY])
    monkeypatch.setattr(
        fonts,
        "configure_windows_terminal",
        lambda: calls.append("config") or (True, "font set"),
    )
    status = fonts.ensure_font()
    assert calls == ["config"]
    assert status.detail.endswith("; font set")


def test_ensure_font_leaves_other_terminals_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Nerd Font outside Windows Terminal needs no settings rewrite."""
    calls: list[str] = []
    monkeypatch.setattr(fonts, "detect_terminal", lambda: "vscode")
    monkeypatch.setattr(fonts, "find_installed_nerd_fonts", lambda: [fonts.FAMILY])
    monkeypatch.setattr(
        fonts,
        "configure_windows_terminal",
        lambda: calls.append("config") or (True, ""),
    )
    assert fonts.ensure_font().has_nerd_font is True
    assert calls == []
