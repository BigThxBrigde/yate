"""The yate application: the Textual shell that hosts the editor.

:class:`YateApp` is deliberately thin: it owns the Textual lifecycle (theme
bridge, CSS, mount/unmount, key forwarding) and nothing else.  Every editor
operation lives on :class:`~yate.editor.Editor`, which the shell builds and
forwards to; the built-in action / command tables are loaded here too (the
table modules import the editor, so the editor must not import them back).
"""

from __future__ import annotations

import logging
import sys
import time
from importlib.resources import files
from pathlib import Path
from typing import override

from textual import events
from textual.app import App, ComposeResult
from textual.driver import Driver
from textual.events import Key
from textual.logging import TextualHandler

from yate import __version__
from yate.actions import populate
from yate.commands import register_commands
from yate.config import YateConfig
from yate.editor import Editor
from yate.editor_sprites.characters import character_names
from yate.editor_view import theme
from yate.editor_view.screensaver import ScreensaverScreen
from yate.keyproto.legacy import textual_key_to_raw
from yate.logs import LOGGER_NAME, tracing
from yate.services.idle_tracker import IdleTracker

# `textual_key_to_raw` lives in the L0 keyproto leaf (no import cycles) and
# is re-exported here for convenience/tests.
__all__ = ["textual_key_to_raw", "YateApp"]

log = tracing.get_logger(__name__)


def _load_app_css() -> str:
    """Read the app-level stylesheet packaged at ``yate/resources/app.tcss``.

    The shell's CSS is a bundled resource rather than an inline literal so it
    gets editor syntax highlighting and ships through the same packaging
    channels as every other file under ``yate/resources`` (hatchling wheel and
    both PyInstaller specs already collect that directory whole).  An
    unreadable resource means a broken installation: fail fast at import time
    with an actionable message instead of a confusing stylesheet error later.
    """
    try:
        return files("yate.resources").joinpath("app.tcss").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "bundled resource yate/resources/app.tcss could not be read; "
            "the yate installation is broken"
        ) from exc


class _TracingGatedTextualHandler(TextualHandler):
    """Devtools bridge that forwards records only while tracing is on (R12).

    Tracing is the single switch for yate diagnostics: while it is off, no
    record may reach the devtools console either.  The gate is needed at the
    handler (not the logger) because the unconfigured ``yate`` logger
    inherits the root logger's WARNING level -- WARNING+ records would flow
    to every attached handler, devtools included.
    """

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if not tracing.is_enabled():
            return
        super().emit(record)


