"""VS Code-style command palette and quick file open (fuzzy filtered modal).

Two modes share one widget:

* ``"files"`` (ctrl+p): fuzzy search over the workspace files, enter opens.
* ``"commands"`` (ctrl+shift+p): fuzzy search over ``:`` commands, enter runs.

The fuzzy matcher is a plain subsequence scorer (fzf-style): every query
character must appear in order; matches at word starts / path boundaries
score better than gap matches.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from yate.services.workspace import Workspace

from . import theme
from .icons import GEAR, icon_for_path

if TYPE_CHECKING:
    from yate.app import YateApp

#: maximum number of result rows rendered under the input
MAX_VISIBLE = 12


def fuzzy_match(query: str, target: str) -> Optional[tuple[int, list[int]]]:
    """Subsequence-match *query* against *target* (case insensitive).

    Returns ``(score, matched_indices)`` (lower score = better) or ``None``
    when the query is not a subsequence of the target.
    """
    if not query:
        return (0, [])
    q = query.lower()
    t = target.lower()
    matched: list[int] = []
    score = 0
    ti = 0
    for qi, qch in enumerate(q):
        # skip whitespace in the query (typing "ctrlp" matches "ctrl p")
        if qch.isspace():
            continue
        idx = t.find(qch, ti)
        if idx == -1:
            return None
        matched.append(idx)
        if idx == ti and qi > 0:
            score += 0  # consecutive: best
        elif idx == 0 or t[idx - 1] in "/\\._- ":
            score += 1  # word / path boundary start
        else:
            score += 2 + (idx - ti)  # gap penalty
        # exact-case bonus
        if target[idx] == query[qi]:
            score -= 1
        ti = idx + 1
    return (score, matched)


class PaletteScreen(ModalScreen[None]):
    """Fuzzy palette overlay for files (quick open) or commands."""

    BINDINGS = [
        ("escape", "dismiss", "close"),
        ("ctrl+c", "dismiss", "close"),
    ]

    DEFAULT_CSS = """
    PaletteScreen {
        align: center top;
    }
    PaletteScreen #palette {
        width: 70%;
        max-width: 90;
        height: 14;
        margin-top: 3;
        border: tall $primary;
        background: $surface;
        padding: 0 1;
    }
    PaletteScreen #palette-input {
        height: 1;
        border: none;
        background: $surface;
        padding: 0;
    }
    PaletteScreen #palette-results {
        height: 1fr;
        padding: 0;
        background: $surface;
    }
    """

    def __init__(self, yate: YateApp, mode: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.yate = yate
        self.mode = mode  # "files" | "commands"
        self._entries: list[tuple[str, str, Any]] = []  # (display, hint, payload)
        self._filtered: list[tuple[int, list[int], int]] = []  # (score, hits, idx)
        self._cursor = 0

    @property
    def filtered_count(self) -> int:
        """Number of rows currently visible after filtering."""
        return len(self._filtered)

    @property
    def cursor_index(self) -> int:
        """Index of the highlighted row within the filtered results."""
        return self._cursor

    # --------------------------------------------------------------- data

    def _build_entries(self) -> None:
        app = self.yate
        entries: list[tuple[str, str, Any]] = []
        if self.mode == "files":
            if app.workspace.root is not None:
                root = app.workspace.root
                paths = app.workspace.walk_files()
            else:
                root = Path.cwd()
                paths = _walk(root)
            for path in paths:
                try:
                    label = str(path.resolve().relative_to(root.resolve()))
                except ValueError:
                    label = path.name
                entries.append((label.replace("\\", "/"), "", path))
        else:
            for name in app.commands.names():
                entries.append((name, app.commands.describe(name), name))
        self._entries = entries

    def refilter(self, query: str) -> None:
        scored: list[tuple[int, list[int], int]] = []
        for i, (display, _hint, _payload) in enumerate(self._entries):
            match = fuzzy_match(query, display)
            if match is not None:
                score, hits = match
                scored.append((score, hits, i))
        scored.sort(key=lambda item: (item[0], self._entries[item[2]][0].lower()))
        self._filtered = scored[:MAX_VISIBLE]
        self._cursor = 0
        self._render_results()

    # -------------------------------------------------------------- render

    def _render_results(self) -> None:
        t = theme.active()
        results = self.query_one("#palette-results", Static)
        text = Text()
        if not self._filtered:
            text.append("  no matches", style=t.fg_dim)
            results.update(text)
            return
        for row, (_score, hits, idx) in enumerate(self._filtered):
            display, hint, _payload = self._entries[idx]
            selected = row == self._cursor
            bg = t.accent if selected else None
            base = f"bold {t.on_accent}" if selected else t.fg
            icon = (
                icon_for_path(display.rsplit("/", 1)[-1], False)
                if self.mode == "files"
                else GEAR
            )
            text.append(" ", style=f"on {bg}" if bg else "")
            text.append(icon + " ", style=(f"{t.on_accent} on {bg}") if selected else t.fg_dim)
            hit_set = set(hits)
            for ci, ch in enumerate(display):
                style = (
                    f"bold {t.on_accent} on {bg}"
                    if selected
                    else (f"bold {t.accent}" if ci in hit_set else base)
                )
                text.append(ch, style=style)
            if hint:
                pad = max(1, 30 - len(display))
                text.append(" " * pad, style=f"on {bg}" if bg else "")
                text.append(hint, style=(f"{t.panel} on {bg}") if selected else t.fg_dim)
            text.append("\n")
        results.update(text)

    # ------------------------------------------------------------- textual

    def compose(self) -> ComposeResult:
        with Vertical(id="palette"):
            placeholder = (
                "search files by name…" if self.mode == "files"
                else "type a command name…"
            )
            yield Input(placeholder=placeholder, id="palette-input")
            yield Static(id="palette-results")

    def on_mount(self) -> None:
        # Colors come from the DEFAULT_CSS design tokens ($surface/$primary),
        # which track Textual's dark/light mode; result rows use the active
        # Catppuccin palette via Rich styles.
        self._build_entries()
        self.refilter("")
        self.query_one("#palette-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "palette-input":
            self.refilter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "palette-input":
            return
        self._choose()

    def on_key(self, event: Key) -> None:
        if event.key in ("up", "ctrl+p"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor - 1) % len(self._filtered)
                self._render_results()
        elif event.key in ("down", "ctrl+n"):
            event.stop()
            event.prevent_default()
            if self._filtered:
                self._cursor = (self._cursor + 1) % len(self._filtered)
                self._render_results()

    # ------------------------------------------------------------- actions

    def _choose(self) -> None:
        if not self._filtered:
            return
        _score, _hits, idx = self._filtered[self._cursor]
        _display, _hint, payload = self._entries[idx]
        self.dismiss()
        if self.mode == "files":
            self.yate.open_path(payload)
            self.yate.focus_editor()
        else:
            self.yate.run_command(str(payload))


def _walk(root: Path, limit: int = 5000) -> list[Path]:
    """Fallback file walk (no workspace root set); mirrors Workspace logic."""
    ws = Workspace(root)
    return ws.walk_files(limit=limit)
