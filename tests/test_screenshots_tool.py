"""Tests for the screenshot tool: registry integrity, gallery, CLI edges.

The end-to-end case exercises exactly one real, fast pilot scenario
(welcome-screen) so the suite stays quick; the three subprocess-report
scenarios are deliberately not run here.  Failure/edge paths use stub
registries so no pilot is needed for them either.
"""

from __future__ import annotations

import getpass
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import tools.screenshots.__main__ as screenshots_cli
from tools.screenshots.driver import DriverFn
from tools.screenshots.__main__ import main
from tools.screenshots.gallery import render_gallery
from tools.screenshots.scenarios import SCENARIOS, Scenario


def _stub_scenario(name: str) -> Scenario:
    """A registry-shaped entry whose driver is never invoked here."""
    async def _driver(svg_path: Path, fixtures: Path) -> None:
        return None

    return Scenario(
        name=name,
        title_en=f"{name} title",
        title_zh=f"{name} 标题",
        desc_en=f"English description for {name}.",
        desc_zh=f"{name} 的中文说明。",
        size=(100, 30),
        driver=_driver,
    )


def test_registry_names_are_kebab_and_unique() -> None:
    """Every scenario name is kebab-case and unique; texts are non-empty."""
    names = [scenario.name for scenario in SCENARIOS]
    assert len(set(names)) == len(names)
    for name in names:
        assert re.fullmatch(r"[a-z0-9-]+", name), name
    for scenario in SCENARIOS:
        assert scenario.title_en and scenario.title_zh
        assert scenario.desc_en and scenario.desc_zh
        assert scenario.size == (100, 30)


def test_gallery_renders_registry_to_markdown(tmp_path: Path) -> None:
    """The gallery renders one section per scenario plus the font note."""
    stubs = (_stub_scenario("stub-alpha"), _stub_scenario("stub-beta"))
    gallery = render_gallery(stubs, tmp_path)
    assert gallery == tmp_path / "README.md"
    text = gallery.read_text(encoding="utf-8")
    assert text.count("### ") == 2
    assert "### stub-alpha" in text
    assert '<img src="./stub-alpha.svg" width="720">' in text
    assert "Nerd Font" in text
    assert "中文说明" in text


def test_welcome_screenshot_end_to_end(tmp_path: Path) -> None:
    """``--only welcome-screen`` produces a real SVG plus the gallery."""
    out = tmp_path / "shots"
    exit_code = main(["--only", "welcome-screen", "--out", str(out)])
    assert exit_code == 0
    svg = out / "welcome-screen.svg"
    assert svg.exists()
    assert "rich-terminal" in svg.read_text(encoding="utf-8")
    gallery = out / "README.md"
    assert gallery.exists()
    text = gallery.read_text(encoding="utf-8")
    assert "### welcome-screen" in text
    assert '<img src="./welcome-screen.svg" width="720">' in text


def test_partial_regen_preserves_full_gallery(tmp_path: Path) -> None:
    """A partial ``--only`` regen keeps the complete gallery intact.

    With every SVG present, the existence-filtered gallery renders the full
    registry, so regenerating one scenario must not shrink the gallery to
    that subset (regression for the subset-render defect).
    """
    out = tmp_path / "shots"
    out.mkdir()
    for scenario in SCENARIOS:
        (out / f"{scenario.name}.svg").write_text("<svg/>", encoding="utf-8")
    exit_code = main(["--only", "welcome-screen", "--out", str(out)])
    assert exit_code == 0
    text = (out / "README.md").read_text(encoding="utf-8")
    assert text.count("### ") == len(SCENARIOS)
    assert "### welcome-screen" in text
    assert "### game-snake" in text


def test_list_prints_registry(capsys: pytest.CaptureFixture[str]) -> None:
    """``--list`` prints one line per scenario plus the total line."""
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == len(SCENARIOS) + 1
    assert lines[-1] == f"total: {len(SCENARIOS)} scenarios"
    assert lines[0].startswith("welcome-screen")


