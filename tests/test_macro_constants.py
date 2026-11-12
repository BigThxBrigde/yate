"""Guard the shared L0 macro key constants and their parse_key forms."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from yate.keymaps.keys import (
    HOVER_DOC_KEY,
    MACRO_CONTROL_KEYS,
    MACRO_PLAY_KEY,
    MACRO_RECORD_KEY,
    MACRO_REPLAY_LAST_KEY,
    SPECIAL_KEYS,
    parse_key,
)

#: Repository root, resolved at runtime (no machine-local path literals).
PROJECT: Path = Path(__file__).resolve().parent.parent
#: The L0 key-notation module whose AST is inspected below.
KEYS_PATH: Path = PROJECT / "yate" / "keymaps" / "keys.py"


def test_macro_keys_have_expected_specs_and_no_conflict() -> None:
    """The three macro specs are f10/f11/f12 and collide with no reserved key."""
    assert MACRO_RECORD_KEY == "<f10>"
    assert MACRO_PLAY_KEY == "<f11>"
    assert MACRO_REPLAY_LAST_KEY == "<f12>"
    assert parse_key(MACRO_RECORD_KEY) == "\x1b[21~"
    assert parse_key(MACRO_PLAY_KEY) == "\x1b[23~"
    assert parse_key(MACRO_REPLAY_LAST_KEY) == "\x1b[24~"
    assert parse_key(HOVER_DOC_KEY) == "\x1b[18~"
    assert SPECIAL_KEYS["f9"] == "\x1b[20~"
    assert SPECIAL_KEYS["f8"] == "\x1b[19~"
    assert SPECIAL_KEYS["f6"] == "\x1b[17~"
    raw_forms = {
        parse_key(MACRO_RECORD_KEY),
        parse_key(MACRO_PLAY_KEY),
        parse_key(MACRO_REPLAY_LAST_KEY),
        parse_key(HOVER_DOC_KEY),
        SPECIAL_KEYS["f9"],
        SPECIAL_KEYS["f8"],
        SPECIAL_KEYS["f6"],
    }
    assert len(raw_forms) == 7


def test_macro_control_keys_match_parse_key() -> None:
    """The control set is exactly the parse_key forms of the three specs."""
    expected = frozenset({
        parse_key(MACRO_RECORD_KEY),
        parse_key(MACRO_PLAY_KEY),
        parse_key(MACRO_REPLAY_LAST_KEY),
    })
    assert MACRO_CONTROL_KEYS == expected
    assert len(MACRO_CONTROL_KEYS) == 3
    assert all(isinstance(item, str) for item in MACRO_CONTROL_KEYS)


def test_hover_doc_key_unchanged_after_macro_constants() -> None:
    """Adding macro constants leaves the shared hover key untouched."""
    assert HOVER_DOC_KEY == "<f7>"
    assert parse_key(HOVER_DOC_KEY) == "\x1b[18~"


def test_parse_key_unknown_macro_spec_raises_value_error() -> None:
    """An unknown function-key spec still raises the codec's ValueError."""
    with pytest.raises(ValueError) as excinfo:
        parse_key("<f13>")
    assert "unknown key name in spec" in str(excinfo.value)


def test_macro_constants_are_upper_case_module_level() -> None:
    """All four names are module-level and the control set follows parse_key."""
    tree = ast.parse(KEYS_PATH.read_text(encoding="utf-8"))
    assigned: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned[node.target.id] = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned[target.id] = node.lineno
    names = (
        "MACRO_RECORD_KEY",
        "MACRO_PLAY_KEY",
        "MACRO_REPLAY_LAST_KEY",
        "MACRO_CONTROL_KEYS",
    )
    for name in names:
        assert name in assigned, name
    parse_key_line = next(
        node.lineno
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_key"
    )
    assert assigned["MACRO_CONTROL_KEYS"] > parse_key_line
