"""The key notation layer: spec parsing, its inverse and keymap dispatch.

``parse_key`` turns human specs into the raw strings a terminal sends, and
``key_name`` turns them back for the help overlay; the two are only partly
inverse because several specs share a code (``<ctrl-[>`` *is* ESC).  The rest
of the module -- bindings, lookups, dispatch and the default self-inserting
fallback -- is what every keymap subclass rests on.
"""

from __future__ import annotations


from collections.abc import Callable

import pytest

from yate.config import YateConfig
from yate.keymaps.base import ActionContext, KeyBinding, Keymap, KeyUi, key_name, parse_key
from yate.session import EditorSession


def _ui(
    execute: Callable[[str], bool] = lambda _name: True,
    on_message: Callable[[str], None] = lambda _text: None,
) -> KeyUi:
    """A KeyUi recording what it is asked to do (inert by default)."""
    return KeyUi(
        execute_action=execute,
        message=on_message,
        command_prompt=lambda: None,
        find_prompt=lambda _forward: None,
        goto_prompt=lambda: None,
        toggle_keymap=lambda: None,
    )


def _context(ui: KeyUi | None = None) -> ActionContext:
    """A real action context (the session plus the given or inert UI callbacks)."""
    session = EditorSession(YateConfig())
    session.new_buffer()
    return ActionContext(session, ui if ui is not None else _ui())


class _SampleKeymap(Keymap):
    """A keymap whose bindings come from :meth:`build_bindings`."""

    name = "sample"
    label = "Sample"

    def build_bindings(self) -> list[KeyBinding]:
        return [
            KeyBinding(parse_key("<ctrl-s>"), "save", "write the file", "file"),
            KeyBinding(parse_key("<ctrl-q>"), "quit", "leave the editor", "file"),
        ]


# --- parse_key --------------------------------------------------------------


def test_parse_key_returns_plain_specs_unchanged() -> None:
    """A spec that is not bracketed is already a raw key."""
    assert parse_key("a") == "a"
    assert parse_key("abc") == "abc"


def test_parse_key_maps_letter_control_keys_to_c0_codes() -> None:
    """ctrl+letter follows the terminal convention: subtract 64 from the uppercase."""
    assert parse_key("<ctrl-a>") == "\x01"
    assert parse_key("<ctrl-s>") == "\x13"
    assert parse_key("<ctrl-z>") == "\x1a"


def test_parse_key_maps_ctrl_space_to_nul() -> None:
    """ctrl+space is NUL, not the space character."""
    assert parse_key("<ctrl-space>") == "\x00"


def test_parse_key_maps_the_at_to_underscore_range() -> None:
    """ctrl-@ .. ctrl-_ are the remaining C0 codes (brackets included)."""
    assert parse_key("<ctrl-@>") == "\x00"
    assert parse_key("<ctrl-[>") == "\x1b"
    assert parse_key("<ctrl-]>") == "\x1d"
    assert parse_key("<ctrl-_>") == "\x1f"


def test_parse_key_encodes_control_digits_as_csi_u() -> None:
    """ctrl+digits have no C0 code, so they use the kitty CSI-u encoding."""
    assert parse_key("<ctrl-1>") == "\x1b[49;5u"
    assert parse_key("<ctrl-9>") == "\x1b[57;5u"


def test_parse_key_uppercases_shifted_keys() -> None:
    """shift on a single character produces the uppercase form."""
    assert parse_key("<shift-a>") == "A"


def test_parse_key_prefixes_alt_keys_with_escape() -> None:
    """alt prefixes the key with ESC."""
    assert parse_key("<alt-a>") == "\x1ba"


def test_parse_key_ignores_case() -> None:
    """Specs are case-insensitive."""
    assert parse_key("<CTRL-S>") == "\x13"
    assert parse_key("<Shift-A>") == "A"