def test_unknown_only_name_fails() -> None:
    """An unknown ``--only`` name exits with a clear message."""
    try:
        main(["--only", "nope"])
    except SystemExit as exc:
        assert "unknown scenario(s): nope" in str(exc)
    else:
        raise AssertionError("expected SystemExit for unknown scenario")


def test_failing_scenario_is_reported_and_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing driver exits 1 and stays out of the gallery.

    Two stub scenarios: one writes a valid image, one returns without
    writing anything (the runner must treat a missing/invalid image as a
    failure, not as success).  The gallery then lists only the successful
    one and the exit code is 1.
    """

    async def _ok(svg_path: Path, fixtures: Path) -> None:
        svg_path.write_text("<svg/>", encoding="utf-8")

    async def _lazy(svg_path: Path, fixtures: Path) -> None:
        return None

    stubs = tuple(
        Scenario(
            name=name,
            title_en=f"{name} title",
            title_zh=f"{name} 标题",
            desc_en=f"English description for {name}.",
            desc_zh=f"{name} 的中文说明。",
            size=(100, 30),
            driver=driver,
        )
        for name, driver in (("stub-ok", _ok), ("stub-lazy", _lazy))
    )
    monkeypatch.setattr(screenshots_cli, "SCENARIOS", stubs)
    out = tmp_path / "shots"
    exit_code = main(["--out", str(out)])
    assert exit_code == 1
    assert (out / "stub-ok.svg").exists()
    assert not (out / "stub-lazy.svg").exists()
    text = (out / "README.md").read_text(encoding="utf-8")
    assert "### stub-ok" in text
    assert "### stub-lazy" not in text


def _single_stub(
    monkeypatch: pytest.MonkeyPatch, name: str, driver: DriverFn
) -> None:
    """Point the CLI's registry at one stub scenario."""
    stub = Scenario(
        name=name,
        title_en=f"{name} title",
        title_zh=f"{name} 标题",
        desc_en=f"English description for {name}.",
        desc_zh=f"{name} 的中文说明。",
        size=(100, 30),
        driver=driver,
    )
    monkeypatch.setattr(screenshots_cli, "SCENARIOS", (stub,))


def test_placeholders_and_controls_are_xml_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scrubbed frames stay well-formed XML.

    The stub frame carries the OS user name inside a home path plus a raw
    control character: the runner must escape its placeholders and
    caret-encode the control character, or viewers refuse to render the
    image at all (the reported "broken image" defect).
    """

    async def _dirty(svg_path: Path, fixtures: Path) -> None:
        svg_path.write_text(
            "<svg><text>C:\\Users\\" + getpass.getuser()
            + "\\x" + chr(0x1D) + "</text></svg>",
            encoding="utf-8",
        )

    _single_stub(monkeypatch, "stub-dirty", _dirty)
    out = tmp_path / "shots"
    assert main(["--out", str(out)]) == 0
    text = (out / "stub-dirty.svg").read_text(encoding="utf-8")
    ET.fromstring(text)
    assert "&lt;home&gt;" in text
    assert "^]" in text


def test_icon_font_is_embedded_for_pua_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A frame with private-use glyphs gets the icon font embedded."""

    async def _icons(svg_path: Path, fixtures: Path) -> None:
        svg_path.write_text(
            "<svg><style>text { font-family: Fira Code, monospace; }"
            "</style><text>" + chr(0xF07B) + "</text></svg>",
            encoding="utf-8",
        )

    _single_stub(monkeypatch, "stub-icons", _icons)
    out = tmp_path / "shots"
    assert main(["--out", str(out)]) == 0
    text = (out / "stub-icons.svg").read_text(encoding="utf-8")
    assert 'font-family: Fira Code, "Yate NF Icons", monospace;' in text
    assert "data:font/woff2;base64," in text
