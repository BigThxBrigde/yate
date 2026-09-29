"""Full-screen overlay flows: help, manual, changelog, palettes, screensaver.

Extracted from :mod:`yate.editor` (review 20260926 #5).  Every overlay is
pushed through :meth:`OverlayController.push`, which also clears the stale
bottom message (the prompt line is hidden behind the overlay; a leftover
"saved ..." note would reappear on close and read like missing feedback).
Like :class:`~yate.completion.CompletionController` this module is
constructed by the editor and never imports upward.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from textual.app import App
from textual.screen import Screen

from yate.config import YateConfig
from yate.editor_sprites.characters import character_names
from yate.editor_view.commandline import PromptBar
from yate.editor_view.manual import MarkdownDocScreen
from yate.editor_view.modals import HelpScreen
from yate.editor_view.palette import PaletteScreen
from yate.editor_view.screensaver import ScreensaverScreen
from yate.keymaps.registry import KeymapSet
from yate.registries import ActionRegistry, CommandRegistry
from yate.services.workspace import Workspace


class OverlayController:
    """Pushes the editor's full-screen overlays and keeps them consistent."""

    def __init__(
        self,
        app: App[Any],
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
        self.app = app
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

    def push(
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
        self.app.push_screen(screen, callback=callback)

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
        if not self._mounted() or isinstance(self.app.screen, MarkdownDocScreen):
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
        if isinstance(self.app.screen, ScreensaverScreen):
            self.app.pop_screen()
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
