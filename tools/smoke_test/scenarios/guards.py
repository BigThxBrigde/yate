"""Guard scenarios: read-only refusal, unknown command / action, prompt
tab completion and the search / go-to-line message branches.

Every string asserted here is copied verbatim from the product source (see
the per-scenario docstrings for the file and line it comes from), so a
reworded message fails loudly instead of silently passing a substring test.
The scenarios are grouped by *what they guard* rather than by widget:

* ``readonly_refuses_edits``      -- the read-only flag set by
  ``:set readonly=`` really refuses typing and saving;
* ``unknown_command_and_action``  -- the two "I do not know this" branches
  name the offending token instead of failing silently;
* ``prompt_tab_completion``       -- bash-style tab completion of command
  names, ``:set`` values and open-prompt paths;
* ``search_and_goto_messages``    -- the message-only branches of ``f3`` /
  ``ctrl+f`` / ``ctrl+g``.

Teardown: each scenario restores what it touched.  The read-only flag is
switched back off, the theme is set back to ``mocha`` and the prompt is always
cancelled rather than submitted -- see
:func:`_unknown_command_and_action` for why the temporary ``<f6>`` binding
needs no ``remove_binding`` call.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.events import Key

from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from ._base import goto, message_text, run_command, type_text
from yate.app import YateApp
from yate.editor_view import theme
from yate.keymaps.base import Keymap
from yate.keymaps.vsc import VscKeymap

__all__ = ["SCENARIOS"]

# Verbatim product strings (see the docstrings for their source location).
# Kept as module constants so a rewording in yate/ breaks the scenario that
# quotes them instead of silently drifting.
_READONLY_NOTICE: str = "buffer is read-only (:set readonly=false to unlock)"
#: ``Editor.readonly_notice`` -- yate/editor.py.
_READONLY_SAVE: str = (
    "cannot save a read-only buffer; use :saveas to write elsewhere"
)
#: ``DocumentFlows.save_document`` -- yate/document_flows.py.
_UNKNOWN_COMMAND: str = "not an editor command: nosuchcmd (try :help)"
#: ``Editor.run_command`` -- yate/editor.py.
_UNKNOWN_ACTION: str = "unknown action: nosuch_action"
#: ``Keymap.dispatch`` -- yate/keymaps/base.py.
#: ``PromptFlows.find_next`` -- yate/prompt_flows.py (the em dash of the
#: full sentence is not quoted: only the stable prefix is asserted).
_NO_ACTIVE_SEARCH: str = "no active search"
_NO_MATCHES: str = "no matches for"
#: ``PromptFlows.find_next`` / ``_do_replace`` -- yate/prompt_flows.py.
_NOT_A_LINE_NUMBER: str = "not a line number"
#: ``PromptFlows.goto_line_command`` -- yate/prompt_flows.py.

#: Raw sequence behind ``<f6>`` (``yate.keymaps.base.SPECIAL_KEYS``).  Spelled
#: out instead of calling ``parse_key`` so the leak check does not depend on
#: the very codec that turns the key into this sequence.
_F6_RAW: str = "\x1b[17~"


def _message(app: YateApp) -> str:
    """The bottom-bar message with its Rich colour markup removed.

    ``_base.message_text`` goes through ``plain_text``, which only unwraps a
    ``Text`` renderable.  ``PromptBar._render_message`` writes a *markup
    string* (``"[#f9e2af]...[/]"``) into the ``Static``, so ``plain_text``
    hands back the tags verbatim and an exact-match assertion on a product
    message can never match.  Parsing the markup back to a ``Text`` and
    taking ``.plain`` is the inverse of what the bar did (it escapes the
    message body before wrapping it), so this returns the message verbatim.
    """
    return Text.from_markup(str(message_text(app))).plain


def _binding_action(keymap: Keymap, raw: str) -> str | None:
    """Action name bound to *raw* in *keymap*, or ``None`` when unbound."""
    binding = keymap.lookup(raw)
    if binding is None:
        return None
    action = binding.action
    # ``KeyBinding.action`` is ``str | ActionFunc``; a smoke scenario only
    # ever registers named actions, so a callable is reported as unnamed
    # rather than leaking its repr into the assertion.
    return action if isinstance(action, str) else None


async def _readonly_refuses_edits(tmp: Path) -> ScenarioResult:
    """``:set readonly=true`` refuses typing and both save paths.

    ``Editor.set_readonly`` flips ``session.doc.buffer.read_only``; every
    write funnels through a guarded ``TextBuffer`` mutation, so
    ``Editor.handle_raw_key`` catches ``BufferReadOnlyError`` and shows
    ``readonly_notice`` instead of editing (yate/editor.py).  ``:w`` /
    ``ctrl+s`` reach ``DocumentFlows.save_document``, which refuses earlier
    with its own message (yate/document_flows.py).
    """
    target = tmp / "ro.txt"
    target.write_text("seed", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "set readonly=true")
        doc = app.editor.session.doc
        checks.append(Check("readonly_on", True, doc.buffer.read_only))

        await type_text(pilot, "X")
        checks.append(Check("text_unchanged", "seed",
                            app.editor.session.buffer.lines[0]))
        checks.append(Check("not_modified", False, doc.modified))
        checks.append(Check("typing_warned", _READONLY_NOTICE,
                            _message(app)))

        await pilot.press("ctrl+s")
        await pilot.pause()
        checks.append(Check("ctrl_s_refused", _READONLY_SAVE, _message(app)))
        await run_command(pilot, "w")
        checks.append(Check("colon_w_refused", _READONLY_SAVE, _message(app)))
        checks.append(Check("disk_untouched", "seed",
                            target.read_text(encoding="utf-8")))

        await run_command(pilot, "set readonly=false")
        checks.append(Check("readonly_off", False, doc.buffer.read_only))
        await type_text(pilot, "Y")
        checks.append(Check("editable_again", "Yseed",
                            app.editor.session.buffer.lines[0]))
        checks.append(Check("modified_after_edit", True, doc.modified))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("readonly_refuses_edits", checks, rows)


async def _unknown_command_and_action(tmp: Path) -> ScenarioResult:
    """An unknown ``:`` command and an unknown action both name themselves.

    ``Editor.run_command`` warns ``not an editor command: <name>`` when the
    command registry misses (yate/editor.py).  ``Editor.execute_action``
    returns ``False`` for an unregistered action, and ``Keymap.dispatch``
    turns that into an ``unknown action: <name>`` message plus a ``False``
    return, i.e. the key is reported as *unhandled* rather than swallowed
    (yate/keymaps/base.py).

    ``<f6>`` has no built-in binding, so the scenario registers one pointing
    at the missing action and presses the key.  ``Keymap`` exposes no
    ``remove_binding``, but it does not need one here: ``YateApp`` builds a
    brand new ``VscKeymap`` for every ``Editor`` (``yate/editor.py``), so the
    binding dies with the app.  ``binding_not_leaked`` proves that instead of
    asserting it: a freshly constructed keymap has no ``<f6>`` entry.
    """
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await run_command(pilot, "nosuchcmd")
        checks.append(Check("unknown_command", _UNKNOWN_COMMAND, _message(app)))
        checks.append(Check("execute_action_false", False,
                            app.editor.execute_action("nosuch_action")))

        keymap = app.editor.keymaps.active
        keymap.add_binding("<f6>", "nosuch_action")
        checks.append(Check("binding_registered", "nosuch_action",
                            _binding_action(keymap, _F6_RAW)))
        await pilot.press("f6")
        await pilot.pause()
        checks.append(Check("unknown_action", _UNKNOWN_ACTION, _message(app)))
        # The key reached the keymap (the message proves it) and was *not*
        # turned into text: the escape sequence is not a printable char, so
        # the buffer must still hold the empty seed line.
        checks.append(Check("no_phantom_insert", "",
                            app.editor.session.buffer.lines[0]))
        # The dispatch contract itself: ``handle_key`` reports the unknown
        # action as unhandled (R10 lets the caller keep looking) instead of
        # consuming it as a successful edit.
        checks.append(Check(
            "dispatch_unhandled", False,
            app.editor.handle_key(Key("f6", None)),
        ))
        checks.append(Check("binding_not_leaked", None,
                            _binding_action(VscKeymap(), _F6_RAW)))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("unknown_command_and_action", checks, rows)


async def _prompt_tab_completion(tmp: Path) -> ScenarioResult:
    """Tab completes command names, ``:set`` values and open-prompt paths.

    ``CommandInput._do_tab_completion`` (yate/editor_view/commandline.py)
    drives bash-style completion: one match is applied at once, several
    matches extend to the longest common prefix and further tabs cycle while
    the value is one of the matches.  The candidates come from
    ``prompt_completions`` (yate/prompt_completion.py): command names, the
    ``:set`` option list, the per-option value enums and filesystem entries
    for the open prompt.

    Measured behaviour worth pinning (it is not what the code reads like):
    the *value enum* does not cycle.  ``prompt_completions`` returns
    ``"set theme=<name>"`` for every theme, so after the first tab the value
    is ``"set theme=frappe"``; a second tab recomputes the candidates from
    that completed value, the value filter ``v != value`` now excludes the
    only prefix match, and the round restarts.  The *path* candidates do
    cycle, because the completed value is still a directory prefix there.
    """
    (tmp / "sub").mkdir()
    (tmp / "sub" / "inner.txt").write_text("inner", encoding="utf-8")
    (tmp / "sub2.txt").write_text("sibling", encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        bar = app.editor.prompt_bar
        assert bar is not None

        # --- command name completion: "set re" -> the one "readonly" option
        await pilot.press("f5")
        await pilot.pause()
        await type_text(pilot, "set re")
        await pilot.press("tab")
        await pilot.pause()
        checks.append(Check("command_mode", "command", bar.active_mode))
        checks.append(Check("option_completed", "set readonly", bar.input.value))
        # A single match was applied at once, so a second tab finds nothing
        # and leaves the value alone instead of guessing.
        await pilot.press("tab")
        await pilot.pause()
        checks.append(Check("tab_noop", "set readonly", bar.input.value))
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("cancelled", None, bar.active_mode))

        # --- value enum completion: "set theme=" takes the first theme name
        await pilot.press("f5")
        await pilot.pause()
        await type_text(pilot, "set theme=")
        checks.append(Check("theme_candidates", 8,
                            len(bar.completer("set theme=", "command"))))
        await pilot.press("tab")
        await pilot.pause()
        # Several themes match and their common prefix is not longer than
        # what was typed, so the first tab starts the round at matches[0].
        checks.append(Check("first_value", "set theme=frappe", bar.input.value))
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        checks.append(Check("theme_applied", "frappe", theme.active().name))
        await run_command(pilot, "set theme=mocha")
        checks.append(Check("theme_restored", "mocha", theme.active().name))

        # --- path candidates in the open prompt: "su" -> "sub" then "sub/"
        await pilot.press("ctrl+o")
        await pilot.pause()
        checks.append(Check("open_mode", "open", bar.active_mode))
        await type_text(pilot, "su")
        await pilot.press("tab")
        await pilot.pause()
        # Two candidates share the prefix "sub", which is longer than "su",
        # so the common prefix is applied and the round is kept open.
        checks.append(Check("path_common_prefix", "sub", bar.input.value))
        await pilot.press("tab")
        await pilot.pause()
        # The value is now a match, so the next tab cycles to it.
        checks.append(Check("path_cycled", "sub/", bar.input.value))
        await pilot.press("tab")
        await pilot.pause()
        # "sub/" is a directory prefix, so the candidates are its contents
        # and the single entry is applied at once.
        checks.append(Check("path_descended", "sub/inner.txt", bar.input.value))
        # Cancelled rather than submitted: the scenario is about the
        # candidates, and opening a path would re-root the workspace.
        await pilot.press("escape")
        await pilot.pause()
        checks.append(Check("open_cancelled", None, bar.active_mode))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("prompt_tab_completion", checks, rows)


async def _search_and_goto_messages(tmp: Path) -> ScenarioResult:
    """The message-only branches of ``f3`` / ``ctrl+f`` / ``ctrl+g``.

    ``PromptFlows.find_next`` warns when no search is running and when the
    pattern has no match; ``goto_line_command`` rejects a non-numeric answer
    and ``goto_line`` clamps an out-of-range line to the last row while
    dropping the selection anchor (yate/prompt_flows.py).
    """
    target = tmp / "lines.txt"
    target.write_text("l1\nl2\nl3\nl4\nl5", encoding="utf-8")
    app = new_app(target=target)
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        buf = app.editor.session.buffer

        await pilot.press("f3")
        await pilot.pause()
        checks.append(Check("no_active_search", True,
                            _NO_ACTIVE_SEARCH in _message(app)))
        checks.append(Check("no_query", "", app.editor.session.search.query))

        await pilot.press("ctrl+f")
        await pilot.pause()
        await type_text(pilot, "zzz")
        await pilot.press("enter")
        await pilot.pause()
        checks.append(Check("no_matches", True, _NO_MATCHES in _message(app)))
        checks.append(Check("zero_match_spans", 0,
                            len(app.editor.session.search.matches)))

        # ctrl+g with a non-numeric answer: message only, cursor unmoved.
        await goto(pilot, "abc")
        checks.append(Check("not_a_line_number", True,
                            _NOT_A_LINE_NUMBER in _message(app)))
        checks.append(Check("cursor_kept", (0, 0), buf.cursor))

        # A selection first, so the anchor clearing is observable.
        await pilot.press("ctrl+a")
        await pilot.pause()
        checks.append(Check("anchor_set", True, buf.has_selection()))
        await goto(pilot, "999")
        checks.append(Check("clamped_to_last_row", 4, buf.row))
        checks.append(Check("anchor_cleared", None, buf.anchor))
        checks.append(Check("search_cleared", "",
                            app.editor.session.search.query))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("search_and_goto_messages", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("readonly_refuses_edits", _readonly_refuses_edits,
             ("files", "regression")),
    Scenario("unknown_command_and_action", _unknown_command_and_action,
             ("files", "regression")),
    Scenario("prompt_tab_completion", _prompt_tab_completion,
             ("command", "view")),
    Scenario("search_and_goto_messages", _search_and_goto_messages,
             ("search",)),
]
