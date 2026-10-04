"""Language-aware indentation rules and bracket pairs for the editor core.

Pure logic only -- no state, no I/O, no UI.  The buffer looks tables up here
instead of branching on language names, so covering another language later
means adding one :class:`LanguageRules` entry rather than another
``if language == ...`` inside
:class:`~yate.editor_core.buffer.TextBuffer`.

Two independent tables sit side by side:

* :data:`PAIRS` -- the bracket/quote pairs auto-completed in *every* language,
  plus :func:`pair_for` and :func:`is_pair_of` behind the buffer's
  insert / skip / paired-delete decisions;
* :class:`LanguageRules` -- what a line does to the indentation of the *next*
  line, resolved by :func:`rules_for`.

Usage::

    from yate.editor_core.indentation import indent_unit, rules_for

    rules = rules_for("python")
    unit = indent_unit(4, use_spaces=True)

The tables deliberately ignore lexical context: a quote typed inside a string
or a comment still auto-completes, matching the editor's documented V1 scope.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Paired symbols (left -> right), auto-completed in every language.
PAIRS: dict[str, str] = {"(": ")", "[": "]", "{": "}", "'": "'", '"': '"'}

#: Every closing symbol of :data:`PAIRS` -- the union of its values.
CLOSERS: frozenset[str] = frozenset(PAIRS.values())

#: Language names that select :data:`PYTHON_RULES`: the bare file suffix
#: (``py``, what ``Document.filetype`` carries) and the ``filetype`` spelling
#: users type in ``:set filetype=python``.
_PYTHON_NAMES: frozenset[str] = frozenset({"py", "python"})


@dataclass(frozen=True)
class LanguageRules:
    """What one line of text does to the indentation of the line after it.

    *block_openers* are the line-final tokens that open a block (Python: a
    trailing ``:``); *dedent_keywords* are the line-initial keywords that end
    the block the cursor sits in (``return``, ``break``, ``else`` ...), so
    such a line never gains indentation.  Instances are immutable and shared
    -- build one per language as a module constant.
    """

    block_openers: tuple[str, ...]
    dedent_keywords: frozenset[str]


#: Python: a line ending in ``:`` indents the next line one level further, and
#: the block-closing keywords stand for themselves at the current level.  The
#: keywords are stored bare -- :func:`closes_block` strips the trailing colon,
#: so ``else:`` and ``finally:`` match their bare spelling.
PYTHON_RULES: LanguageRules = LanguageRules(
    block_openers=(":",),
    dedent_keywords=frozenset(
        {
            "break",
            "continue",
            "elif",
            "else",
            "except",
            "finally",
            "pass",
            "raise",
            "return",
        }
    ),
)

#: Every other language in V1: a newline just continues the current indent.
DEFAULT_RULES: LanguageRules = LanguageRules(block_openers=(), dedent_keywords=frozenset())


def rules_for(language: str) -> LanguageRules:
    """Return the indentation rules of *language*, defaulting to :data:`DEFAULT_RULES`.

    Both the bare suffix (``py``) and the ``filetype`` spelling (``python``)
    are accepted, because documents report the former while ``:set
    filetype=...`` yields the latter.  Unknown names fall back to
    :data:`DEFAULT_RULES`, which preserves the long-standing "newline
    continues the current indent" behaviour everywhere else.
    """
    if language in _PYTHON_NAMES:
        return PYTHON_RULES
    return DEFAULT_RULES


def indent_unit(tab_width: int, use_spaces: bool) -> str:
    """Return one indentation level: *tab_width* spaces, or a single hard tab.

    Same semantics as :meth:`~yate.editor_core.buffer.TextBuffer.indent_selection`
    so an auto-indented line and a manually indented one are indistinguishable.
    """
    if use_spaces:
        return " " * tab_width
    return "\t"


def opens_block(rules: LanguageRules, line: str) -> bool:
    """Return whether *line* ends with one of *rules*' block openers.

    Trailing whitespace is irrelevant, so ``"if x:  "`` opens a block too.
    """
    stripped = line.rstrip()
    return any(stripped.endswith(opener) for opener in rules.block_openers)


def closes_block(rules: LanguageRules, line: str) -> bool:
    """Return whether *line* starts with one of *rules*' dedent keywords.

    The probe is the first whitespace-delimited word with its trailing colons
    stripped, so both the bare statements (``return x``, ``break``) and the
    compound ones that always carry a colon (``else:``, ``elif cond:``,
    ``except ValueError:``, ``finally:``) match their bare keyword.  The
    comparison is anchored at the start of the line, so ``x = returned`` and
    ``a::b`` do not.  An empty word (``"::"``, or a whitespace-only line) is in
    no set and therefore never matches.

    Such a line still *opens* a block when it also ends with an opener --
    ``else:`` satisfies both -- and V1 deliberately leaves that extra level
    alone: undoing it is a syntax-level dedent, which
    :meth:`~yate.editor_core.buffer.TextBuffer.insert_newline` does not attempt.
    Callers that do want the dedent subtract a level when both predicates hold.
    """
    words = line.strip().split(maxsplit=1)
    if not words:
        return False
    return words[0].rstrip(":") in rules.dedent_keywords


def pair_for(ch: str) -> str | None:
    """Return the symbol that completes *ch*, or ``None`` when it has no pair.

    ``None`` marks the keys that are inserted verbatim (``a``, ``,``, ``)``
    once closing); the quotes map to themselves, so typing ``'`` yields
    ``''`` with the cursor in the middle.
    """
    return PAIRS.get(ch)


def is_pair_of(left: str, right: str) -> bool:
    """Return whether *left* and *right* are the two halves of one pair.

    Drives :meth:`~yate.editor_core.buffer.TextBuffer.delete_backward`, which
    removes both halves of an emptied pair in a single keystroke.
    """
    return PAIRS.get(left) == right