def test_parse_key_resolves_special_key_names() -> None:
    """The canonical names map to the sequences terminals send."""
    assert parse_key("<enter>") == "\r"
    assert parse_key("<esc>") == "\x1b"
    assert parse_key("<tab>") == "\t"
    assert parse_key("<backspace>") == "\x7f"
    assert parse_key("<delete>") == "\x1b[3~"
    assert parse_key("<up>") == "\x1b[A"
    assert parse_key("<f1>") == "\x1bOP"


def test_parse_key_rejects_unknown_key_names() -> None:
    """A name that is neither special nor a single character is an error."""
    with pytest.raises(ValueError, match="unknown key name"):
        parse_key("<nope>")


def test_parse_key_rejects_ctrl_on_multichar_special_keys() -> None:
    """ctrl has no encoding for a multi-character special key."""
    with pytest.raises(ValueError, match="ctrl"):
        parse_key("<ctrl-enter>")


def test_parse_key_rejects_ctrl_combined_with_alt() -> None:
    """ESC-prefixing first leaves ctrl with more than one character."""
    with pytest.raises(ValueError, match="ctrl requires a single character"):
        parse_key("<ctrl-alt-a>")


def test_parse_key_rejects_ctrl_on_unsupported_characters() -> None:
    """Characters outside the @.._ and digit ranges cannot be ctrl-encoded."""
    with pytest.raises(ValueError, match="unsupported ctrl key"):
        parse_key("<ctrl-.>")


# --- key_name ---------------------------------------------------------------


def test_key_name_uses_the_alias_table_first() -> None:
    """Terminal variants are reported under their canonical alias."""
    assert key_name("\x1b[1~") == "<home>"
    assert key_name("\x1b[4~") == "<end>"
    assert key_name("\x1b[Z") == "<shift-tab>"
    assert key_name("\x1b[1;5D") == "<ctrl-left>"


def test_key_name_prefers_the_canonical_special_name() -> None:
    """return/escape are skipped so the pair reported is enter/esc."""
    assert key_name("\r") == "<enter>"
    assert key_name("\x1b") == "<esc>"


def test_key_name_reports_special_sequences() -> None:
    """Special keys are rendered back as their bracketed names."""
    assert key_name("\t") == "<tab>"
    assert key_name(" ") == "<space>"
    assert key_name("\x7f") == "<backspace>"
    assert key_name("\x1b[3~") == "<delete>"
    assert key_name("\x1b[A") == "<up>"
    assert key_name("\x1bOP") == "<f1>"
    assert key_name("\x1b[24~") == "<f12>"


def test_key_name_decodes_single_control_characters() -> None:
    """C0 codes are rendered as ctrl-<letter> (NUL as ctrl-space)."""
    assert key_name("\x00") == "<ctrl-space>"
    assert key_name(chr(1)) == "<ctrl-a>"
    assert key_name(chr(2)) == "<ctrl-b>"
    assert key_name(chr(26)) == "<ctrl-z>"


def test_key_name_returns_plain_characters_unchanged() -> None:
    """An ordinary printable character is its own label."""
    assert key_name("a") == "a"
    assert key_name("Z") == "Z"
    assert key_name("!") == "!"


def test_key_name_reports_a_two_byte_escape_sequence_as_alt() -> None:
    """ESC followed by one character is alt-<char>."""
    assert key_name("\x1ba") == "<alt-a>"
    assert key_name("\x1bA") == "<alt-A>"


def test_key_name_decodes_csi_u_modifier_bits() -> None:
    """The kitty CSI-u encoding carries shift(1), alt(2) and ctrl(4) bits."""
    assert key_name("\x1b[97;1u") == "<shift-a>"
    assert key_name("\x1b[97;3u") == "<shift-alt-a>"
    assert key_name("\x1b[97;5u") == "<shift-ctrl-a>"
    assert key_name("\x1b[97;7u") == "<shift-alt-ctrl-a>"
    assert key_name("\x1b[49;5u") == "<shift-ctrl-1>"


def test_key_name_falls_back_to_repr() -> None:
    """An unrecognised sequence is shown as its repr rather than guessed at."""
    assert key_name("\x1b[1;5X") == "'\\x1b[1;5X'"
    assert key_name("abc") == "'abc'"


