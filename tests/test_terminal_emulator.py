"""The headless VT emulator: input mapping, grid edits and the view API.

Everything is driven through :meth:`TerminalEmulator.feed` and the public
surface (``grid`` / ``cursor`` / ``view_lines`` / ``max_scroll`` /
``resize``), so no Textual app and no real PTY is involved.
"""

from __future__ import annotations

from yate.editor_term.emulator import (
    ANSI_16_RGB,
    Cell,
    TerminalEmulator,
    key_to_terminal,
    palette_color,
)


def _rows(emu: TerminalEmulator, index: int = 0) -> str:
    """Row *index* of the active grid with trailing blanks trimmed."""
    screen = emu.alt_grid if emu.in_alt else emu.grid
    return "".join(cell.char for cell in screen[index]).rstrip()


def _emu(cols: int = 20, rows: int = 4) -> TerminalEmulator:
    return TerminalEmulator(cols, rows)


# --- key translation --------------------------------------------------------


def test_printable_key_uses_the_typed_character() -> None:
    """A plain key press sends the character the keyboard produced."""
    assert key_to_terminal("a", "a") == "a"
    assert key_to_terminal("A", "A") == "A"
    assert key_to_terminal("space", " ") == " "


def test_single_character_key_without_a_character() -> None:
    """A bare single-character key is sent as-is."""
    assert key_to_terminal("x") == "x"


def test_named_keys_map_to_their_escape_sequences() -> None:
    """The named keys cover the ones a shell expects."""
    assert key_to_terminal("enter") == "\r"
    assert key_to_terminal("tab") == "\t"
    assert key_to_terminal("backspace") == "\x7f"
    assert key_to_terminal("escape") == "\x1b"
    assert key_to_terminal("delete") == "\x1b[3~"
    assert key_to_terminal("pageup") == "\x1b[5~"
    assert key_to_terminal("pagedown") == "\x1b[6~"
    assert key_to_terminal("up") == "\x1b[A"
    assert key_to_terminal("left") == "\x1b[D"
    assert key_to_terminal("home") == "\x1b[H"
    assert key_to_terminal("end") == "\x1b[F"
    assert key_to_terminal("f1") == "\x1bOP"
    assert key_to_terminal("f12") == "\x1b[24~"


def test_modified_arrows_and_tab() -> None:
    """ctrl/shift/alt arrows use the xterm modifier encodings."""
    assert key_to_terminal("ctrl+up") == "\x1b[1;5A"
    assert key_to_terminal("shift+right") == "\x1b[1;2C"
    assert key_to_terminal("shift+tab") == "\x1b[Z"
    assert key_to_terminal("alt+left") == "\x1b[1;3D"


def test_control_letters_and_symbols() -> None:
    """ctrl+letter is the classic control code; symbols have their own codes."""
    assert key_to_terminal("ctrl+a") == "\x01"
    assert key_to_terminal("ctrl+c") == "\x03"
    assert key_to_terminal("ctrl+shift+a") == "\x01"
    assert key_to_terminal("ctrl+space") == "\x00"
    assert key_to_terminal("ctrl+@") == "\x00"
    assert key_to_terminal("ctrl+[") == "\x1b"
    assert key_to_terminal("ctrl+\\") == "\x1c"
    assert key_to_terminal("ctrl+?") == "\x7f"


def test_alt_prefixed_keys() -> None:
    """alt+letter is ESC followed by the letter; alt+named reuses the table."""
    assert key_to_terminal("alt+x") == "\x1bx"
    assert key_to_terminal("alt+enter") == "\x1b\r"


def test_unmappable_keys_return_none() -> None:
    """Combinations the emulator cannot express are dropped."""
    assert key_to_terminal("ctrl+alt+a") is None
    assert key_to_terminal("super+a") is None
    assert key_to_terminal("ctrl+1") is None
    assert key_to_terminal("ctrl+") is None
    assert key_to_terminal("f13") is None  # not a named key, no modifier
    assert key_to_terminal("ctrl+shift+1") is None


