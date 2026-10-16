"""Project-wide find & replace overlay screen (ctrl+h).

Pure L2: collaborators and callbacks are constructor-injected; searching
runs in a worker thread over :mod:`yate.editor_core.project_search`
primitives.  Replace policy follows the plan-c decision table: an open
document is edited in memory through a temporary
:class:`~yate.editor_core.SearchEngine` (stays dirty, undoable), a closed
file goes through read-modify-write on disk with the ``replace_lines``
no-change contract (same list object back means nothing was written).
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import override

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from yate.editor_core import BufferReadOnlyError, Document, SearchEngine
from yate.editor_core import project_search
from yate.editor_core.project_search import FileMatch, LineMatch
from yate.editor_view import theme
from yate.logs import tracing
from yate.paths import load_tcss
from yate.services.workspace import Workspace
from yate.session import EditorSession

log = tracing.get_logger(__name__)

#: Delay between the last keystroke and the (re)start of the search worker.
DEBOUNCE_SECONDS: float = 0.3

#: Context columns kept on each side of a highlighted match snippet.
SNIPPET_CONTEXT: int = 40

#: File-scan ceiling handed to ``Workspace.walk_files``; reaching it means
#: the result list may be incomplete and the pane says so.
SCAN_FILE_CAP: int = 5_000

#: Reveal callback: focus (path, row, col) after the document opens.
type RevealFn = Callable[[Path, int, int], None]

#: Message-line callback (text + severity kind, as ``Editor.message``).
type MessageFn = Callable[[str, str], None]


class _Results(Static):
    """Focusable results pane (owns the enter / ``r`` / ``a`` cursor)."""

    can_focus = True


def _relative(path: Path, root: Path | None) -> str:
    """Display label for *path*: workspace-relative, else the bare name."""
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return path.name


class FindReplaceScreen(ModalScreen[None]):
    """Workspace-wide find & replace modal: grouped hits, ``enter`` jumps,
    ``r`` replaces the cursor's file, ``a`` replaces every hit file."""

    BINDINGS = [
        ("alt+c", "toggle_case", "match case"),
        ("alt+w", "toggle_word", "whole word"),
        ("alt+r", "toggle_regex", "regex"),
        ("escape", "dismiss_screen", "Close"),
    ]

    DEFAULT_CSS = load_tcss("find-replace-screen.tcss")

    def __init__(
        self,
        workspace: Workspace,
        session: EditorSession,
        *,
        open_path: Callable[[Path], None],
        reveal: RevealFn | None = None,
        message: MessageFn,
        readonly_notice: Callable[[], None],
        refresh: Callable[[], None],
    ) -> None:
        """Store the injected collaborators (no App handle reaches here).

        *open_path* opens a result file (async-scheduled by the shell);
        *reveal* focuses the match inside it once open (``None`` keeps the
        open-only behaviour until the wiring wave supplies one); *message* /
        *readonly_notice* / *refresh* are the usual editor feedback hooks.
        """
        super().__init__()
        self._workspace = workspace
        self._session = session
        self._open_path = open_path
        self._reveal = reveal
        self._message = message
        self._readonly_notice = readonly_notice
        # named apart from ``Widget.refresh`` (palette precedent)
        self._refresh_ui = refresh
        self._case = False
        self._word = False
        self._regex = False
        self._results: list[FileMatch] = []
        #: flat (path, match) cursor table rebuilt with every search
        self._flat: list[tuple[Path, LineMatch]] = []
        self._cursor = 0
        #: True when the workspace walk returned ``SCAN_FILE_CAP`` paths
        self._truncated = False
        #: 0-based results-pane line of the cursor row (scroll anchor)
        self._cursor_line = 0
        self._debounce: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------ compositional

    @override
    def compose(self) -> ComposeResult:
        """Compose the find/replace inputs, options chip and results pane."""
        with Vertical(id="find-replace"):
            with Horizontal(id="fr-inputs"):
                yield Input(placeholder="find", id="fr-find")
                yield Input(placeholder="replace with", id="fr-replace")
                yield Static(id="fr-options")
            # the results pane scrolls as a container: a Static with a
            # fractional height reports no virtual overflow, so its own
            # scrolling never engages (probed 2026-10-16)
            with VerticalScroll(id="fr-results-scroll"):
                yield _Results(id="fr-results")

    def on_mount(self) -> None:
        """Attach to the theme broadcast, paint the options and focus find."""
        theme.attach(self, self._apply_theme)
        self._render_options()
        self.query_one("#fr-find", Input).focus()

    def on_unmount(self) -> None:
        """Detach from the theme broadcast and drop the pending debounce."""
        theme.detach(self)
        self._cancel_debounce()

    # -------------------------------------------------------------- rendering

    def _apply_theme(self) -> None:
        """Repaint the theme-owned bits (options chip + results rows)."""
        self._render_options()
        self._render_results()

    def _render_options(self) -> None:
        """Paint the option toggles, active ones highlighted on accent."""
        t = theme.active()
        text = Text()
        for label, flag in (
            ("Aa", self._case), ("W", self._word), (".*", self._regex),
        ):
            style = f"{t.on_accent} on {t.accent}" if flag else t.fg_dim
            text.append(f" {label} ", style=style)
        self.query_one("#fr-options", Static).update(text)

    def _render_results(self) -> None:
        """Render hits grouped per file with the cursor row marked."""
        t = theme.active()
        text = Text()
        pane = self.query_one("#fr-results", _Results)
        scroller = self.query_one("#fr-results-scroll", VerticalScroll)
        if not self._results:
            text.append("  no matches", style=t.fg_dim)
            pane.update(text)
            scroller.scroll_to(y=0, animate=False)
            return
        root = self._workspace.root
        flat_index = 0
        line_no = 0
        for fm in self._results:
            label = _relative(fm.path, root)
            text.append(
                f"{label}  ({len(fm.matches)} match(es))\n", style=t.fg_muted,
            )
            line_no += 1
            for m in fm.matches:
                cursor_here = flat_index == self._cursor
                if cursor_here:
                    self._cursor_line = line_no
                fg = t.fg if cursor_here else t.fg_muted
                marker = "> " if cursor_here else "  "
                text.append(f"{marker}{m.row + 1}: ", style=fg)
                self._append_snippet(
                    text, fm.hit_lines.get(m.row, ""), m, fg, cursor_here,
                )
                text.append("\n")
                flat_index += 1
                line_no += 1
        if self._truncated:
            text.append(
                f"  scan stopped at the {SCAN_FILE_CAP}-file cap; "
                "results may be incomplete",
                style=t.fg_dim,
            )
        pane.update(text)
        # large hit sets overflow the pane: keep the cursor row in view
        scroller.scroll_to(y=self._cursor_line, animate=False)

    def _append_snippet(
        self, text: Text, line: str, m: LineMatch, fg: str, cursor_here: bool,
    ) -> None:
        """Append one ``…context[match]context…`` snippet row body."""
        # the raw hit line keeps its "\r" tail on CRLF files: display noise
        line = line.rstrip("\r")
        start = max(0, m.start - SNIPPET_CONTEXT)
        end = min(len(line), m.end + SNIPPET_CONTEXT)
        t = theme.active()
        if start > 0:
            text.append("…", style=t.fg_dim)
        text.append(line[start : m.start], style=fg)
        style = f"{t.on_accent} on {t.match_bg}" if cursor_here else f"on {t.match_bg}"
        text.append(line[m.start : m.end], style=style)
        text.append(line[m.end : end], style=fg)
        if end < len(line):
            text.append("…", style=t.fg_dim)

    # ------------------------------------------------------------ live search

    def _query(self) -> str:
        """Current find text (the find input is always mounted here)."""
        return self.query_one("#fr-find", Input).value

    def _replace_text(self) -> str:
        """Current replace-with text."""
        return self.query_one("#fr-replace", Input).value

    def on_input_changed(self, event: Input.Changed) -> None:
        """Debounce the find input; an empty query clears at once."""
        if event.input.id != "fr-find":
            return
        self._cancel_debounce()
        if event.value == "":
            self._clear_results()
            return
        loop = asyncio.get_running_loop()
        self._debounce = loop.call_later(DEBOUNCE_SECONDS, self._start_search)

    def _start_search(self) -> None:
        """(Re)start the exclusive search worker over the workspace."""
        self._cancel_debounce()
        if self._query() == "":
            self._clear_results()
            return
        self.run_worker(
            # coroutine *function* via partial, palette precedent: an eager
            # coroutine would leak if the worker never starts (closing pump)
            partial(self._search_worker, self._query()),
            group="fr-search", exclusive=True, exit_on_error=False,
        )

    async def _search_worker(self, query: str) -> None:
        """Scan the workspace in a thread, then repaint when still mounted."""

        def _scan() -> tuple[list[FileMatch], bool]:
            paths = self._workspace.walk_files(limit=SCAN_FILE_CAP)
            truncated = len(paths) >= SCAN_FILE_CAP
            # hit lines ride along from the scan read (FileMatch.hit_lines):
            # no per-hit re-read for snippet rendering
            results = project_search.search_files(
                paths, query,
                case_sensitive=self._case, use_regex=self._regex,
                whole_word=self._word,
            )
            return results, truncated

        results, truncated = await asyncio.to_thread(_scan)
        if not self.is_mounted:
            return
        self._results = results
        self._truncated = truncated
        self._flat = [(fm.path, m) for fm in results for m in fm.matches]
        self._cursor = 0
        self._render_results()

    def _clear_results(self) -> None:
        """Drop every hit and repaint the empty results pane."""
        self._results = []
        self._flat = []
        self._cursor = 0
        self._truncated = False
        self._render_results()

    def _cancel_debounce(self) -> None:
        """Cancel a pending debounce timer, if any."""
        if self._debounce is not None:
            self._debounce.cancel()
            self._debounce = None

    # ----------------------------------------------------------------- keys

    def on_key(self, event: Key) -> None:
        """Results-pane keys: move the cursor, jump or replace (R10).

        Consumed keys are stopped and prevented; everything else falls
        through to the normal dispatch.
        """
        results = self.query_one("#fr-results", _Results)
        if self.focused is not results:
            return
        if event.key in ("up", "down"):
            event.stop()
            event.prevent_default()
            if self._flat:
                step = -1 if event.key == "up" else 1
                self._cursor = max(0, min(len(self._flat) - 1, self._cursor + step))
                self._render_results()
        elif event.key == "enter":
            event.stop()
            event.prevent_default()
            self._open_current()
        elif event.key == "r":
            event.stop()
            event.prevent_default()
            self._replace_scope_current()
        elif event.key == "a":
            event.stop()
            event.prevent_default()
            self._replace_scope_all()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the find input jumps; in the replace input it moves the
        focus to the results pane so r/a/enter become reachable."""
        if event.input.id == "fr-find":
            self._open_current()
        elif event.input.id == "fr-replace":
            self.query_one("#fr-results", _Results).focus()

    # -------------------------------------------------------------- actions

    def action_toggle_case(self) -> None:
        """Toggle match-case and rerun the search."""
        self._case = not self._case
        self._render_options()
        self._start_search()

    def action_toggle_word(self) -> None:
        """Toggle whole-word and rerun the search."""
        self._word = not self._word
        self._render_options()
        self._start_search()

    def action_toggle_regex(self) -> None:
        """Toggle regex mode and rerun the search."""
        self._regex = not self._regex
        self._render_options()
        self._start_search()

    def action_dismiss_screen(self) -> None:
        """Close the overlay (escape)."""
        self.dismiss()

    # ----------------------------------------------------------- open / jump

    def _open_current(self) -> None:
        """Dismiss the overlay, open the cursor's file and reveal the hit."""
        if not self._flat:
            return
        path, match = self._flat[self._cursor]
        self.dismiss()
        self._open_path(path)
        if self._reveal is not None:
            self._reveal(path, match.row, match.start)

    # -------------------------------------------------------------- replace

    def _replace_scope_current(self) -> None:
        """Replace within the file under the cursor only."""
        if not self._flat:
            return
        path = self._flat[min(self._cursor, len(self._flat) - 1)][0]
        self._replace_scope([path])

    def _replace_scope_all(self) -> None:
        """Replace within every file that currently has a hit."""
        paths = list(dict.fromkeys(path for path, _match in self._flat))
        self._replace_scope(paths)

    def _replace_scope(self, paths: list[Path]) -> None:
        """Guard the inputs, then run the replace worker (r / a shared)."""
        find = self._query()
        replacement = self._replace_text()
        # an empty replacement is legal: it deletes every match
        if find == "":
            self._message("find field must be filled", "warn")
            return
        pattern = project_search.compile_query(
            find,
            case_sensitive=self._case, use_regex=self._regex,
            whole_word=self._word,
        )
        if pattern is None:
            self._message("invalid search pattern", "warn")
            return
        # snapshot the option state here: the worker must not re-read live
        # inputs or flags mid-flight, or open-buffer edits would follow a
        # different query than the disk edits of the same batch
        engine = SearchEngine()
        engine.case_sensitive = self._case
        engine.use_regex = self._regex
        engine.whole_word = self._word
        self.run_worker(
            partial(
                self._replace_worker, paths, pattern, engine, find, replacement,
            ),
            group="fr-replace", exclusive=True, exit_on_error=False,
        )

    async def _replace_worker(
        self, paths: list[Path], pattern: re.Pattern[str], engine: SearchEngine,
        find: str, replacement: str,
    ) -> None:
        """Replace in every *path* (open buffers in memory, the rest on disk)."""
        total = 0
        files = 0
        for path in paths:
            doc = self._session.is_open(path)
            if doc is not None:
                count = self._replace_open(doc, engine, find, replacement)
            else:
                count = await asyncio.to_thread(
                    self._replace_on_disk, path, pattern, replacement,
                )
            if count > 0:
                total += count
                files += 1
        log.debug(
            "project replace: %d occurrence(s) in %d file(s)", total, files,
        )
        if not self.is_mounted:
            return
        self._message(f"replaced {total} occurrence(s) in {files} file(s)", "ok")
        self._refresh_ui()
        self._start_search()

    def _replace_open(
        self, doc: Document, engine: SearchEngine, find: str, replacement: str,
    ) -> int:
        """Replace inside an open buffer via the snapshot engine; undoable."""
        engine.update(find, doc.buffer)
        try:
            return engine.replace_all(doc.buffer, replacement)
        except BufferReadOnlyError:
            self._readonly_notice()
            return 0

    def _replace_on_disk(
        self, path: Path, pattern: re.Pattern[str], replacement: str,
    ) -> int:
        """Read-modify-write *path* (worker thread); skip when unchanged.

        Honours the ``replace_lines`` contract: the very same lines object
        coming back means nothing matched, so the file is left untouched.
        Lines are split on ``"\\n"`` only -- like ``TextBuffer`` -- so CRLF
        and CR line endings round-trip byte-exact and legal characters that
        ``str.splitlines`` would treat as breaks (``\u2028`` & co) are never
        rewritten outside the replaced spans.  The write itself follows the
        ``Document.save`` durability standard: a sibling temp file swapped
        in with ``os.replace``, so a crash mid-write cannot destroy the
        previous contents.  Read and write errors skip the file with a
        count of zero.
        """
        try:
            data = path.read_bytes()
        except OSError:
            log.debug("project replace skipped unreadable file %s", path)
            return 0
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            log.debug("project replace skipped non-utf8 file %s", path)
            return 0
        lines = text.split("\n")
        new_lines, count = project_search.replace_lines(lines, pattern, replacement)
        if new_lines is lines:
            return 0
        payload = "\n".join(new_lines).encode("utf-8")
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=path.parent, prefix=path.name + ".yate-tmp-"
            )
        except OSError:
            # the file vanished (or its directory did) between search and
            # replace: skip it, the batch keeps going
            log.warning("project replace could not stage %s", path)
            return 0
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
            # inherit permission bits (POSIX: also the xattrs carrying ACLs)
            # like ``Document.save``, but not the timestamps: a replaced file
            # must look freshly written to build tools and file watchers
            shutil.copystat(path, tmp)
            os.utime(tmp)
            os.replace(tmp, path)
        except OSError:
            tmp.unlink(missing_ok=True)
            log.warning("project replace failed to write %s", path)
            return 0
        return count
