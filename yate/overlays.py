"""Full-screen overlay flows: help, manual, changelog, palettes, screensaver.

Extracted from :mod:`yate.editor` (review 20260926 #5).  Every overlay is
pushed through :meth:`OverlayFlows.push`, which also clears the stale
bottom message (the prompt line is hidden behind the overlay; a leftover
"saved ..." note would reappear on close and read like missing feedback).
Like :class:`~yate.completion.CompletionFlows` this module is
constructed by the editor and never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from textual.screen import Screen

from yate.config import YateConfig
from yate.editor_core.document import Document
from yate.editor_sprites.characters import character_names
from yate.editor_view.commandline import PromptBar
from yate.editor_view.diffview import MAX_DIFF_LINES, DiffScreen
from yate.editor_view.manual import MarkdownDocScreen
from yate.editor_view.modals import HelpScreen
from yate.editor_view.palette import PaletteScreen
from yate.editor_view.screensaver import ScreensaverScreen
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.workspace import Workspace


class OverlayFlows:
    """Pushes the editor's full-screen overlays and keeps them consistent."""

    def __init__(  # noqa: Any - current_screen query returns any Textual Screen
        self,
        push_screen: Callable[..., object],
        pop_screen: Callable[[], object],
        current_screen: Callable[[], Screen[Any]],
        config: YateConfig,
        keymaps: KeymapSet,
        commands: CommandRegistry,
        actions: ActionRegistry,
        workspace: Workspace,
        prompt: PromptBar,
        message: Callable[[str, str], None],
        mounted: Callable[[], bool],
        open_path: Callable[[Path], None],
        focus_editor: Callable[[], None],
        execute_action: Callable[[str], bool],
        run_command: Callable[[str], None],
        refresh: Callable[[], None],
    ) -> None:
        # Screen-stack verbs and the top-screen query, injected as bound
        # methods / callables by the editor (no App handle is held here).
        self._push_screen = push_screen
        self._pop_screen = pop_screen
        self._current_screen = current_screen
        self.config = config
        self.keymaps = keymaps
        self.commands = commands
        self.actions = actions
        self.workspace = workspace
        self.prompt = prompt
        self._message = message
        self._mounted = mounted
        self._open_path = open_path
        self._focus_editor = focus_editor
        self._execute_action = execute_action
        self._run_command = run_command
        self._refresh = refresh

    def push(  # noqa: Any - any Textual screen, callback payload untyped
        self,
        screen: Screen[Any],
        callback: Callable[[Any], None] | None = None,
    ) -> None:
        """Push a full-screen overlay, clearing the stale bottom message first.

        The prompt/message line is hidden behind the overlay while it is up,
        so reset it to the idle hint now; otherwise the previous command's
        message (e.g. "saved …") would reappear, untouched, once the overlay
        closes -- looking like the overlay command itself had no feedback.
        """
        self.prompt.idle()
        self._push_screen(screen, callback=callback)

    def show_help(self) -> None:
        """Open the keybinding reference overlay."""
        if self._mounted():
            self.push(HelpScreen(self.keymaps, self.commands))

    def show_manual(self, lang: str = "en") -> None:
        """Open the bundled user manual, rendered as read-only markdown."""
        self._open_doc(kind="manual", lang=lang, title="user manual")

    def show_changelog(self, lang: str = "en") -> None:
        """Open the bundled bilingual changelog viewer."""
        self._open_doc(kind="changelog", lang=lang, title="changelog")

    def _open_doc(self, *, kind: str, lang: str, title: str) -> None:
        """Push a markdown document screen unless one is already up."""
        if not self._mounted() or isinstance(self._current_screen(), MarkdownDocScreen):
            return
        self.push(MarkdownDocScreen(kind=kind, lang=lang, title=title))

    def open_file_palette(self) -> None:
        """Quick file open: fuzzy palette over the workspace files (ctrl+p)."""
        if self._mounted():
            self.push(self._palette("files"))

    def open_command_palette(self) -> None:
        """Command palette: fuzzy search over commands (alt+shift+p)."""
        if self._mounted():
            self.push(self._palette("commands"))

    def open_diff(self, paths: list[Path]) -> None:
        """Open the two- or three-way diff overlay for *paths*.

        Mode is derived from the count (2 -> 2way, 3 -> 3way with the
        base/local/remote order).  Missing, non-text, unreadable or
        oversized files are refused on the message line; the screen never
        opens half-configured.
        """
        if not self._mounted():
            return
        if isinstance(self._current_screen(), DiffScreen):
            self._message("diff view is already open", "info")
            return
        if len(paths) not in (2, 3):
            self._message("usage: :diff [--3way] FILE1 FILE2 [FILE3]", "warn")
            return
        for path in paths:
            # is_file(), not exists(): a directory wearing a text suffix
            # would pass the suffix check and crash Document.open with
            # IsADirectoryError (no try/except around command actions).
            if not path.is_file():
                self._message(f"no such file: {path}", "warn")
                return
            if not Workspace.is_text_file(path):
                self._message(f"not a text file: {path.name}", "warn")
                return
        try:
            docs = [Document.open(path) for path in paths]
        except OSError as exc:
            # the file vanished / was locked after the is_file() check
            self._message(f"cannot open file: {exc}", "warn")
            return
        for doc in docs:
            if doc.buffer.line_count > MAX_DIFF_LINES:
                self._message(
                    f"file too large for diff view: {doc.name}"
                    f" (>{MAX_DIFF_LINES} lines)",
                    "warn",
                )
                return
        labels = (
            ["base", "local", "remote"] if len(docs) == 3 else ["left", "right"]
        )
        self.push(
            DiffScreen(
                docs,
                mode="3way" if len(docs) == 3 else "2way",
                keymaps=self.keymaps,
                labels=labels,
            )
        )

    def _palette(self, mode: str) -> PaletteScreen:
        """Build the palette screen for *mode* (``files`` / ``commands``)."""
        return PaletteScreen(
            mode,
            workspace=self.workspace,
            commands=self.commands,
            actions=self.actions,
            open_path=self._open_path,
            focus_editor=self._focus_editor,
            execute_action=self._execute_action,
            run_command=self._run_command,
            refresh=self._refresh,
            preview=self.config.file_preview,
        )

    def toggle_screensaver(self) -> None:
        """Enter or leave the full-terminal idle screensaver.

        While the screensaver is up this pops it; otherwise ``enable =
        False`` only reports on the message line.  A configured
        ``characters`` whitelist that matches no roster entry refuses to
        start too (every name was already reported at startup) -- falling
        back to the whole roster would silently betray the explicit
        whitelist.  A real entry filters the rc names against the roster
        and pushes the overlay; an unconfigured whitelist (empty tuple)
        means the whole roster.  The idle poll re-checks the screen type
        before calling, so this pop branch only serves the direct action
        paths (palette, keys).
        """
        if isinstance(self._current_screen(), ScreensaverScreen):
            self._pop_screen()
            return
        if not self.config.screen_saver.enable:
            self._message("screensaver disabled (screen_saver.enable = False)",
                          "info")
            return
        configured = self.config.screen_saver.characters
        known = set(character_names())
        if configured:
            wanted = tuple(name for name in configured if name in known)
            if not wanted:
                self._message(
                    "screensaver: no valid screen_saver.characters entry", "info"
                )
                return
        else:
            wanted = ()
        self.push(
            ScreensaverScreen(
                wanted or character_names(),
                self.config.screen_saver.switch,
                self.config.screen_saver.dist_bounds,
            )
        )
