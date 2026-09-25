"""``KeymapSet``: lookups, the active keymap and switching between keymaps.

``test_registries.py`` already pins the two constructor edge cases (an empty
mapping raises ``ValueError``; an unknown active name falls back to the first
registered keymap).  This module covers the rest: the ``get`` /
``__getitem__`` / ``__iter__`` / ``names`` views, the ``name`` and ``active``
properties, ``select`` (including the "unknown name changes nothing" branch)
and ``toggle`` with one, two and three registered keymaps.
"""

from __future__ import annotations

from typing import override

import pytest

from yate.keymaps.base import KeyBinding, Keymap, parse_key
from yate.keymaps.registry import KeymapSet


class _FakeKeymap(Keymap):
    """A minimal keymap: a registry name, a label and one real binding."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.label = f"{name.title()} keys"
        super().__init__()

    @override
    def build_bindings(self) -> list[KeyBinding]:
        """One binding so the keymap behaves like a real one."""
        return [KeyBinding(parse_key("<ctrl-s>"), "save", f"save in {self.name}")]


def _set(*names: str, active: str = "") -> KeymapSet:
    """Build a KeymapSet of *names*; the active one defaults to the first."""
    keymaps: dict[str, Keymap] = {name: _FakeKeymap(name) for name in names}
    return KeymapSet(keymaps, active or names[0])


# --- lookups ---------------------------------------------------------------


def test_get_returns_the_registered_keymap() -> None:
    """A known name resolves to the very instance that was registered."""
    keymaps = _set("vim", "emacs")
    vim = keymaps.get("vim")

    assert isinstance(vim, Keymap)
    assert vim is keymaps["vim"]
    assert vim.name == "vim"


def test_get_reports_an_unknown_name() -> None:
    """An unknown name yields None (no exception, no fallback)."""
    assert _set("vim").get("nope") is None


def test_getitem_returns_the_registered_keymap() -> None:
    """Indexing hits the same instance as ``get``."""
    keymaps = _set("vim", "emacs")

    assert keymaps["emacs"] is keymaps.get("emacs")
    assert keymaps["emacs"].name == "emacs"


def test_getitem_raises_key_error_for_an_unknown_name() -> None:
    """Indexing an unknown name raises KeyError (unlike ``get``)."""
    with pytest.raises(KeyError):
        _set("vim")["nope"]


def test_iter_yields_every_registered_name() -> None:
    """Iteration yields the keys, both as a set and as an ordered list."""
    keymaps = _set("vim", "emacs", "nano")

    assert set(keymaps) == {"vim", "emacs", "nano"}
    assert list(keymaps) == ["vim", "emacs", "nano"]


def test_names_are_sorted() -> None:
    """``names`` is the sorted view the help overlay and completion read."""
    keymaps = _set("vim", "emacs", "nano")

    assert keymaps.names() == ["emacs", "nano", "vim"]


# --- the active keymap -----------------------------------------------------


def test_active_is_the_keymap_named_by_name() -> None:
    """``active`` is the registered instance behind ``name``."""
    keymaps = _set("vim", "emacs", active="emacs")

    assert keymaps.name == "emacs"
    assert keymaps.active is keymaps.get("emacs")


def test_select_activates_a_known_keymap() -> None:
    """A known name is activated and reported as selected."""
    keymaps = _set("vim", "emacs")

    assert keymaps.select("emacs") is True
    assert keymaps.name == "emacs"
    assert keymaps.active is keymaps.get("emacs")


def test_select_keeps_the_active_keymap_for_an_unknown_name() -> None:
    """An unknown name is refused: False, and nothing changes."""
    keymaps = _set("vim", "emacs")
    before = keymaps.active

    assert keymaps.select("nope") is False
    assert keymaps.name == "vim"
    assert keymaps.active is before


# --- toggle ----------------------------------------------------------------


def test_toggle_switches_between_two_keymaps() -> None:
    """With two keymaps each call flips to the other one."""
    keymaps = _set("vim", "emacs")

    assert keymaps.toggle() == "emacs"
    assert keymaps.active is keymaps.get("emacs")
    assert keymaps.toggle() == "vim"
    assert keymaps.active is keymaps.get("vim")


def test_toggle_with_a_single_keymap_keeps_the_active_one() -> None:
    """With nothing else to switch to, the same name comes back."""
    keymaps = _set("vim")
    before = keymaps.active

    assert keymaps.toggle() == "vim"
    assert keymaps.active is before


def test_toggle_picks_the_first_other_name_in_sorted_order() -> None:
    """With three keymaps the first name that is not the active one wins."""
    keymaps = _set("vim", "emacs", "nano")

    assert keymaps.toggle() == "emacs"
    assert keymaps.toggle() == "nano"
    assert keymaps.toggle() == "emacs"


# --- construction ----------------------------------------------------------


def test_init_copies_the_given_mapping() -> None:
    """The set snapshots the mapping: later edits to it are invisible."""
    source: dict[str, Keymap] = {"vim": _FakeKeymap("vim"), "emacs": _FakeKeymap("emacs")}
    keymaps = KeymapSet(source, "vim")
    vim = keymaps.active

    source["nano"] = _FakeKeymap("nano")
    del source["vim"]

    assert keymaps.names() == ["emacs", "vim"]
    assert keymaps.get("nano") is None
    assert keymaps.active is vim
    assert keymaps["vim"] is vim