class YateApp(App[None]):
    """The yate Textual application: theme bridge, CSS, lifecycle, keys."""

    # ctrl+p is yate's own command prompt -- disable Textual's palette.
    ENABLE_COMMAND_PALETTE = False

    #: R12 devtools bridge, mounted in :meth:`on_mount` and detached by
    #: identity in :meth:`on_unmount`; ``None`` while not mounted.
    _devtools_bridge: logging.Handler | None = None

    #: Idle-input tracker for the screensaver trigger; ``None`` while
    #: ``screen_saver.enable`` is off.  Poked from :meth:`on_event`, polled
    #: once a second from :meth:`on_mount`.  Read tests through the
    #: :attr:`idle_tracker` property; this attribute stays private.
    _idle: IdleTracker | None = None

    @property
    def idle_tracker(self) -> IdleTracker | None:
        """The active idle tracker, or ``None`` when the screensaver is off."""
        return self._idle

    @override
    def get_driver_class(self) -> type[Driver]:
        """Pick the chord-aware driver on Windows unless yaterc opts out.

        The stock Windows driver reduces every key record to its character,
        losing the virtual key and modifier state -- ctrl+digit never arrives
        and ctrl+`/ctrl+space collapse into one NUL byte.  The chord driver
        synthesizes canonical key names from the console records instead
        (headless/pilot runs are unaffected: they request HeadlessDriver
        explicitly).  ``key_protocol = "legacy"`` in yaterc restores the
        stock driver; non-Windows platforms keep Textual's platform default.
        """
        if sys.platform == "win32" and self.config.key_protocol != "legacy":
            from yate.keyproto.driver_windows import YateWindowsDriver

            return YateWindowsDriver
        return super().get_driver_class()

    CSS = _load_app_css()

    def __init__(
        self,
        target: str | Path | None = None,
        *,
        keymap: str | None = None,
        theme_name: str | None = None,
        config: YateConfig | None = None,
        readonly: bool = False,
        ext_files: list[str | Path] | None = None,
        ext_dirs: list[str | Path] | None = None,
    ) -> None:
        # self.config must exist before super().__init__(): App.__init__
        # resolves the driver class, which consults config.key_protocol.
        self.config = config if config is not None else YateConfig()
        super().__init__()
        self.title = f"yate {__version__}"

        # The color theme is process-global state (like vim's colorscheme).
        # An explicit selection (--theme) wins over the yaterc option.
        wanted_theme = theme_name if theme_name is not None else self.config.theme
        try:
            theme.set_theme(wanted_theme)
            log.debug("theme set: %s", wanted_theme)
        except KeyError:
            log.warning("unknown theme: %s", wanted_theme)
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
            log.warning(
                "theme '%s' has no usable bridge; falling back to mocha",
                theme.active().name,
            )
            self.config.errors.append(
                f"theme '{theme.active().name}' has no usable bridge; "
                f"falling back to mocha"
            )
            theme.set_theme("mocha")
            self.theme = theme.textual_theme_name("mocha")
        else:
            self.theme = wanted_textual

        # Idle screensaver trigger: input activity pokes the tracker (see
        # on_event) and a once-a-second poll in on_mount starts the
        # screensaver when the configured interval elapses.  Unknown rc
        # character names are reported here, before the Editor snapshot of
        # ``config.errors`` so they reach the startup warning banner like
        # every other yaterc error (config.py deliberately stays
        # sprite-pack free, so the roster is knowable only in the shell).
        self._idle = IdleTracker() if self.config.screen_saver.enable else None
        known = set(character_names())
        for name in self.config.screen_saver.characters:
            if name not in known:
                self.config.errors.append(
                    f"unknown screensaver character: {name!r}"
                )

        self.editor = Editor(
            self,
            self.config,
            target=target,
            keymap=keymap,
            readonly=readonly,
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

    def watch_theme(self, _theme: str) -> None:
        """Repaint the base screen background with the active yate palette.

        The screen is the one surface the shell owns; every other widget
        paints itself via the :mod:`yate.editor_view.theme` broadcast.
        """
        if self.screen_stack:
            self.screen.styles.background = theme.active().bg

    async def on_mount(self) -> None:
        # R12: mirror tracing records into the Textual devtools console so
        # no yate module ever needs the devtools channel (``app.log`` /
        # widget ``self.log``) directly -- this bridge is the only sanctioned
        # path.  Mounted here (not __init__) so the handler follows the app
        # lifecycle, and detached by identity in on_unmount so concurrent
        # app instances never strip each other's bridge.
        yate_root = logging.getLogger(LOGGER_NAME)
        if self._devtools_bridge is not None:
            # Defensive: a remount without an unmount would otherwise leak
            # the previous handler.
            yate_root.removeHandler(self._devtools_bridge)
        self._devtools_bridge = _TracingGatedTextualHandler(
            stderr=False, stdout=False
        )
        yate_root.addHandler(self._devtools_bridge)
        log.info("app mounted: theme=%s version=%s", theme.active().name, __version__)
        # watch_theme skips pre-mount assignments (no screen yet); paint once
        # here so the startup screen background matches the active palette.
        self.screen.styles.background = theme.active().bg
        self.set_interval(1.0, self.poll_idle)
        await self.editor.on_mount()

    async def on_unmount(self) -> None:
        # Detach the R12 bridge by identity (see on_mount): removing only
        # our own handler keeps a concurrently mounted app's bridge intact.
        if self._devtools_bridge is not None:
            logging.getLogger(LOGGER_NAME).removeHandler(self._devtools_bridge)
            self._devtools_bridge = None
        log.debug("app unmount")
        await self.editor.on_unmount()

    @override
    async def on_event(self, event: events.Event) -> None:
        """Poke the idle tracker on every input event, then dispatch normally.

        ``App.on_event`` sees every Key / Mouse record before the focused
        widget does -- including records a widget then consumes -- which
        makes it the only reliable "user is active" probe.  Only
        ``InputEvent`` subclasses count as activity; every event continues
        through the normal dispatch either way.
        """
        if self._idle is not None and isinstance(event, events.InputEvent):
            self._idle.poke()
        await super().on_event(event)

    def poll_idle(self) -> None:
        """Start the idle screensaver once ``screen_saver.interval`` elapses.

        Public so tests can drive the poll deterministically instead of
        waiting on the real one-second interval.  (Named to avoid Textual's
        own ``MessagePump.check_idle``, which this must not shadow.)  The
        poll keeps firing while no input arrives, so it must skip when the
        screensaver is already up: otherwise the toggle action would push
        and immediately pop in a one-second loop, and a manually started
        screensaver would never survive continued idle.  (The registered
        ``toggle_screensaver`` re-checks the screen type too, which keeps
        the palette / extension paths safe the same way.)
        """
        if self._idle is None or self.config.screen_saver.interval <= 0:
            return
        if isinstance(self.screen, ScreensaverScreen):
            return
        if self._idle.due(time.monotonic(), self.config.screen_saver.interval):
            self.editor.execute_action("toggle_screensaver")

    def on_key(self, event: Key) -> None:
        """Fallback routing: keys not consumed by a focused widget."""
        log.debug("key fallback: %s", event.key)
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
        log.debug("quit via registry")
        self.editor.execute_action("quit")