def test_ctrl_shift_space_is_nul() -> None:
    """ctrl+shift+space shares the NUL encoding with ctrl+space."""
    assert key_to_terminal("ctrl+shift+space") == "\x00"


# --- colour tables ----------------------------------------------------------


def test_palette_color_uses_the_system_table_for_the_first_16() -> None:
    """Indices 0-15 come straight from the pre-resolved ANSI table."""
    assert palette_color(0) == ANSI_16_RGB[0]
    assert palette_color(15) == ANSI_16_RGB[15]


def test_palette_color_maps_the_6x6x6_cube() -> None:
    """The 216-colour cube uses the xterm component levels."""
    assert palette_color(16) == (0, 0, 0)
    assert palette_color(17) == (0, 0, 95)
    assert palette_color(21) == (0, 0, 255)
    assert palette_color(196) == (255, 0, 0)
    assert palette_color(231) == (255, 255, 255)


def test_palette_color_maps_the_grey_ramp_and_clamps() -> None:
    """232-255 are greys; out-of-range indices are clamped."""
    assert palette_color(232) == (8, 8, 8)
    assert palette_color(255) == (238, 238, 238)
    assert palette_color(-3) == palette_color(0)
    assert palette_color(999) == palette_color(255)


def test_cell_style_key_covers_every_attribute() -> None:
    """The style key is what the view uses to group equal attributes."""
    cell = Cell(char="x", fg=(1, 2, 3), bg=(4, 5, 6), bold=True, reverse=True)
    assert cell.style_key() == ((1, 2, 3), (4, 5, 6), True, False, False,
                                False, True)


# --- printing and cursor motion ---------------------------------------------


def test_plain_text_lands_on_the_first_row() -> None:
    """Characters are written left to right and advance the cursor."""
    emu = _emu()
    emu.feed(b"abc")
    assert _rows(emu) == "abc"
    assert emu.cursor == (0, 3)


def test_carriage_return_overwrites_and_line_feed_keeps_the_column() -> None:
    """CR returns to column 0; LF moves down without resetting the column."""
    emu = _emu()
    emu.feed(b"ab\ncd")
    assert _rows(emu, 0) == "ab"
    assert _rows(emu, 1) == "  cd"
    assert emu.cursor == (1, 4)

    emu.feed(b"\rmore")
    assert _rows(emu, 1) == "more"


def test_backspace_rewrites_the_previous_cell() -> None:
    """BS moves left, the next character overwrites the cell."""
    emu = _emu()
    emu.feed(b"ab\bX")
    assert _rows(emu) == "aX"


def test_tab_advances_to_the_next_eight_column_stop() -> None:
    """TAB stops every eight columns, clamped to the last one."""
    emu = _emu()
    emu.feed(b"a\tb")
    assert _rows(emu) == "a       b"
    assert emu.cursor == (0, 9)

    narrow = _emu(cols=5)
    narrow.feed(b"\t")
    assert narrow.cursor == (0, 4)


def test_bell_is_ignored_and_does_not_print() -> None:
    """BEL produces no cell content."""
    emu = _emu()
    emu.feed(b"a\x07b")
    assert _rows(emu) == "ab"


def test_autowrap_defers_to_the_next_character() -> None:
    """The last column only arms the wrap; the next character wraps."""
    emu = _emu(cols=4, rows=3)
    emu.feed(b"abcd")
    assert _rows(emu) == "abcd"
    assert emu.cursor == (0, 4)

    emu.feed(b"e")
    assert _rows(emu, 0) == "abcd"
    assert _rows(emu, 1) == "e"
    assert emu.cursor == (1, 1)


def test_wide_characters_take_two_columns() -> None:
    """A CJK character occupies its cell plus a continuation cell."""
    emu = _emu(cols=8, rows=2)
    emu.feed("你好".encode())
    screen = emu.grid[0]
    assert screen[0].char == "你"
    assert screen[1].char == ""
    assert screen[2].char == "好"
    assert emu.cursor == (0, 4)


