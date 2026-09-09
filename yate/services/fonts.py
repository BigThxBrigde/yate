"""Bundled Nerd Font support: detection, user-level install, terminal setup.

yate ships FiraCode Nerd Font Mono (OFL license, see
``yate/resources/fonts/FiraCodeNerdFont-LICENSE.txt``) inside the package.

A terminal program cannot choose its own font -- the terminal emulator does
that.  So this module provides the full fallback chain:

1. :func:`bundled_font_files`  -- the TTFs shipped with yate
2. :func:`find_installed_nerd_fonts` -- scan the OS font registry
3. :func:`install_bundled_fonts` -- per-user install (NO administrator needed)
4. :func:`configure_windows_terminal` -- point Windows Terminal at the font

Everything is idempotent and never touches system-wide locations.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, cast

FAMILY = "FiraCode Nerd Font Mono"

# Win32 constants for the font-change broadcast (SendModuleMessage family).
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D
SMTO_ABORTIFHUNG = 0x0002

# Registry value suffix for TrueType fonts on Windows.
_TTF_SUFFIX = " (TrueType)"


# ---------------------------------------------------------------- bundled

def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundled_font_files() -> list[Path]:
    """The TTF files shipped inside the yate package."""
    fonts_dir = package_root() / "resources" / "fonts"
    return sorted(fonts_dir.glob("*.ttf")) if fonts_dir.is_dir() else []


# ------------------------------------------------------------- detection

@dataclass
class FontStatus:
    has_nerd_font: bool
    installed_fonts: list[str] = field(default_factory=list[str])
    terminal: str = "unknown"
    detail: str = ""


def _scan_windows_registry() -> list[str]:
    import winreg  # pylint: disable=import-outside-toplevel; Windows only

    names: list[str] = []
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    ]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    if "nerd" in name.lower() or "nerd" in str(value).lower():
                        names.append(name)
                    i += 1
        except OSError:
            continue
    return names


def _scan_fontconfig() -> list[str]:
    """Best-effort fc-list scan on macOS/Linux."""
    try:
        out = subprocess.run(
            ["fc-list", "--format=%{family}\n"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout
        return sorted({fam for fam in out.splitlines() if "nerd" in fam.lower()})
    except (OSError, subprocess.SubprocessError):
        return []


def find_installed_nerd_fonts() -> list[str]:
    """Return display names of installed Nerd Fonts (empty list if none)."""
    if sys.platform == "win32":
        return _scan_windows_registry()
    return _scan_fontconfig()


def detect_terminal() -> str:
    if os.environ.get("WT_SESSION"):
        return "windows_terminal"
    prog = os.environ.get("TERM_PROGRAM", "")
    if "vscode" in prog.lower():
        return "vscode"
    if "iterm" in prog.lower():
        return "iterm2"
    if "apple_terminal" in prog.lower() or "terminal.app" in prog.lower():
        return "apple_terminal"
    if sys.platform == "win32":
        return "conhost"
    return "unknown"


def font_status() -> FontStatus:
    installed = find_installed_nerd_fonts()
    terminal = detect_terminal()
    has = bool(installed)
    detail = ""
    if has:
        detail = f"found Nerd Font(s): {', '.join(installed[:3])}"
    else:
        detail = "no Nerd Font detected -- run 'yate --install-font' or ':font'"
    return FontStatus(
        has_nerd_font=has, installed_fonts=installed, terminal=terminal, detail=detail
    )


# --------------------------------------------------------------- install

@dataclass
class InstallResult:
    ok: bool
    installed: list[str] = field(default_factory=list[str])
    skipped: list[str] = field(default_factory=list[str])
    message: str = ""


def _broadcast_font_change_windows() -> None:
    """Notify running applications that the font list changed (best effort)."""
    try:
        import ctypes  # pylint: disable=import-outside-toplevel; Windows only

        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 1000, None
        )
    except Exception:
        pass


def _register_windows_user_font(fonts_dir: Path) -> tuple[list[str], list[str]]:
    """Copy bundled TTFs to the per-user font dir and register in HKCU."""
    import winreg  # Windows only

    installed: list[str] = []
    skipped: list[str] = []
    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"

    for ttf in bundled_font_files():
        dest = fonts_dir / ttf.name
        if not dest.exists():
            shutil.copy2(ttf, dest)

        # The registry value name is "<family> <style> (TrueType)"; derive the
        # friendly style from the file name, e.g. FiraCodeNerdFontMono-Bold.
        stem = ttf.stem  # FiraCodeNerdFontMono-Bold
        style = stem.split("-", 1)[1].replace("SemiBold", "Semi Bold") if "-" in stem else "Regular"
        value_name = f"{FAMILY} {style}{_TTF_SUFFIX}"

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            try:
                existing, _ = winreg.QueryValueEx(key, value_name)
            except OSError:
                existing = None
            if existing != ttf.name:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, ttf.name)
                installed.append(ttf.name)
            else:
                skipped.append(ttf.name)

    _broadcast_font_change_windows()
    return installed, skipped


def _install_unix() -> tuple[list[str], list[str]]:
    installed: list[str] = []
    skipped: list[str] = []
    fonts_dir = Path.home() / ".local" / "share" / "fonts" / "yate"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for ttf in bundled_font_files():
        dest = fonts_dir / ttf.name
        if dest.exists():
            skipped.append(ttf.name)
        else:
            shutil.copy2(ttf, dest)
            installed.append(ttf.name)
    if shutil.which("fc-cache"):
        # 等价于原来的 os.system：同一条 shell 命令（~ 展开与输出重定向
        # 交给 /bin/sh 处理），忽略退出码、fire-and-forget
        subprocess.run(
            "fc-cache -f ~/.local/share/fonts >/dev/null 2>&1",
            shell=True,
            check=False,
        )
    return installed, skipped


def install_bundled_fonts() -> InstallResult:
    """Install the bundled font for the current user (no admin required).

    Idempotent: already-present files/registry entries are reported as
    skipped.
    """
    files = bundled_font_files()
    if not files:
        return InstallResult(False, message="no bundled fonts found in the package")

    try:
        if sys.platform == "win32":
            fonts_dir = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            installed, skipped = _register_windows_user_font(fonts_dir)
        else:
            installed, skipped = _install_unix()
    except Exception as exc:  # environment issues must not crash the editor
        return InstallResult(False, message=f"font install failed: {type(exc).__name__}: {exc}")

    parts = [f"installed {len(installed)} font file(s) into your user font directory"]
    if skipped:
        parts.append(f"{len(skipped)} already present")
    parts.append("restart your terminal if icons do not appear")
    return InstallResult(True, installed=installed, skipped=skipped, message="; ".join(parts))


# ------------------------------------------------- Windows Terminal setup

def windows_terminal_settings_path() -> Optional[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    packages = Path(local) / "Packages"
    for candidate in packages.glob(
        "Microsoft.WindowsTerminal*_8wekyb3d8bbwe/LocalState/settings.json"
    ):
        if candidate.exists():
            return candidate
    return None


def configure_windows_terminal(family: str = FAMILY) -> tuple[bool, str]:
    """Set the default font face in Windows Terminal (with a backup).

    Returns ``(changed, message)``.  Leaves a ``settings.json.yate-bak``
    backup next to the settings file.
    """
    settings = windows_terminal_settings_path()
    if settings is None:
        return False, "Windows Terminal settings.json not found"

    try:
        raw = settings.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read settings.json: {exc}"

    # json.loads 返回 Any：逐级收窄为 dict[str, Any]，避免 Unknown 扩散
    profiles = cast(dict[str, Any], data.setdefault("profiles", {}))
    defaults = cast(dict[str, Any], profiles.setdefault("defaults", {}))
    # font 旧版 schema 允许是字符串，保留原始 object 做运行时类型判断
    font_value: object = defaults.setdefault("font", {})
    font = cast(dict[str, Any], font_value)

    current: object = font.get("face") if isinstance(font_value, dict) else font_value
    if current == family:
        return True, f"Windows Terminal already uses {family}"

    try:
        backup = settings.with_suffix(".json.yate-bak")
        if not backup.exists():
            backup.write_text(raw, encoding="utf-8")
        font["face"] = family
        settings.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        return False, f"cannot write settings.json: {exc}"

    return True, f"Windows Terminal default font set to {family} (backup: {backup.name})"


def ensure_font(*, configure_terminal: bool = True) -> FontStatus:
    """Install the bundled font if no Nerd Font is present.

    Returns the resulting :class:`FontStatus`.  Used by ``yate --install-font``
    and the ``:font`` ex command.
    """
    status = font_status()
    if not status.has_nerd_font:
        result = install_bundled_fonts()
        status.detail = result.message
        status.has_nerd_font = bool(find_installed_nerd_fonts())
    if configure_terminal and status.terminal == "windows_terminal" and status.has_nerd_font:
        _, msg = configure_windows_terminal()
        status.detail = f"{status.detail}; {msg}"
    return status
