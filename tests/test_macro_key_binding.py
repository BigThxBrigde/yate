"""The shared macro prefix key: one constant, two built-in tables.

Guards the macro record / replay keymap wiring (plan b, wave-1):
``MACRO_PREFIX_KEY`` is a single L0 constant referenced by both
``build_bindings`` tables, it resolves to the same ``macro_prefix`` action in
both, it claims no vim reserved key and no conflict, and neither table
hard-codes the ``<f6>`` literal.  The vim keymap overrides
``take_pending_count`` to consume the typed count prefix (``3@a``); the
table-driven keymap keeps the default (always 1).
"""

from __future__ import annotations

import ast
from pathlib import Path

from yate.keymaps.base import parse_key
from yate.keymaps.conflicts import find_key_conflicts
from yate.keymaps.keys import MACRO_PREFIX_KEY, SPECIAL_KEYS
from yate.keymaps.vim import RESERVED_KEYS, VimKeymap
from yate.keymaps.vsc import VscKeymap

_RAW: str = parse_key(MACRO_PREFIX_KEY)


def test_macro_keys_are_shared_constants() -> None:
    """The ``<f6>`` constant resolves to f6 and both tables reference it.

    Scenario: the L0 constant and both built-in tables.  Assertions: the
    constant is the ``<f6>`` notation mapping to the f6 raw code; each
    ``build_bindings`` body mentions ``MACRO_PREFIX_KEY`` by name and no
    ``"<f6>"`` string literal appears in either table (AC3).
    """
    assert MACRO_PREFIX_KEY == "<f6>"
    assert _RAW == SPECIAL_KEYS["f6"] == "\x1b[17~"
    base = Path(__file__).resolve().parent.parent / "yate" / "keymaps"
    for module in ("vsc.py", "vim.py"):
        source = (base / module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        bindings_body: list[ast.stmt] | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "build_bindings":
                bindings_body = list(node.body)
                break
        assert bindings_body is not None, module
        body = ast.Module(body=bindings_body, type_ignores=[])
        names = [
            sub
            for sub in ast.walk(body)
            if isinstance(sub, ast.Name) and sub.id == "MACRO_PREFIX_KEY"
        ]
        assert names != [], module
        literals = [
            sub
            for sub in ast.walk(body)
            if isinstance(sub, ast.Constant) and sub.value == "<f6>"
        ]
        assert literals == [], module


def test_macro_keys_resolve_identically_in_both_keymaps() -> None:
    """Both built-in tables expose ``macro_prefix`` on the same raw key."""
    vsc_binding = VscKeymap().lookup(_RAW)
    vim_binding = VimKeymap().lookup(_RAW)
    assert vsc_binding is not None
    assert vim_binding is not None
    assert vsc_binding.action == "macro_prefix"
    assert vim_binding.action == "macro_prefix"
    assert vsc_binding.key == vim_binding.key == _RAW


def test_macro_keys_are_not_reserved_or_conflicting() -> None:
    """The macro raw key claims no vim reserved key and no conflict class.

    Scenario: the full conflict scan over both built-in tables.  Assertions:
    the f6 raw code is absent from ``RESERVED_KEYS`` and no conflict class in
    either table claims it, so the single binding row per table stays intact.
    """
    assert _RAW not in RESERVED_KEYS
    vsc_conflicts = find_key_conflicts(VscKeymap())
    vim_conflicts = find_key_conflicts(VimKeymap(), reserved=RESERVED_KEYS)
    for conflicts in (vsc_conflicts, vim_conflicts):
        assert not [c for c in conflicts if c.raw == _RAW]


def test_vim_take_pending_count_consumes_and_clears() -> None:
    """A vim count prefix is consumed once, then the default 1 applies.

    Scenario: ``VimKeymap`` with ``count_str = "3"`` (the ``3@a`` form).
    Assertions: the first ``take_pending_count()`` returns 3 and clears the
    pending digits; the next call returns the default 1.
    """
    km = VimKeymap()
    km.count_str = "3"
    assert km.take_pending_count() == 3
    assert km.count_str == ""
    assert km.take_pending_count() == 1


def test_vsc_take_pending_count_returns_one() -> None:
    """The table-driven keymap holds no count state: always the default 1."""
    km = VscKeymap()
    assert km.take_pending_count() == 1
    assert km.take_pending_count() == 1