def test_combining_marks_append_to_the_previous_cell() -> None:
    """A zero-width mark joins the character before it."""
    emu = _emu()
    emu.feed("e\u0301".encode())
    assert emu.grid[0][0].char == "e\u0301"
    assert emu.cursor == (0, 1)


def test_combining_mark_on_an_empty_grid_is_dropped() -> None:
    """Nothing to combine with at (0, 0)."""
    emu = _emu()
    emu.feed("\u0301".encode())
    assert _rows(emu) == ""
    assert emu.cursor == (0, 0)


def test_wide_character_at_the_last_column_arms_the_wrap() -> None:
    """A wide character cannot straddle the margin."""
    emu = _emu(cols=3, rows=2)
    emu.feed(b"ab")
    emu.feed("你".encode())
    assert emu.grid[0][2].char == ""
    emu.feed("好".encode())
    assert emu.grid[1][0].char == "好"


def test_wide_character_at_the_last_column_is_drawn_on_the_next_line() -> None:
    """A wide glyph at the margin is not lost: it lands whole one row down."""
    emu = _emu(cols=3, rows=3)
    emu.feed(b"ab")
    emu.feed("中".encode())
    assert emu.grid[0][2].char == ""  # the straddled margin cell is blanked
    assert emu.grid[1][0].char == "中"  # ... and the glyph appears below it
    assert emu.grid[1][1].char == ""  # on its own continuation column
    assert emu.cursor == (1, 2)

    # Same situation one row further down (no scrolling involved yet).
    emu.feed("文".encode())
    assert emu.grid[1][2].char == ""
    assert emu.grid[2][0].char == "文"
    assert emu.cursor == (2, 2)


def test_wide_character_at_the_bottom_margin_wraps_through_the_scrollback() -> None:
    """Wrapping a margin wide glyph off the last row scrolls like a LF."""
    emu = _emu(cols=3, rows=2)
    emu.feed(b"ab")
    emu.feed("中".encode())  # wraps to row 1
    emu.feed("文".encode())  # at the bottom margin: must scroll, not vanish
    assert emu.scrollback[-1][0].char == "a"
    assert emu.grid[0][0].char == "中"
    assert emu.grid[1][0].char == "文"
    assert emu.cursor == (1, 2)


def test_wide_character_mid_line_placement_is_unchanged() -> None:
    """Wide glyphs away from the margin still take their two cells."""
    emu = _emu(cols=6, rows=2)
    emu.feed("中文x".encode())
    assert [c.char for c in emu.grid[0][:5]] == ["中", "", "文", "", "x"]
    assert emu.cursor == (0, 5)


# --- CSI: cursor positioning -------------------------------------------------


def test_cursor_positioning_and_moves() -> None:
    """CUP/HVP, the four moves and the horizontal/vertical absolutes."""
    emu = _emu(cols=20, rows=6)
    emu.feed(b"\x1b[3;5H")
    assert emu.cursor == (2, 4)

    emu.feed(b"\x1b[2A")
    assert emu.cursor == (0, 4)
    emu.feed(b"\x1b[1B")
    assert emu.cursor == (1, 4)
    emu.feed(b"\x1b[2C")
    assert emu.cursor == (1, 6)
    emu.feed(b"\x1b[3D")
    assert emu.cursor == (1, 3)
    emu.feed(b"\x1b[9G")
    assert emu.cursor == (1, 8)
    emu.feed(b"\x1b[4d")
    assert emu.cursor == (3, 8)
    emu.feed(b"\x1b[H")
    assert emu.cursor == (0, 0)
    emu.feed(b"\x1b[3;4f")
    assert emu.cursor == (2, 3)


