"""Regression tests for the screenshot driver's subprocess timeout (m21).

Pins review finding m21 only: the ``fontTools.subset`` subprocess carries a
wall-clock timeout, and the post-processing steps (``scrub_svg`` /
``embed_icon_font``) run inside the awaited ``wait_for`` budget instead of
after it -- a hung font subsetting subprocess previously stalled the
screenshot tool indefinitely.
"""

# embed_icon_font's subprocess boundary and _run_one's coroutine layout are
# the contracts under test (module-private seams, same convention
# tests/test_screenshots_tool.py uses).
# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from tools.screenshots import driver
from tools.screenshots.__main__ import _run_one


@pytest.fixture
def svg_with_icon_glyphs(tmp_path: Path) -> Path:
    """An SVG whose style block contains a private-use-area icon glyph."""
    path = tmp_path / "probe.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        "<style>text { font-family: mono; }</style>\n"
        f"<text>\ue0b0</text>\n"
        "</svg>\n",
        encoding="utf-8",
    )
    return path


def test_embed_icon_font_bounds_the_font_subset_subprocess(
    monkeypatch: pytest.MonkeyPatch, svg_with_icon_glyphs: Path
) -> None:
    """The fontTools.subset call carries a timeout (m21)."""
    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> Any:
        captured.update(kwargs)
        captured["args"] = args
        return type("Proc", (), {"returncode": 1, "stderr": b"stubbed"})()

    monkeypatch.setattr(driver.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="font subset failed"):
        driver.embed_icon_font(svg_with_icon_glyphs)

    assert captured.get("timeout") == driver._FONT_SUBSET_TIMEOUT_S
    assert any("fontTools.subset" == part for part in captured["args"])


def test_scrub_and_embed_run_inside_the_wait_for_budget() -> None:
    """scrub_svg / embed_icon_font are awaited within _run_one's budget (m21).

    Source-text pin: the defect is temporal ordering (post-processing ran
    after ``asyncio.wait_for`` returned), which a unit test can only
    observe by inspecting the coroutine body.
    """
    source = inspect.getsource(_run_one)
    body = source.split("async def _render_and_finish", 1)[1].split(
        "asyncio.run(", 1
    )[0]
    # The post-processing steps share one wait_for with the pilot run:
    assert "scrub_svg" in body
    assert "embed_icon_font" in body
    assert "asyncio.wait_for(_render_and_finish(), timeout=timeout)" in body