# --- round trip -------------------------------------------------------------


def test_key_name_inverts_parse_key_for_reversible_specs() -> None:
    """Specs with a code of their own survive the parse / name round trip."""
    for spec in (
        "a",
        "<ctrl-s>",
        "<ctrl-space>",
        "<alt-a>",
        "<enter>",
        "<esc>",
        "<tab>",
        "<backspace>",
        "<delete>",
        "<insert>",
        "<up>",
        "<down>",
        "<left>",
        "<right>",
        "<home>",
        "<end>",
        "<pageup>",
        "<pagedown>",
        "<f1>",
        "<f12>",
        "<space>",
    ):
        assert key_name(parse_key(spec)) == spec


def test_key_name_normalises_specs_that_share_a_code() -> None:
    """Lossy specs come back in canonical form: ctrl-[ is ESC, shift-a is A."""
    assert key_name(parse_key("<ctrl-[>")) == "<esc>"
    assert key_name(parse_key("<shift-a>")) == "A"
    assert key_name(parse_key("<ctrl-1>")) == "<shift-ctrl-1>"


# --- KeyBinding -------------------------------------------------------------


def test_key_label_is_the_human_readable_key_name() -> None:
    """The help overlay reads the label, which is key_name of the raw key."""
    assert KeyBinding(parse_key("<ctrl-s>"), "save").key_label == "<ctrl-s>"
    assert KeyBinding(parse_key("<alt-a>"), "mark").key_label == "<alt-a>"
    assert KeyBinding("a", "self-insert").key_label == "a"


# --- Keymap: construction and lookup ----------------------------------------


def test_build_bindings_populates_bindings_and_the_index() -> None:
    """A subclass table is indexed by raw key at construction time."""
    keymap = _SampleKeymap()

    assert [b.key for b in keymap.bindings] == ["\x13", "\x11"]
    assert keymap.lookup("\x13") is keymap.bindings[0]
    assert keymap.lookup("\x11") is keymap.bindings[1]


def test_lookup_returns_none_for_an_unbound_key() -> None:
    """A key with no binding is reported as missing, not as an error."""
    assert _SampleKeymap().lookup("\x01") is None
    assert Keymap().lookup("a") is None


def test_add_binding_appends_a_new_key() -> None:
    """Registering a fresh key appends it to the binding list."""
    keymap = _SampleKeymap()
    keymap.add_binding("<ctrl-p>", "print")

    assert len(keymap.bindings) == 3
    binding = keymap.lookup("\x10")
    assert binding is not None
    assert binding is keymap.bindings[-1]
    assert binding.action == "print"
    assert binding.category == "extension"


def test_add_binding_replaces_a_duplicate_key_in_place() -> None:
    """Re-registering a key drops the stale entry instead of shadowing it."""
    keymap = _SampleKeymap()
    keymap.add_binding("<ctrl-s>", "write-all", "write every buffer")

    assert len(keymap.bindings) == 2
    assert keymap.bindings[0].key == "\x11"
    binding = keymap.lookup("\x13")
    assert binding is not None
    assert binding is keymap.bindings[-1]
    assert binding.action == "write-all"
    assert binding.description == "write every buffer"


def test_add_binding_converts_bracketed_and_single_char_specs() -> None:
    """A bracketed spec is parsed; a longer bare spec is passed through as-is."""
    keymap = Keymap()
    keymap.add_binding("<ctrl-s>", "save")
    keymap.add_binding("a", "self-insert")
    keymap.add_binding("abc", "literal")

    assert [b.key for b in keymap.bindings] == ["\x13", "a", "abc"]
    assert keymap.lookup("\x13") is not None
    assert keymap.lookup("a") is not None
    assert keymap.lookup("abc") is not None


# --- Keymap: dispatch -------------------------------------------------------


