"""The yate application: the Textual shell that hosts the editor.

:class:`YateApp` is deliberately thin: it owns the Textual lifecycle (theme
bridge, CSS, mount/unmount, key forwarding) and nothing else.  Every editor
operation lives on :class:`~yate.editor.Editor`, which the shell builds and
forwards to; the built-in action / command tables are loaded here too (the
table modules import the editor, so the editor must not import them back).
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from textual.app import App, ComposeResult
from textual.events import Key

from yate import __version__
from yate.actions import populate
from yate.commands import register_commands
from yate.config import YateConfig
from yate.editor import Editor
from yate.editor_view import theme
from yate.editor_view.keys import textual_key_to_raw

# `textual_key_to_raw` lives in yate.editor_view.keys to avoid import cycles
# and is re-exported here for convenience/tests.
__all__ = ["textual_key_to_raw", "YateApp"]


class YateApp(App[None]):
    """The yate Textual application: theme bridge, CSS, lifecycle, keys."""

    # ctrl+p is yate's own command prompt -- disable Textual's palette.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #bottom-dock {
        dock: bottom;
        height: auto;
    }
    #bottom {
        height: 2;
    }
    #terminal-dock {
        height: 12;
        display: none;
    }
    #body {
        height: 1fr;
    }
    #sidebar {
        width: 34;
        min-width: 16;
        height: 1fr;
    }
    #sidebar-head {
        height: 1;
        padding: 0;
    }
    #explorer {
        height: 1fr;
    }
    #editor-col {
        width: 1fr;
        height: 1fr;
        layers: default lsp-popup;
    }
    #tabbar {
        height: 1;
        padding: 0;
    }
    #breadcrumbs {
        height: 1;
        padding: 0;
    }
    """

    def __init__(
        self,
        target: str | Path | None = None,
        *,
        keymap: str | None = None,
        theme_name: str | None = None,
        config: YateConfig | None = None,
        ext_files: list[str | Path] | None = None,
        ext_dirs: list[str | Path] | None = None,
    ) -> None:
        super().__init__()
        self.title = f"yate {__version__}"

        self.config = config if config is not None else YateConfig()
        # The color theme is process-global state (like vim's colorscheme).
        # An explicit selection (--theme) wins over the yaterc option.
        wanted_theme = theme_name if theme_name is not None else self.config.theme
        try:
            theme.set_theme(wanted_theme)
        except KeyError:
            self.config.errors.append(f"unknown theme: {wanted_theme!r}")
        # Bridge every yate theme into a Textual theme (``yate-<name>``) so
        # the app's design tokens always match the active yate palette and
        # every overlay (help, manual, changelog, palette, ...) is on-theme
        # with zero per-screen theme switching.  super().__init__() already
        # seeded Textual's built-in themes; we register the bridges before
        # assigning the reactive (its validator requires the theme to exist).
        for yt in theme.THEMES.values():
            try:
                self.register_theme(theme.to_textual_theme(yt))
            except Exception as exc:  # noqa: BLE001 - never fatal at startup
                self.config.errors.append(
                    f"yate theme '{yt.name}': {type(exc).__name__}: {exc}"
                )
        # Set the app's Textual theme to the bridge of the active yate theme;
        # fall back to yate-mocha if the selected theme's bridge is unusable
        # (the reactive validator would raise InvalidThemeError otherwise).
        wanted_textual = theme.textual_theme_name(theme.active().name)
        if self.get_theme(wanted_textual) is None:
            self.config.errors.append(
                f"theme '{theme.active().name}' has no usable bridge; "
                f"falling back to mocha"
            )
            theme.set_theme("mocha")
            self.theme = theme.textual_theme_name("mocha")
        else:
            self.theme = wanted_textual

        self.editor = Editor(
            self,
            self.config,
            target=target,
            keymap=keymap,
            ext_files=ext_files,
            ext_dirs=ext_dirs,
        )
        # The built-in tables are loaded by the shell (R7): the table modules
        # import the editor, so the editor must never import them back.
        populate(self.editor.actions, self.editor)
        register_commands(self.editor.commands, self.editor)

    @override
    def compose(self) -> ComposeResult:
        yield from self.editor.compose()

    async def on_mount(self) -> None:
        await self.editor.on_mount()

    async def on_unmount(self) -> None:
        await self.editor.on_unmount()

    def on_key(self, event: Key) -> None:
        """Fallback routing: keys not consumed by a focused widget."""
        if self.editor.handle_key(event):
            event.stop()
            event.prevent_default()

    @override
    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Provide defaults for the custom doc-hit CSS variables.

        The manual/changelog viewer references ``$doc-hit-background`` and
        ``$doc-hit-current-background`` in its CSS.  The bridged yate themes
        override these, but Textual's CSS parser needs a default value
        available at parse time for any theme that doesn't define them, so
        they are derived from the active yate theme's yellow accent.
        """
        t = theme.active()
        return {
            "doc-hit-background": f"{t.yellow} 12%",
            "doc-hit-current-background": f"{t.yellow} 40%",
        }

    @override
    async def action_quit(self) -> None:
        """Textual's ctrl+q priority binding — route through the registry.

        Dispatches the registered ``quit`` action (same path as the palette
        and extensions) instead of calling :meth:`Editor.quit` directly, so
        the registry entry is not dead weight and stays observable.
        """
        self.editor.execute_action("quit")
