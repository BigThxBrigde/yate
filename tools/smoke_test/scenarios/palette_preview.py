"""Ctrl+p file preview scenarios (tag: ``files``).

Three paths through the ``file_preview`` feature, driven end to end
(ctrl+p open -> preview render -> confirm open):

* the pane renders the highlighted file with syntax tokens applied;
* an oversize file truncates at the configured line cap;
* ``file_preview enable = False`` keeps the legacy palette DOM and the
  plain open behaviour.

``PaletteScreen`` exposes no public accessor for ``_preview_cache``, so the
read helpers below go through ``getattr`` + ``cast`` with the field names
taken from ``yate/editor_view/palette.py`` -- the same documented-private
probe pattern the diffview scenarios use (direct private attribute access
would trip pyright's ``reportPrivateUsage``, which this repo's
zero-diagnostic gate treats as an error).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from yate.config import load_config
from yate.editor_view.palette import PaletteScreen, PreviewLog

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import type_text, wait_until

__all__ = ["SCENARIOS"]


# --------------------------------------------------------------- read helpers


def _palette(app: object) -> PaletteScreen | None:
    """The top screen when it is the ctrl+p palette, else ``None``."""
    screen = getattr(app, "screen", None)
    return screen if isinstance(screen, PaletteScreen) else None


def _entry(screen: PaletteScreen, name: str) -> object | None:
    """Cached preview payload for the file called *name* (``None`` if absent).

    Paths are matched by *name*, not equality, so the probe is independent
    of how the workspace root was spelled (short names / resolve()).
    """
    cache = cast("dict[Path, object]", getattr(screen, "_preview_cache", {}))
    for path, data in cache.items():
        if path.name == name:
            return data
    return None


def _note(entry: object) -> str | None:
    """``note`` of a cached preview payload (``_PreviewData.note``)."""
    return cast("str | None", getattr(entry, "note", "missing"))


def _lines(entry: object) -> list[str]:
    """``lines`` of a cached preview payload (``_PreviewData.lines``)."""
    return cast("list[str]", getattr(entry, "lines", []))


def _tokens(entry: object) -> list[object]:
    """``tokens`` of a cached preview payload (``_PreviewData.tokens``)."""
    return cast("list[object]", getattr(entry, "tokens", []))


def _truncated(entry: object) -> bool:
    """``truncated`` flag of a cached preview payload."""
    return cast(bool, getattr(entry, "truncated", False))


def _rendered_text(screen: PaletteScreen) -> str:
    """Plain text currently rendered in the ``#palette-preview`` log pane."""
    pane = screen.query_one("#palette-preview", PreviewLog)
    return "\n".join(strip.text for strip in pane.lines)


# ------------------------------------------------------------------ scenarios


async def _palette_preview_renders(tmp: Path) -> ScenarioResult:
    """The ctrl+p preview pane renders the highlighted file with syntax."""
    (tmp / "alpha.py").write_text(
        'def greet():\n    return "hi"\n', encoding="utf-8"
    )
    (tmp / "notes.txt").write_text("hello\n", encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        checks.append(Check("palette_open", 2, len(app.screen_stack)))
        await type_text(pilot, "alpha")

        def preview_ready() -> bool:
            palette = _palette(app)
            return (
                palette is not None
                and bool(palette.query("#palette-preview"))
                and _entry(palette, "alpha.py") is not None
            )

        # the read+tokenize worker lands asynchronously; the cache entry is
        # the reliable completion signal (painted in the same callback)
        await wait_until(pilot, preview_ready)
        screen = _palette(app)
        entry = None if screen is None else _entry(screen, "alpha.py")
        checks.append(Check(
            "preview_widget", True,
            screen is not None and bool(screen.query("#palette-preview")),
        ))
        checks.append(Check("preview_note", None, _note(entry)))
        lines = _lines(entry)
        checks.append(Check(
            "preview_first_line", True,
            bool(lines) and "def greet" in lines[0],
        ))
        checks.append(Check("preview_tokens", True, bool(_tokens(entry))))
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("doc.name", "alpha.py", app.editor.session.doc.name))
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("palette_preview_renders", checks, rows)


async def _palette_preview_truncates(tmp: Path) -> ScenarioResult:
    """An oversize preview truncates at the default 2000-line cap."""
    (tmp / "big.py").write_text("x = 1\n" * 3000, encoding="utf-8")
    app = new_app(target=tmp)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        await type_text(pilot, "big")

        def preview_ready() -> bool:
            palette = _palette(app)
            return palette is not None and _entry(palette, "big.py") is not None

        await wait_until(pilot, preview_ready)
        screen = _palette(app)
        entry = None if screen is None else _entry(screen, "big.py")
        checks.append(Check("truncated", True, _truncated(entry)))
        checks.append(Check("line_cap", 2000, len(_lines(entry))))
        checks.append(Check(
            "truncated_note_rendered", True,
            screen is not None and "truncated" in _rendered_text(screen),
        ))
        # The runner's invariant sweep fails a scenario that ends with a
        # modal left on the stack; close the palette the way a user would.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
    return ScenarioResult("palette_preview_truncates", checks)


async def _palette_preview_disabled(tmp: Path) -> ScenarioResult:
    """``file_preview enable = False`` keeps the legacy palette DOM.

    The project ``yaterc`` (with the preview switched off) is loaded
    explicitly and handed to :func:`new_app` as the resolved config:
    ``YateApp`` itself never reads rc files from disk (that is the CLI
    entry's job), so ``chdir`` alone would not make the project rc apply.
    """
    project = tmp / "project"
    project.mkdir()
    (project / "yaterc").write_text(
        'file_preview = {"enable": False}\n', encoding="utf-8"
    )
    plain = project / "plain.txt"
    plain.write_text("plain text\n", encoding="utf-8")
    config = load_config([project / "yaterc"])
    app = new_app(target=plain, config=config)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        checks.append(Check("palette_open", 2, len(app.screen_stack)))
        screen = _palette(app)
        checks.append(Check(
            "preview_widget_absent", True,
            screen is not None and not screen.query("#palette-preview"),
        ))
        checks.append(Check(
            "with_preview_class_absent", True,
            screen is not None and not screen.has_class("with-preview"),
        ))

        def results_ready() -> bool:
            palette = _palette(app)
            return palette is not None and palette.filtered_count >= 1

        # the file index builds in a worker thread; wait for it to land
        await wait_until(pilot, results_ready)
        screen = _palette(app)
        checks.append(Check(
            "results_rendered", True,
            screen is not None and screen.filtered_count >= 1,
        ))
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("doc.name", "plain.txt", app.editor.session.doc.name))
        checks.append(Check("palette_closed", 1, len(app.screen_stack)))
    return ScenarioResult("palette_preview_disabled", checks)


SCENARIOS: list[Scenario] = [
    Scenario("palette_preview_renders", _palette_preview_renders, ("files",)),
    Scenario("palette_preview_truncates", _palette_preview_truncates, ("files",)),
    Scenario("palette_preview_disabled", _palette_preview_disabled, ("files",)),
]
