"""Tests for the static chrome widgets: TabBar overflow and hit regions.

``TabBar.build`` is a pure function over the shared ``EditorSession`` plus
the active theme, so the `` +N`` overflow indicator and the click-test
regions are asserted headlessly without spinning a Textual app.
"""

# tests legitimately poke at widget internals:
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path

import pytest

from yate.config import YateConfig
from yate.editor_core import Document
from yate.editor_view.chrome import Breadcrumbs, TabBar
from yate.session import EditorSession
from yate.services.workspace import Workspace


def _session_with_tabs(tmp_path: Path, names: list[str]) -> EditorSession:
    """A session with one open file tab per *names* entry (short names)."""
    session = EditorSession(YateConfig())
    for name in names:
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        opened = session.open(path)
        assert opened is not None
    return session


# --- overflow indicator ------------------------------------------------------


def test_narrow_tab_bar_collapses_hidden_docs_into_an_indicator(
    tmp_path: Path,
) -> None:
    """Tabs that do not fit collapse into a trailing `` +N`` marker."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py", "c.py"])
    bar = TabBar(session, lambda _doc: None)
    text, regions = bar.build(14)  # 8 cells per tab: only the first fits
    assert " +2" in text.plain
    assert len(regions) < len(session.docs)


def test_wide_tab_bar_shows_every_doc_without_an_indicator(
    tmp_path: Path,
) -> None:
    """A bar wide enough for all tabs renders no overflow marker."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py", "c.py"])
    bar = TabBar(session, lambda _doc: None)
    text, regions = bar.build(80)
    assert "+" not in text.plain
    assert [doc_idx for _s, _e, doc_idx in regions] == [0, 1, 2]


def test_indicator_carries_no_click_region_but_tabs_still_hit(
    tmp_path: Path,
) -> None:
    """Only visible tabs register spans; the `` +N`` cells stay inert."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py", "c.py"])
    activated: list[Document] = []
    bar = TabBar(session, activated.append)
    text, regions = bar.build(14)
    assert [doc_idx for _s, _e, doc_idx in regions] == [0]
    start, end, _ = regions[0]
    # the first tab's own span is a live hit target
    assert start < end
    # the indicator occupies the cells right after the last region and no
    # region claims them (a click there falls through like the background)
    assert " +2" in text.plain
    indicator_x = end
    assert not any(s <= indicator_x < e for s, e, _ in regions)


def test_indicator_that_does_not_fit_refits_once(tmp_path: Path) -> None:
    """Two tabs fit the width but leave no room for `` +1``: the bar re-fits
    one tab tighter so the (wider) `` +2`` indicator still shows."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py", "c.py"])
    bar = TabBar(session, lambda _doc: None)
    text, regions = bar.build(18)  # 2 tabs (16 cells) + 3 > 18 -> refit to 15
    assert " +2" in text.plain
    assert [doc_idx for _s, _e, doc_idx in regions] == [0]


def test_extremely_narrow_bar_omits_the_indicator(tmp_path: Path) -> None:
    """A bar too narrow for even `` +N`` degrades to an empty background."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py"])
    bar = TabBar(session, lambda _doc: None)
    text, regions = bar.build(2)  # the 3-cell indicator cannot fit
    assert "+" not in text.plain
    assert regions == []


# --- breadcrumbs (plan-b m-12) ------------------------------------------------


def test_breadcrumbs_resolve_root_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The workspace root resolves once per root, not per redraw (m-12)."""
    workspace = Workspace()
    workspace.set_root(tmp_path)
    doc_path = tmp_path / "sub" / "note.txt"
    doc_path.parent.mkdir()
    doc_path.write_text("", encoding="utf-8")
    session = EditorSession(YateConfig())
    opened = session.open(doc_path)
    assert opened is not None

    real_resolve = Path.resolve
    resolved: list[Path] = []

    def counting_resolve(self: Path) -> Path:
        resolved.append(self)
        return real_resolve(self)

    monkeypatch.setattr(Path, "resolve", counting_resolve)
    crumbs = Breadcrumbs(session, workspace)
    first = crumbs.crumb_parts()
    second = crumbs.crumb_parts()
    assert [label for _i, label, _f in second] == [
        tmp_path.name, "sub", "note.txt",
    ]
    assert first == second
    # two renders: root resolves once (cached per root object) and the doc
    # path resolves once too (cached per path string, plan-f P10b)
    assert resolved.count(tmp_path) == 1  # root, first render only
    assert resolved.count(doc_path) == 1


def test_breadcrumbs_resolve_doc_path_again_after_retarget(
    tmp_path: Path,
) -> None:
    """A different active doc path re-resolves; a save (same path) does not."""
    workspace = Workspace()
    workspace.set_root(tmp_path)
    first = tmp_path / "one.txt"
    second = tmp_path / "two.txt"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    session = EditorSession(YateConfig())
    assert session.open(first) is not None
    crumbs = Breadcrumbs(session, workspace)
    assert crumbs.crumb_parts()[-1][1] == "one.txt"
    assert session.open(second) is not None
    assert crumbs.crumb_parts()[-1][1] == "two.txt"  # retarget re-resolves
    assert crumbs.crumb_parts()[-1][1] == "two.txt"  # same path hits cache


def test_tab_bar_fingerprint_skips_unchanged_rebuild(tmp_path: Path) -> None:
    """refresh_tabs with an unchanged state does not rebuild (plan-f P3)."""
    session = _session_with_tabs(tmp_path, ["a.py", "b.py"])
    bar = TabBar(session, lambda _doc: None)
    bar._last_fingerprint = None
    builds: list[int] = []

    def counting_render(width: int) -> None:
        builds.append(width)

    # Assigning a private test hook onto a frozen instance; suppression is intentional.
    # pyright: ignore[reportAttributeAccessIssue]
    bar.render_content = counting_render
    bar.refresh_tabs()
    bar.refresh_tabs()
    assert len(builds) == 1
    # Any render-input change (width, active index, doc identity) rebuilds.
    session.index = 0
    bar.refresh_tabs()
    assert len(builds) == 2


def test_breadcrumbs_fingerprint_skips_unchanged_rebuild(tmp_path: Path) -> None:
    """refresh_crumbs with an unchanged state does not rebuild (plan-f P3)."""
    workspace = Workspace()
    workspace.set_root(tmp_path)
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("", encoding="utf-8")
    session = EditorSession(YateConfig())
    assert session.open(doc_path) is not None
    crumbs = Breadcrumbs(session, workspace)
    updates: list[object] = []

    def counting_update(content: object = "", *, layout: bool = True) -> None:
        updates.append(content)

    # Test spy needs a wider parameter type than VisualType; suppression is intentional.
    crumbs.update = counting_update  # pyright: ignore[reportAttributeAccessIssue]
    crumbs.refresh_crumbs()
    crumbs.refresh_crumbs()
    assert len(updates) == 1
