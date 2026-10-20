"""Tests for the custom pymarkdown plugins shipped with tools.mdlint."""

from __future__ import annotations

import re

from tools.mdlint.lint import LintEngine
from tools.mdlint.rules import plugin_dir


def _ym_ids(text: str) -> set[str]:
    """Return the YM* rule IDs triggered by *text* under the zh profile."""
    engine = LintEngine("zh")
    return {v.rule_id for v in engine.scan(text) if v.rule_id.startswith("YM")}


def test_ym001_detects_cjk_ascii_adjacency() -> None:
    """Missing space between CJK and Latin triggers YM001."""
    assert "YM001" in _ym_ids("你好world\n")


def test_ym001_clean_with_space() -> None:
    """A space between CJK and Latin is clean."""
    assert "YM001" not in _ym_ids("你好 world\n")


def test_ym001_skips_code_fence() -> None:
    """CJK/Latin adjacency inside a fenced block is not reported."""
    assert _ym_ids("```\n你好world\n```\n") == set()


def test_ym002_detects_halfwidth_comma_near_cjk() -> None:
    """A half-width comma next to CJK text triggers YM002."""
    assert "YM002" in _ym_ids("你好,世界\n")


def test_ym002_clean_with_fullwidth_comma() -> None:
    """A full-width comma is clean."""
    assert "YM002" not in _ym_ids("你好，世界\n")


def test_ym003_detects_ascii_quotes_near_cjk() -> None:
    """ASCII quotes around Chinese text trigger YM003."""
    assert "YM003" in _ym_ids("他说\"你好\"\n")


def test_ym003_clean_with_chinese_quotes() -> None:
    """Chinese quotation marks are clean."""
    assert "YM003" not in _ym_ids("他说\u201c你好\u201d\n")


def test_ym004_detects_trailing_cjk_punct() -> None:
    """A heading ending in Chinese punctuation triggers YM004."""
    assert "YM004" in _ym_ids("## 标题。\n")


def test_ym004_clean_heading_no_trailing_punct() -> None:
    """A heading without trailing punctuation is clean."""
    assert "YM004" not in _ym_ids("## 标题\n")


def test_en_profile_has_no_custom_plugins() -> None:
    """The en profile never reports custom YM* rules."""
    engine = LintEngine("en")
    result = engine.scan("你好world\n")
    assert not [v for v in result if v.rule_id.startswith("YM")]


def test_plugin_dir_exists_and_contains_plugins() -> None:
    """The plugin directory holds at least the four custom plugins."""
    py_files = [p for p in plugin_dir().iterdir() if p.suffix == ".py"]
    plugin_files = [p for p in py_files if p.name != "__init__.py"]
    assert len(plugin_files) >= 4


def test_all_plugins_have_valid_id_format() -> None:
    """Every plugin declares an ID matching 2-3 capitals + 3 digits."""
    pattern = re.compile(r"^[A-Z]{2,3}\d{3}$")
    for plugin_file in sorted(plugin_dir().glob("*.py")):
        if plugin_file.name == "__init__.py":
            continue
        source = plugin_file.read_text(encoding="utf-8")
        ids = re.findall(r'plugin_id="([^"]+)"', source)
        assert ids, f"no plugin_id declared in {plugin_file.name}"
        for plugin_id in ids:
            assert pattern.match(plugin_id), plugin_id
