"""Chunked (large file) scenarios (tags: ``files``, ``command``).

Covers the ``large_file`` chunked path end to end: a synthetic log just
above the default 8 MiB threshold opens as a locked, progressively
filled document -- the first screen renders real content with the
gutter line number ``1`` -- and a goto to the last line loads the final
chunk on demand and shows the correct line number and content.  The
synthetic log lives in the scenario's own harness tmp directory (cleaned
up after the run) and is sized just above the threshold to keep the
smoke wall clock acceptable.
"""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import (
    Check,
    Scenario,
    ScenarioResult,
    new_app,
    snapshot_svg,
)
from tools.smoke_test.scenarios._base import goto, wait_until

__all__ = ["SCENARIOS"]

#: Exact bytes of one synthetic log line (``\n`` included) -- the file is
#: a whole multiple of this, so the line count is deterministic.
_LINE_BYTES: int = 96

#: Total log size target: ~9 MB, above the 8 MiB default chunk threshold.
_LOG_TARGET_BYTES: int = 9_000_000

_HEAD_MARK: str = "chunked-head-marker"
_TAIL_MARK: str = "chunked-tail-marker"


def _line(index: int, payload: str) -> str:
    """Format synthetic log line *index*, padded to :data:`_LINE_BYTES`."""
    base = f"line {index:08d} {payload}"
    return base.ljust(_LINE_BYTES - 1) + "\n"


def _write_synthetic_log(path: Path, target_bytes: int) -> int:
    """Write a synthetic log of *target_bytes* bytes; return the line count.

    Line 0 carries the head marker and the last line the tail marker, so
    the scenario can assert on real content at both ends of the file.
    """
    count = max(1, target_bytes // _LINE_BYTES)
    parts: list[str] = []
    for i in range(count):
        payload = _HEAD_MARK if i == 0 else (
            _TAIL_MARK if i == count - 1 else "x" * 60
        )
        parts.append(_line(i, payload))
    path.write_text("".join(parts), encoding="utf-8")
    return count


def _gutter_row(
    rows: dict[int, str], line_no: str, content_prefix: str, marker: str
) -> bool:
    """Whether some rendered row shows gutter *line_no* over *content*.

    SVG text extraction collapses regular spaces, so the gutter number
    and the line content are glued together; matching the glued pair
    pins both the line number and the content.
    """
    glued = f"{line_no}{content_prefix}{marker}"
    return any(glued in row for row in rows.values())


async def _chunked_text_open_and_scroll(tmp: Path) -> ScenarioResult:
    """A > threshold log opens chunked; goto lands on the real last line.

    The 9 MB synthetic log opens through the chunked path (locked,
    read-only buffer, progressive fills): the first screen must show the
    head marker with gutter number ``1``, the background scan must reach
    the full line count, and ``goto`` to the last line must load the
    tail chunk and render the tail marker with the matching gutter
    number.
    """
    log_path = tmp / "big.log"
    total = _write_synthetic_log(log_path, _LOG_TARGET_BYTES)
    app = new_app(target=log_path)
    checks: list[Check] = []
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        checks.append(Check(
            "chunked_document", True,
            await wait_until(
                pilot,
                lambda: bool(app.editor.session.docs)
                and app.editor.session.doc.chunked is not None,
            ),
        ))
        buf = app.editor.session.buffer
        checks.append(Check("buffer_locked", True, buf.locked))
        checks.append(Check("buffer_read_only", True, buf.read_only))
        checks.append(Check(
            "first_screen_filled", True,
            await wait_until(pilot, lambda: buf.rows_loaded(0, 1)),
        ))
        rows = snapshot_svg(app, tmp)
        checks.append(Check(
            "svg_shows_head_line_and_gutter", True,
            _gutter_row(rows, "1", "line00000000", _HEAD_MARK),
        ))
        checks.append(Check(
            "scan_reaches_last_line", True,
            await wait_until(
                pilot, lambda: buf.line_count >= total, timeout=30.0
            ),
        ))
        await goto(pilot, str(total))
        checks.append(Check(
            "tail_chunk_loaded", True,
            await wait_until(
                pilot, lambda: buf.rows_loaded(total - 1, 1), timeout=30.0
            ),
        ))
        rows = snapshot_svg(app, tmp)
        checks.append(Check(
            "svg_shows_tail_line_and_gutter", True,
            _gutter_row(rows, str(total), f"line{total - 1:08d}", _TAIL_MARK),
        ))
    return ScenarioResult("chunked_text_open_and_scroll", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario(
        "chunked_text_open_and_scroll",
        _chunked_text_open_and_scroll,
        ("files", "command"),
    ),
]