def test_dispatch_calls_a_callable_action() -> None:
    """A direct callable is invoked with the context and counts as handled."""
    seen: list[ActionContext] = []
    keymap = Keymap()
    keymap.add_binding("<ctrl-s>", seen.append)

    ctx = _context()
    binding = keymap.lookup("\x13")
    assert binding is not None
    assert keymap.dispatch(binding, ctx) is True
    assert seen == [ctx]


def test_dispatch_reports_true_for_a_known_string_action() -> None:
    """A named action the UI can execute is handled."""
    executed: list[str] = []

    def execute(name: str) -> bool:
        executed.append(name)
        return True

    ctx = _context(_ui(execute=execute))
    keymap = _SampleKeymap()
    binding = keymap.lookup("\x13")
    assert binding is not None
    assert keymap.dispatch(binding, ctx) is True
    assert executed == ["save"]


def test_dispatch_reports_an_unknown_action_and_returns_false() -> None:
    """An unregistered name is reported and handed back as unhandled."""
    messages: list[str] = []

    def execute(_name: str) -> bool:
        return False

    def message(text: str) -> None:
        messages.append(text)

    ctx = _context(_ui(execute=execute, on_message=message))
    keymap = Keymap()
    keymap.add_binding("<ctrl-s>", "no-such-action")

    binding = keymap.lookup("\x13")
    assert binding is not None
    assert keymap.dispatch(binding, ctx) is False
    assert messages == ["unknown action: no-such-action"]


def test_handle_key_dispatches_a_bound_key() -> None:
    """A bound key runs its action instead of being inserted."""
    seen: list[ActionContext] = []
    keymap = Keymap()
    keymap.add_binding("<ctrl-s>", seen.append)

    ctx = _context()
    assert keymap.handle_key(ctx, "\x13") is True
    assert len(seen) == 1
    assert ctx.buffer.get_text() == ""


def test_handle_key_falls_back_to_the_unbound_handler() -> None:
    """An unbound key is left to handle_unbound."""
    keymap = Keymap()
    ctx = _context()

    assert keymap.handle_key(ctx, "x") is True
    assert ctx.buffer.get_text() == "x"


def test_handle_unbound_inserts_printable_characters() -> None:
    """The default fallback self-inserts single printable characters."""
    ctx = _context()

    assert Keymap().handle_unbound(ctx, "h") is True
    assert Keymap().handle_unbound(ctx, "i") is True
    assert ctx.buffer.get_text() == "hi"


def test_handle_unbound_rejects_non_printable_and_multichar_keys() -> None:
    """Sequences and control codes are not inserted; the buffer is untouched."""
    ctx = _context()
    keymap = Keymap()

    assert keymap.handle_unbound(ctx, "\x1b[A") is False
    assert keymap.handle_unbound(ctx, "\x00") is False
    assert keymap.handle_unbound(ctx, "ab") is False
    assert ctx.buffer.get_text() == ""


# --- ActionContext ----------------------------------------------------------


def test_action_context_exposes_the_session_buffer_and_doc() -> None:
    """Actions reach the edited text through the context shortcuts."""
    ctx = _context()

    assert ctx.buffer is ctx.session.buffer
    assert ctx.doc is ctx.session.doc


def test_action_context_carries_the_ui_callbacks() -> None:
    """The UI record is the only channel an action has to the editor."""
    messages: list[str] = []

    def message(text: str) -> None:
        messages.append(text)

    ui = _ui(on_message=message)
    ctx = _context(ui)

    assert ctx.ui is ui
    ctx.ui.message("hello")
    assert messages == ["hello"]


def test_sample_keymap_keeps_its_own_identity() -> None:
    """Subclass name/label defaults are what the help overlay prints."""
    assert Keymap().name == "base"
    assert _SampleKeymap().name == "sample"
    assert _SampleKeymap().label == "Sample"


def test_binding_action_accepts_both_names_and_callables() -> None:
    """A binding action is either an action name or a direct callable."""
    actions: list[str | Callable[[ActionContext], None]] = ["save", lambda _ctx: None]

    assert KeyBinding("\x13", actions[0]).action == "save"
    assert callable(KeyBinding("\x13", actions[1]).action)
