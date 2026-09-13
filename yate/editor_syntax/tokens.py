"""Shared token contract of the syntax layer.

A :class:`Token` is one highlighted span on a single line; ``kind`` is the
semantic name of the construct (``keyword``, ``string``, ...).  The view
layer maps kinds to colors through the active theme via :data:`SYNTAX_KINDS`,
so this module is the single place where the set of valid kinds is defined:
both built-in backends (regex, tree-sitter) and custom highlighters must
only emit kinds listed there; anything else renders with the default
foreground color.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    """A highlighted span on one line (character columns, half-open)."""

    start: int
    end: int
    kind: str


#: Token kind -> syntax palette attribute name on
#: :class:`~yate.editor_view.theme.Theme`.  This is the contract every
#: syntax backend must stick to.
SYNTAX_KINDS: dict[str, str] = {
    "keyword": "syn_keyword",
    "string": "syn_string",
    "number": "syn_number",
    "comment": "syn_comment",
    "function": "syn_function",
    "type": "syn_type",
    "constant": "syn_constant",
    "builtin": "syn_builtin",
    "decorator": "syn_decorator",
    "operator": "syn_operator",
    "property": "syn_property",
    "heading": "syn_keyword",
    "link": "syn_function",
    "emphasis": "fg_bright",
}