def test_next_and_previous_line_and_line_home() -> None:
    """CNL/CPL move vertically and reset the column; CHA is absolute."""
    emu = _emu(cols=20, rows=6)
    emu.feed(b"\x1b[5;7H\x1b[E")
    assert emu.cursor == (5, 0)
    emu.feed(b"\x1b[2F")
    assert emu.cursor == (3, 0)
    emu.feed(b"\x1b[6G")
    assert emu.cursor == (3, 5)


def test_cursor_motion_clamps_to_the_screen() -> None:
    """Moves never leave the grid, even with large counts."""
    emu = _emu(cols=5, rows=3)
    emu.feed(b"\x1b[99B")
    assert emu.cursor == (2, 0)
    emu.feed(b"\x1b[99C")
    assert emu.cursor == (2, 4)
    emu.feed(b"\x1b[99A")
    assert emu.cursor == (0, 4)
    emu.feed(b"\x1b[99D")
    assert emu.cursor == (0, 0)


def test_cursor_movement_cancels_the_pending_wrap() -> None:
    """A move after the last column writes on the same row."""
    emu = _emu(cols=4, rows=3)
    emu.feed(b"abcd\x1b[1D")
    emu.feed(b"X")
    assert _rows(emu, 0) == "abcX"
    assert _rows(emu, 1) == ""


# --- CSI: erasing and editing ------------------------------------------------


def test_erase_line_modes() -> None:
    """EL 0/1/2 clear to the end, to the start and the whole line."""
    emu = _emu()
    emu.feed(b"abcdef\x1b[3G\x1b[K")
    assert _rows(emu) == "ab"

    emu = _emu()
    emu.feed(b"abcdef\x1b[3G\x1b[1K")
    assert _rows(emu) == "   def"

    emu = _emu()
    emu.feed(b"abcdef\x1b[2K")
    assert _rows(emu) == ""


