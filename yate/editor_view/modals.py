"""Modal screens: help overlay and shell-command output."""

from __future__ import annotations

from typing import Protocol

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from yate.keymaps.base import KeyBinding, Keymap

from . import theme
from .icons import CHECK, KEYBOARD, TERMINAL, TIMES


class HelpHost(Protocol):
    """What :class:`HelpScreen` reads from its host application."""

    keymap_name: str

    @property
    def active_keymap(self) -> Keymap: ...

    def command_entries(self) -> list[tuple[str, str]]:
        """``(name, description)`` pairs of the ``:`` command table."""
        ...


class _OverlayScreen(ModalScreen[None]):
    """Base: dim the background, dismiss on esc / q / ctrl+c."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("q", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
    ]

    DEFAULT_CSS = """
    _OverlayScreen {
        align: center middle;
    }
    _OverlayScreen #overlay {
        width: 90%;
        height: 85%;
        border: tall $primary;
        background: $surface;
        padding: 1 2;
    }
    _OverlayScreen .hint {
        color: $text-muted;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="overlay"):
            yield Static(self._body(), id="overlay-body")
            yield Static(" press esc or q to close ", classes="hint")

    def _body(self) -> Text:  # pragma: no cover - overridden
        return Text("")


class HelpScreen(_OverlayScreen):
    """Full keybinding reference, grouped by category."""

    def __init__(self, host: HelpHost) -> None:
        super().__init__()
        self.host = host

    def _body(self) -> Text:
        t = theme.active()
        host = self.host
        text = Text()
        text.append(f"{KEYBOARD}  YATE — KEYBOARD REFERENCE\n",
                    style=f"bold {t.accent}")
        text.append(f"keymap: {host.keymap_name}    "
                    f"(toggle with ctrl+/ or :set keymap=vsc|vim)\n\n",
                    style=t.fg_muted)

        km = host.active_keymap
        groups: dict[str, list[KeyBinding]] = {}
        for binding in km.bindings:
            groups.setdefault(binding.category or "other", []).append(binding)

        for category, bindings in groups.items():
            text.append(f"  {category.upper()}\n", style=f"bold {t.accent2}")
            seen: set[str] = set()
            for b in bindings:
                key = b.key_label
                if key in seen:
                    continue
                seen.add(key)
                text.append("    ")
                text.append(key.ljust(16), style=t.green)
                text.append(b.description or str(b.action), style=t.fg_bright)
                text.append("\n")
            text.append("\n")

        # Keys intercepted outside the keymap dispatch, active in both keymaps.
        text.append("  GLOBAL KEYS\n", style=f"bold {t.accent2}")
        for key, desc in (
            ("ctrl+`", "Toggle the integrated terminal (bottom panel)"),
        ):
            text.append("    ")
            text.append(key.ljust(16), style=t.green)
            text.append(desc, style=t.fg_bright)
            text.append("\n")
        text.append("\n")

        text.append("  COMMANDS (prefix :)\n", style=f"bold {t.accent2}")
        for name, desc in host.command_entries():
            text.append("    ")
            text.append((":" + name).ljust(16), style=t.green)
            text.append(desc or "", style=t.fg_bright)
            text.append("\n")
        return text


class OutputScreen(_OverlayScreen):
    """Scrollable output of a shell command."""

    def __init__(self, title: str, output: str, returncode: int = 0) -> None:
        super().__init__()
        self._title = title
        self._output = output
        self._returncode = returncode

    @property
    def output_text(self) -> str:
        """Captured stdout/stderr of the finished shell command."""
        return self._output

    @property
    def exit_code(self) -> int:
        """Process exit code (``0`` = success)."""
        return self._returncode

    def _body(self) -> Text:
        t = theme.active()
        text = Text()
        glyph = CHECK if self._returncode == 0 else TIMES
        color = t.green if self._returncode == 0 else t.red
        text.append(f"{TERMINAL}  {self._title}\n", style=f"bold {t.accent}")
        text.append(f"{glyph} exit code {self._returncode}\n\n", style=f"bold {color}")
        text.append(self._output or "(no output)", style=t.fg_bright)
        return text