def test_erase_display_modes() -> None:
    """ED 0/1/2 clear from, to and including the cursor row."""
    emu = _emu(cols=6, rows=3)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[2;2H\x1b[J")
    assert _rows(emu, 1) == "b"
    assert _rows(emu, 2) == ""

    emu = _emu(cols=6, rows=3)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[2;2H\x1b[1J")
    assert _rows(emu, 0) == ""
    assert _rows(emu, 1) == "  b"  # ED 1 erases up to and including the cursor

    emu.feed(b"\x1b[2J")
    assert all(_rows(emu, r) == "" for r in range(3))


def test_erase_display_keeps_the_cursor() -> None:
    """Erasing the screen must not move the cursor (xterm behaviour)."""
    emu = _emu(cols=6, rows=3)
    emu.feed(b"\x1b[2;3H\x1b[2J")
    assert emu.cursor == (1, 2)


def test_insert_and_delete_characters() -> None:
    """ICH opens a gap, DCH removes characters, ECH blanks in place."""
    emu = _emu()
    emu.feed(b"abcdef\x1b[4G\x1b[2@")
    assert _rows(emu) == "abc  def"

    emu = _emu()
    emu.feed(b"abcdef\x1b[4G\x1b[2P")
    assert _rows(emu) == "abcf"

    emu = _emu()
    emu.feed(b"abcdef\x1b[4G\x1b[2X")
    assert _rows(emu) == "abc  f"


def test_character_edits_from_the_start_of_the_line() -> None:
    """ICH opens a gap, DCH closes it and ECH blanks in place."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"ab\x1b[1G\x1b[2@")
    assert _rows(emu) == "  ab"

    emu = _emu(cols=6, rows=2)
    emu.feed(b"ab\x1b[1G\x1b[1P")
    assert _rows(emu) == "b"

    emu = _emu(cols=6, rows=2)
    emu.feed(b"ab\x1b[1G\x1b[1X")
    assert _rows(emu) == " b"


def test_character_edits_clamp_their_count_to_the_line() -> None:
    """A count larger than the line simply empties it."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"ab\x1b[1G\x1b[99@")
    assert _rows(emu) == ""


def test_insert_and_delete_lines_with_counts() -> None:
    """IL/DL repeat their count and blank the freed rows."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\x1b[1;1H\x1b[2L")
    assert [_rows(emu, r) for r in range(4)] == ["", "", "aaa", "bbb"]

    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[1;1H\x1b[9M")
    assert [_rows(emu, r) for r in range(4)] == ["", "", "", ""]


def test_erase_display_mode_three_clears_screen_and_scrollback() -> None:
    """ED 3 is implemented as "clear everything, history included"."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"one\r\ntwo\r\nthree")
    assert emu.max_scroll() == 1

    emu.feed(b"\x1b[3J")
    assert emu.max_scroll() == 0
    assert [_rows(emu, r) for r in range(2)] == ["", ""]


def test_insert_and_delete_lines() -> None:
    """IL opens blank lines, DL removes them (inside the region)."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[1;2H\x1b[L")
    assert [_rows(emu, r) for r in range(4)] == ["", "aaa", "bbb", "ccc"]

    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[1;1H\x1b[M")
    assert [_rows(emu, r) for r in range(4)] == ["bbb", "ccc", "", ""]


def test_scroll_up_and_down_commands() -> None:
    """CSI S/T scroll the region without moving the cursor."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\r\nccc\x1b[3;4H\x1b[S")
    assert [_rows(emu, r) for r in range(4)] == ["bbb", "ccc", "", ""]
    assert emu.cursor == (2, 3)

    emu = _emu(cols=6, rows=4)
    emu.feed(b"aaa\r\nbbb\x1b[1;1H\x1b[T")
    assert [_rows(emu, r) for r in range(4)] == ["", "aaa", "bbb", ""]


# --- SGR --------------------------------------------------------------------


def test_sgr_attribute_toggles_and_reset() -> None:
    """Bold/dim/italic/underline/reverse go on and off individually."""
    emu = _emu()
    emu.feed(b"\x1b[1;2;3;4;7mX")
    cell = emu.grid[0][0]
    assert (cell.bold, cell.dim, cell.italic, cell.underline, cell.reverse) == (
        True, True, True, True, True,
    )

    emu.feed(b"\x1b[22mY")
    assert emu.grid[0][1].bold is False
    assert emu.grid[0][1].dim is False

    emu.feed(b"\x1b[23;24;27mZ")
    cell = emu.grid[0][2]
    assert cell.italic is False
    assert cell.underline is False
    assert cell.reverse is False

    emu.feed(b"\x1b[1m\x1b[0m ")
    assert emu.grid[0][3].bold is False


def test_sgr_16_colours_and_their_resets() -> None:
    """30-37/40-47 and the bright 90-97/100-107 map into the ANSI table."""
    emu = _emu()
    emu.feed(b"\x1b[31;44mA")
    cell = emu.grid[0][0]
    assert cell.fg == ANSI_16_RGB[1]
    assert cell.bg == ANSI_16_RGB[4]

    emu.feed(b"\x1b[93;104mB")
    cell = emu.grid[0][1]
    assert cell.fg == ANSI_16_RGB[11]
    assert cell.bg == ANSI_16_RGB[12]

    emu.feed(b"\x1b[39;49mC")
    cell = emu.grid[0][2]
    assert cell.fg is None
    assert cell.bg is None


def test_sgr_256_and_truecolor() -> None:
    """38/48 accept both the palette index and the direct RGB form."""
    emu = _emu()
    emu.feed(b"\x1b[38;5;196;48;5;21mA")
    cell = emu.grid[0][0]
    assert cell.fg == palette_color(196)
    assert cell.bg == palette_color(21)

    emu.feed(b"\x1b[38;2;10;20;30;48;2;300;-5;40mB")
    cell = emu.grid[0][1]
    assert cell.fg == (10, 20, 30)
    assert cell.bg == (255, 0, 40)


def test_sgr_incomplete_colour_spec_is_ignored() -> None:
    """A truncated 38/48 sequence changes nothing."""
    emu = _emu()
    emu.feed(b"\x1b[38;5mX")
    assert emu.grid[0][0].fg is None
    emu.feed(b"\x1b[38;2;1;2mY")
    assert emu.grid[0][1].fg is None


def test_sgr_empty_params_reset() -> None:
    """CSI m with no parameters is the same as SGR 0."""
    emu = _emu()
    emu.feed(b"\x1b[1m\x1b[mX")
    assert emu.grid[0][0].bold is False


# --- modes, response and OSC ------------------------------------------------


def test_autowrap_mode_can_be_switched_off() -> None:
    """DECAWM: with wrap off the last column is overwritten in place."""
    emu = _emu(cols=4, rows=2)
    emu.feed(b"\x1b[?7labcdef")
    assert _rows(emu, 0) == "abcf"
    assert _rows(emu, 1) == ""

    emu.feed(b"\x1b[?7h")
    emu.feed(b"g")
    assert _rows(emu, 1) == "g"


def test_cursor_visibility_and_bracketed_paste_modes() -> None:
    """DECTCEM and bracketed paste are plain flags."""
    emu = _emu()
    emu.feed(b"\x1b[?25l")
    assert emu.cursor_visible is False
    emu.feed(b"\x1b[?25h")
    assert emu.cursor_visible is True
    emu.feed(b"\x1b[?2004h")
    assert emu.bracketed_paste is True
    emu.feed(b"\x1b[?2004l")
    assert emu.bracketed_paste is False


def test_alternate_screen_switches_and_restores() -> None:
    """?1049 keeps the primary grid intact and swaps the active one."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"main\x1b[?1049h")
    assert emu.in_alt is True
    assert _rows(emu) == ""

    emu.feed(b"alt")
    assert _rows(emu) == "alt"

    emu.feed(b"\x1b[?1049l")
    assert emu.in_alt is False
    assert _rows(emu) == "main"
    assert emu.scrollback == []


def test_soft_reset_in_alternate_screen_returns_to_primary() -> None:
    """ESC c (RIS) leaves the alternate screen and clears the primary."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"main\x1b[?1049h\x1b[?25lalt")
    assert emu.in_alt is True
    assert _rows(emu) == "alt"

    emu.feed(b"\x1bc")
    assert emu.in_alt is False
    assert _rows(emu) == ""
    assert emu.cursor == (0, 0)
    assert emu.cursor_visible is True
    assert emu.scrollback == []


def test_device_status_and_identification_responses() -> None:
    """DSR 6/5 and DA report through the on_response callback."""
    seen: list[bytes] = []
    emu = TerminalEmulator(20, 4, on_response=seen.append)

    emu.feed(b"\x1b[2;3H\x1b[6n")
    assert seen[-1] == b"\x1b[2;3R"

    emu.feed(b"\x1b[5n")
    assert seen[-1] == b"\x1b[0n"

    emu.feed(b"\x1b[c")
    assert seen[-1] == b"\x1b[?1;2c"


def test_other_dsr_params_produce_no_response() -> None:
    """Only the documented DSR codes are answered."""
    seen: list[bytes] = []
    emu = TerminalEmulator(20, 4, on_response=seen.append)
    emu.feed(b"\x1b[7n")
    assert seen == []


def test_osc_sets_the_window_title() -> None:
    """OSC 0/2 with a BEL or ST terminator sets ``title``."""
    emu = _emu()
    emu.feed(b"\x1b]0;My Shell\x07")
    assert emu.title == "My Shell"

    emu.feed(b"\x1b]2;Second\x1b\\")
    assert emu.title == "Second"


def test_osc_without_a_terminator_waits_for_it() -> None:
    """The payload only applies once the terminator arrives."""
    emu = _emu()
    emu.feed(b"\x1b]0;Partial")
    assert emu.title == ""
    emu.feed(b"\x07")
    assert emu.title == "Partial"


def test_unknown_escape_sequences_do_not_disturb_the_grid() -> None:
    """Unsupported finals and intermediates are consumed and ignored."""
    emu = _emu()
    emu.feed(b"ok\x1b[99;99;99z\x1b(Bmore")
    assert _rows(emu) == "okmore"


# --- scrolling, scrollback and the view API ---------------------------------


def test_line_feed_scrolls_and_records_scrollback() -> None:
    """Scrolling off the top of the primary screen becomes history."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"one\r\ntwo\r\nthree")
    assert emu.max_scroll() == 1
    assert "".join(c.char for c in emu.scrollback[-1]).rstrip() == "one"
    assert [_rows(emu, r) for r in range(2)] == ["two", "three"]


def test_view_lines_walks_back_into_the_scrollback() -> None:
    """``view_lines(0)`` is the live screen; positive values look back."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"one\r\ntwo\r\nthree")
    live = ["".join(c.char for c in row).rstrip()
            for row in emu.view_lines(0)]
    assert live == ["two", "three"]

    back = ["".join(c.char for c in row).rstrip()
            for row in emu.view_lines(1)]
    assert back == ["one", "two"]

    # the scroll offset is clamped to the available history
    assert emu.view_lines(99) == emu.view_lines(emu.max_scroll())


def test_view_lines_pages_through_a_longer_history() -> None:
    """The view slices the scrollback plus the live rows."""
    emu = _emu(cols=6, rows=2)
    for line in (b"l1", b"l2", b"l3", b"l4", b"l5"):
        emu.feed(line + b"\r\n")
    emu.feed(b"l6")

    def text(scroll: int) -> list[str]:
        return ["".join(c.char for c in row).rstrip()
                for row in emu.view_lines(scroll)]

    assert emu.max_scroll() >= 4
    assert text(0) == ["l5", "l6"]
    assert text(2) == ["l3", "l4"]
    assert text(4) == ["l1", "l2"]


def test_alternate_screen_has_no_scrollback() -> None:
    """History belongs to the primary screen only."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"\x1b[?1049h")
    emu.feed(b"one\r\ntwo\r\nthree")
    assert emu.max_scroll() == 0
    assert emu.view_lines(0) == emu.alt_grid


def test_scroll_region_confines_the_scrolling() -> None:
    """DECSTBM keeps lines outside the region fixed and homes the cursor."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"top\r\nmid1\r\nmid2\r\nbot")
    emu.feed(b"\x1b[2;3r")
    assert (emu.scroll_top, emu.scroll_bottom) == (1, 2)
    assert emu.cursor == (0, 0)

    # a line feed at the bottom of the region scrolls the region only
    emu.feed(b"\x1b[3;1H\n")
    assert [_rows(emu, r) for r in range(4)] == ["top", "mid2", "", "bot"]


def test_invalid_scroll_region_is_ignored() -> None:
    """A region that is not inside the screen keeps the previous one."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"\x1b[1;9r")
    assert (emu.scroll_top, emu.scroll_bottom) == (0, 3)


def test_reverse_index_moves_up_inside_a_region() -> None:
    """Above the top of the region RI just steps the cursor up."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"\x1b[2;4r\x1b[4;1H\x1bM")
    assert emu.cursor == (2, 0)


def test_combining_mark_at_the_start_of_a_row_joins_the_row_above() -> None:
    """A mark typed at column 0 appends to the last cell of the row above."""
    emu = _emu(cols=2, rows=2)
    emu.feed(b"ab")
    emu.feed(b"\r\n")
    emu.feed("\u0301".encode())
    assert emu.grid[0][1].char == "b\u0301"
    assert emu.cursor == (1, 0)


def test_tab_at_the_last_column_does_not_move() -> None:
    """TAB is a no-op once the cursor is already at the right margin."""
    emu = _emu(cols=5, rows=2)
    emu.feed(b"\x1b[1;5H\t")
    assert emu.cursor == (0, 4)


def test_response_is_dropped_without_a_callback() -> None:
    """DSR on an emulator without a callback simply does nothing."""
    emu = _emu()
    emu.feed(b"\x1b[6n\x1b[5n\x1b[c")
    assert emu.cursor == (0, 0)


def test_reverse_index_scrolls_down_at_the_top() -> None:
    """RI at the top of the region pushes the lines down."""
    emu = _emu(cols=6, rows=3)
    emu.feed(b"aaa\r\nbbb")
    emu.feed(b"\x1b[H\x1bM")
    assert [_rows(emu, r) for r in range(3)] == ["", "aaa", "bbb"]


def test_save_and_restore_cursor() -> None:
    """DECSC/DECRC keep row and column across the screen."""
    emu = _emu(cols=8, rows=4)
    emu.feed(b"\x1b[3;5H\x1b[s\x1b[1;1H\x1b[u")
    assert emu.cursor == (2, 4)


def test_save_and_restore_cursor_clamps_after_a_shrink() -> None:
    """Restoring a saved position clamps into the current screen."""
    emu = _emu(cols=8, rows=4)
    emu.feed(b"\x1b[4;8H\x1b[s")
    emu.resize(4, 2)
    emu.feed(b"\x1b[u")
    assert emu.cursor == (1, 3)


# --- resize -----------------------------------------------------------------


def test_resize_keeps_the_bottom_of_the_screen() -> None:
    """Shrinking the primary screen moves the dropped rows into history."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"one\r\ntwo\r\nthree\r\nfour")
    emu.resize(6, 2)
    assert [_rows(emu, r) for r in range(2)] == ["three", "four"]
    assert emu.max_scroll() == 2


def test_resize_grows_with_blank_rows_and_clamps_the_cursor() -> None:
    """Growing pads with blanks; the cursor stays inside the screen."""
    emu = _emu(cols=6, rows=2)
    emu.feed(b"ab\x1b[2;6H")
    emu.resize(4, 4)
    assert (emu.cols, emu.rows) == (4, 4)
    assert [_rows(emu, r) for r in range(4)] == ["", "", "ab", ""]
    assert emu.cursor == (1, 3)


def test_resize_of_the_alternate_screen_drops_history() -> None:
    """The alternate screen is replaced wholesale, without scrollback."""
    emu = _emu(cols=6, rows=4)
    emu.feed(b"\x1b[?1049h\nalt")
    emu.resize(4, 2)
    assert emu.in_alt is True
    assert emu.alt_grid == [[Cell() for _ in range(4)] for _ in range(2)]
    assert emu.scrollback == []


def test_resize_rejects_degenerate_sizes() -> None:
    """Sizes below one are raised to the minimum."""
    emu = _emu(cols=6, rows=4)
    emu.resize(0, -3)
    assert (emu.cols, emu.rows) == (1, 1)
    assert emu.cursor == (0, 0)


# --- parameter parsing ------------------------------------------------------


def test_parameter_parsing_tolerates_junk_and_colons() -> None:
    """Empty and non-numeric tokens fall back to the default count."""
    emu = _emu(cols=10, rows=6)
    emu.feed(b"\x1b[3:8H")  # the sub-parameter is dropped
    assert emu.cursor == (2, 0)

    emu.feed(b"\x1b[;5H")  # an empty row token falls back to the default
    assert emu.cursor == (0, 4)

    emu.feed(b"\x1b[=A")  # "=" is not a number: treated as the default
    assert emu.cursor == (0, 4)

    emu.feed(b"\x1b[99;A")  # a trailing empty token keeps the first count
    assert emu.cursor == (0, 4)


def test_invalid_utf8_bytes_become_replacement_characters() -> None:
    """The decoder never raises on a garbled byte stream."""
    emu = _emu()
    emu.feed(b"a\xffb")
    assert emu.grid[0][0].char == "a"
    assert emu.grid[0][1].char == "\ufffd"
    assert emu.grid[0][2].char == "b"