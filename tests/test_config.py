"""Tests for the yaterc configuration system (yate.config)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from yate import config as cfg
from yate import yaterc as yrc
from yate.editor_view import theme as themes


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _load(
    body: str,
    tmp_path: Path,
    *,
    register_theme: yrc.ThemeRegistrar | None = None,
    load_theme_paths: yrc.ThemeDirLoader | None = None,
) -> cfg.YateConfig:
    rc = _write(tmp_path / "yaterc", body)
    return yrc.load_config(
        [rc],
        register_theme=register_theme,
        load_theme_paths=load_theme_paths,
    )


# --- defaults ---------------------------------------------------------------


def test_builtin_defaults() -> None:
    config = cfg.YateConfig()
    assert config.keymap == "vsc"
    assert config.theme == "mocha"
    assert config.tab_width == 4
    assert config.use_spaces
    assert config.sources == []
    assert config.errors == []


def test_load_no_files_returns_defaults() -> None:
    config = yrc.load_config([])
    assert config.keymap == "vsc"
    assert config.tab_width == 4
    assert config.sources == []


# --- loading ----------------------------------------------------------------


def test_loads_all_options(tmp_path: Path) -> None:
    rc = _write(
        tmp_path / "yaterc",
        'keymap = "vim"\n'
        'theme = "latte"\n'
        "tab_width = 2\n"
        "use_spaces = False\n",
    )
    config = yrc.load_config([rc])
    assert config.keymap == "vim"
    assert config.theme == "latte"
    assert config.tab_width == 2
    assert not config.use_spaces
    assert config.sources == [rc]
    assert config.errors == []


def test_partial_options_keep_other_defaults(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", "tab_width = 8\n")
    config = yrc.load_config([rc])
    assert config.tab_width == 8
    assert config.keymap == "vsc"
    assert config.use_spaces


def test_unknown_options_are_ignored(tmp_path: Path) -> None:
    rc = _write(
        tmp_path / "yaterc",
        "some_future_option = 99\n"
        "def helper():\n    return 1\n",
    )
    config = yrc.load_config([rc])
    assert config.errors == []
    assert config.tab_width == 4


def test_project_rc_overrides_user_rc(tmp_path: Path) -> None:
    user = _write(tmp_path / "user_yaterc", 'keymap = "vsc"\ntab_width = 2\n')
    project = _write(tmp_path / "project_yaterc", "tab_width = 8\n")
    config = yrc.load_config([user, project])
    # later file wins; earlier values survive where not overridden
    assert config.tab_width == 8
    assert config.keymap == "vsc"
    assert config.sources == [user, project]


def test_missing_file_is_an_error() -> None:
    config = yrc.load_config([Path("/nonexistent/yaterc")])
    assert len(config.errors) == 1
    assert config.sources == []
    assert config.tab_width == 4


def test_runtime_error_in_rc_is_caught(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad", 'raise RuntimeError("boom")\n')
    good = _write(tmp_path / "good", "tab_width = 3\n")
    config = yrc.load_config([bad, good])
    assert any("boom" in e for e in config.errors)
    # later files still load
    assert config.tab_width == 3
    assert config.sources == [good]


def test_syntax_error_in_rc_is_caught(tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad", "keymap = \n")
    config = yrc.load_config([bad])
    assert len(config.errors) == 1
    assert config.keymap == "vsc"


# --- validation -------------------------------------------------------------


def test_invalid_keymap(tmp_path: Path) -> None:
    config = _load('keymap = "emacs"\n', tmp_path)
    assert config.keymap == "vsc"
    assert any("keymap" in e for e in config.errors)


def test_key_protocol_defaults_and_valid_values(tmp_path: Path) -> None:
    assert cfg.YateConfig().key_protocol == "auto"
    assert _load('key_protocol = "legacy"\n', tmp_path).key_protocol == "legacy"


def test_invalid_key_protocol(tmp_path: Path) -> None:
    config = _load('key_protocol = "vt100"\n', tmp_path)
    assert config.key_protocol == "auto"
    assert any("key_protocol" in e for e in config.errors)


def test_invalid_tab_width_values(tmp_path: Path) -> None:
    for value in ('"wide"', "0", "17", "True", "3.5"):
        config = _load(f"tab_width = {value}\n", tmp_path)
        assert config.tab_width == 4, value
        assert config.errors, value


def test_valid_tab_width_bounds(tmp_path: Path) -> None:
    assert _load("tab_width = 1\n", tmp_path).tab_width == 1
    assert _load("tab_width = 16\n", tmp_path).tab_width == 16


def test_invalid_use_spaces(tmp_path: Path) -> None:
    config = _load("use_spaces = 1\n", tmp_path)
    assert config.use_spaces
    assert any("use_spaces" in e for e in config.errors)


def test_invalid_theme(tmp_path: Path) -> None:
    config = _load("theme = 123\n", tmp_path)
    assert any("theme" in e for e in config.errors)


def test_shell_option(tmp_path: Path) -> None:
    config = _load('shell = "pwsh -NoLogo"\n', tmp_path)
    assert config.shell == "pwsh -NoLogo"
    assert config.errors == []


def test_shell_must_be_nonempty_string(tmp_path: Path) -> None:
    config = _load('shell = "  "\n', tmp_path)
    assert config.shell == ""
    assert any("shell" in e for e in config.errors)
    config2 = _load("shell = 7\n", tmp_path)
    assert config2.shell == ""
    assert any("shell" in e for e in config2.errors)


def test_terminal_height_bounds(tmp_path: Path) -> None:
    assert _load("terminal_height = 3\n", tmp_path).terminal_height == 3
    assert _load("terminal_height = 40\n", tmp_path).terminal_height == 40
    for value in ("2", "41", "12.5", "True", '"tall"'):
        config = _load(f"terminal_height = {value}\n", tmp_path)
        assert config.terminal_height == 12, value
        assert config.errors, value


def test_show_hidden_accepts_booleans_only(tmp_path: Path) -> None:
    """show_hidden toggles dotfiles and rejects every non-boolean value."""
    assert _load("show_hidden = True\n", tmp_path).show_hidden is True
    assert _load("show_hidden = False\n", tmp_path).show_hidden is False

    config = _load('show_hidden = "yes"\n', tmp_path)
    assert config.show_hidden is False
    assert any("show_hidden" in error for error in config.errors)


# --- support_mouse option ---------------------------------------------------


def test_support_mouse_defaults_true() -> None:
    """Mouse support is on by default (issue IKJRFK opt-out switch)."""
    assert cfg.YateConfig().support_mouse is True


def test_support_mouse_rc_value_applied(tmp_path: Path) -> None:
    """A boolean rc value flips the master switch without errors."""
    config = _load("support_mouse = False\n", tmp_path)
    assert config.support_mouse is False
    assert config.errors == []


def test_support_mouse_rejects_non_bool_keeps_default(tmp_path: Path) -> None:
    """A non-boolean value reports an error and keeps the default."""
    config = _load('support_mouse = "yes"\n', tmp_path)
    assert config.support_mouse is True
    assert any(
        "support_mouse must be True or False" in e for e in config.errors
    )


# --- trace options -----------------------------------------------------------


def test_trace_defaults_to_off() -> None:
    config = cfg.YateConfig()
    assert config.yate_trace is False
    assert config.yate_trace_level == "DEBUG"


def test_trace_option(tmp_path: Path) -> None:
    config = _load("yate_trace = True\n", tmp_path)
    assert config.yate_trace is True
    assert config.errors == []


def test_trace_option_must_be_bool(tmp_path: Path) -> None:
    # Like every other option, an explicit None means "not set" (no error).
    for value in ("1", "0", '"yes"'):
        config = _load(f"yate_trace = {value}\n", tmp_path)
        assert config.yate_trace is False, value
        assert any("yate_trace" in e for e in config.errors), value


def test_trace_level_normalized_to_upper(tmp_path: Path) -> None:
    for value, expected in (
        ('"debug"', "DEBUG"), ('"Info"', "INFO"), ('"  warning  "', "WARNING"),
        ('"ERROR"', "ERROR"), ('"critical"', "CRITICAL"),
    ):
        config = _load(f"yate_trace_level = {value}\n", tmp_path)
        assert config.yate_trace_level == expected, value
        assert config.errors == [], value


def test_invalid_trace_level(tmp_path: Path) -> None:
    for value in ('"VERBOSE"', '"  "', "10"):
        config = _load(f"yate_trace_level = {value}\n", tmp_path)
        assert config.yate_trace_level == "DEBUG", value
        assert any("yate_trace_level" in e for e in config.errors), value


# --- language_servers option ------------------------------------------------


def test_language_servers_minimal_valid_entry(tmp_path: Path) -> None:
    config = _load(
        'language_servers = [{"name": "go", "command": "gopls",'
        ' "filetypes": ["go"]}]\n',
        tmp_path,
    )
    assert config.errors == []
    assert len(config.language_servers) == 1
    spec = config.language_servers[0]
    assert spec.name == "go"
    assert spec.command == "gopls"
    assert spec.filetypes == ["go"]
    assert spec.args == []
    assert spec.language_ids == {}
    assert spec.env is None
    assert spec.root_markers is None


def test_language_servers_full_valid_entry(tmp_path: Path) -> None:
    body = (
        "language_servers = [{\n"
        '    "name": "ts",\n'
        '    "command": "typescript-language-server",\n'
        '    "args": ["--stdio"],\n'
        '    "filetypes": ["ts", "tsx"],\n'
        '    "language_ids": {"ts": "typescript", "tsx": "typescriptreact"},\n'
        '    "root_markers": ["package.json", ".git"],\n'
        '    "env": {"NODE_ENV": "development"},\n'
        '    "initialization_options": {"x": 1},\n'
        '    "settings": {"y": 2},\n'
        "}]\n"
    )
    config = _load(body, tmp_path)
    assert config.errors == []
    spec = config.language_servers[0]
    assert spec.args == ["--stdio"]
    assert spec.filetypes == ["ts", "tsx"]
    assert spec.language_ids == {"ts": "typescript", "tsx": "typescriptreact"}
    assert spec.root_markers == ["package.json", ".git"]
    assert spec.env == {"NODE_ENV": "development"}
    assert spec.initialization_options == {"x": 1}
    assert spec.settings == {"y": 2}


def test_leading_dot_in_filetypes_stripped(tmp_path: Path) -> None:
    config = _load(
        'language_servers = [{"name": "r", "command": "rls",'
        ' "filetypes": [".rs", ".rsx"]}]\n',
        tmp_path,
    )
    assert config.errors == []
    assert config.language_servers[0].filetypes == ["rs", "rsx"]


def test_multiple_entries_and_default_empty(tmp_path: Path) -> None:
    assert cfg.YateConfig().language_servers == []
    config = _load(
        "language_servers = [\n"
        '    {"name": "a", "command": "a-ls", "filetypes": ["a"]},\n'
        '    {"name": "b", "command": "b-ls", "filetypes": ["b"]},\n'
        "]\n",
        tmp_path,
    )
    assert config.errors == []
    assert [s.name for s in config.language_servers] == ["a", "b"]


def test_not_a_list_is_rejected(tmp_path: Path) -> None:
    config = _load(
        'language_servers = {"name": "x", "command": "x",'
        ' "filetypes": ["x"]}\n',
        tmp_path,
    )
    assert config.language_servers == []
    assert any("language_servers" in e for e in config.errors)


def test_entry_must_be_a_mapping(tmp_path: Path) -> None:
    config = _load('language_servers = ["oops", 42]\n', tmp_path)
    assert config.language_servers == []
    assert len(config.errors) == 2
    assert all("entry must be a mapping" in e for e in config.errors)


def test_required_fields(tmp_path: Path) -> None:
    cases = {
        '{"command": "x", "filetypes": ["x"]}': "name",
        '{"name": "x", "filetypes": ["x"]}': "command",
        '{"name": "x", "command": "x"}': "filetypes",
        '{"name": "x", "command": "x", "filetypes": []}': "filetypes",
        '{"name": "  ", "command": "x", "filetypes": ["x"]}': "name",
        '{"name": "x", "command": "  ", "filetypes": ["x"]}': "command",
    }
    for body, field_name in cases.items():
        config = _load(f"language_servers = [{body}]\n", tmp_path)
        assert config.language_servers == [], body
        assert any(field_name in e for e in config.errors), (body, config.errors)


def test_bad_nested_field_types(tmp_path: Path) -> None:
    cases = [
        '{"name": "x", "command": "x", "filetypes": ["ok"], "args": "--x"}',
        '{"name": "x", "command": "x", "filetypes": ["ok"], "args": [1]}',
        '{"name": "x", "command": "x", "filetypes": ["ok"],'
        ' "root_markers": [".git", 7]}',
        '{"name": "x", "command": "x", "filetypes": ["ok"],'
        ' "language_ids": {"x": 1}}',
        '{"name": "x", "command": "x", "filetypes": ["ok"],'
        ' "env": {"X": 1}}',
        '{"name": "x", "command": "x", "filetypes": [3]}',
    ]
    for body in cases:
        config = _load(f"language_servers = [{body}]\n", tmp_path)
        assert config.language_servers == [], body
        assert config.errors, body


def test_bad_entry_skipped_sibling_still_loads(tmp_path: Path) -> None:
    config = _load(
        "language_servers = [\n"
        '    {"name": "bad", "filetypes": ["bad"]},\n'
        '    {"name": "good", "command": "good-ls", "filetypes": ["good"]},\n'
        "]\n",
        tmp_path,
    )
    assert [s.name for s in config.language_servers] == ["good"]
    assert len(config.errors) == 1
    assert "command" in config.errors[0]


def test_later_rc_replaces_entire_list(tmp_path: Path) -> None:
    user_rc = _write(
        tmp_path / "user",
        'language_servers = [{"name": "a", "command": "a",'
        ' "filetypes": ["a"]}]\n',
    )
    project_rc = _write(
        tmp_path / "project",
        'language_servers = [{"name": "b", "command": "b",'
        ' "filetypes": ["b"]}]\n',
    )
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    assert [s.name for s in config.language_servers] == ["b"]


def test_tuples_accepted_for_sequence_fields(tmp_path: Path) -> None:
    body = (
        "language_servers = [{\n"
        '    "name": "t", "command": "t-ls",\n'
        '    "filetypes": ("t",),\n'
        '    "args": ("--stdio",),\n'
        '    "root_markers": (".git", "t.proj"),\n'
        "}]\n"
    )
    config = _load(body, tmp_path)
    assert config.errors == []
    spec = config.language_servers[0]
    assert spec.filetypes == ["t"]
    assert spec.args == ["--stdio"]
    assert spec.root_markers == [".git", "t.proj"]


def test_whitespace_only_items_rejected(tmp_path: Path) -> None:
    cases = [
        '"filetypes": [" "]',
        '"filetypes": ["ok", ""]',
        '"args": ["  "]',
        '"root_markers": [""]',
    ]
    for field_body in cases:
        config = _load(
            "language_servers = [{"
            '"name": "x", "command": "x", '
            f'{field_body}}}]\n',
            tmp_path,
        )
        assert config.language_servers == [], field_body
        assert config.errors, field_body


def test_non_mapping_map_fields_rejected(tmp_path: Path) -> None:
    cases = [
        '"language_ids": ["rs=rust"]',
        '"language_ids": "rs=rust"',
        '"env": ["X=1"]',
        '"env": "X=1"',
    ]
    for field_body in cases:
        config = _load(
            "language_servers = [{"
            '"name": "x", "command": "x", "filetypes": ["x"], '
            f'{field_body}}}]\n',
            tmp_path,
        )
        assert config.language_servers == [], field_body
        assert any("mapping" in e for e in config.errors), (field_body, config.errors)


def test_non_string_dict_key_rejected(tmp_path: Path) -> None:
    body = (
        "language_servers = [{'name': 'x', 'command': 'x',"
        " 'filetypes': ['x'], 'language_ids': {1: 'x'}}]\n"
    )
    config = _load(body, tmp_path)
    assert config.language_servers == []
    assert any("keys and values" in e for e in config.errors)


def test_dot_only_filetypes_rejected(tmp_path: Path) -> None:
    for value in ('["."]', '[".."]', '["ok", "."]'):
        config = _load(
            'language_servers = [{"name": "x", "command": "x",'
            f' "filetypes": {value}}}]\n',
            tmp_path,
        )
        assert config.language_servers == [], value
        assert any("name an extension" in e for e in config.errors), (value, config.errors)


def test_name_and_command_are_stripped(tmp_path: Path) -> None:
    config = _load(
        'language_servers = [{"name": "  go  ", "command": " gopls\\t",'
        ' "filetypes": [" go ", ".go"]}]\n',
        tmp_path,
    )
    assert config.errors == []
    spec = config.language_servers[0]
    assert spec.name == "go"
    assert spec.command == "gopls"
    # list items other than the leading dot are kept verbatim
    assert spec.filetypes == [" go ", "go"]


def test_extra_unknown_keys_ignored(tmp_path: Path) -> None:
    config = _load(
        'language_servers = [{"name": "x", "command": "x",'
        ' "filetypes": ["x"], "future_option": 42, "typo": True}]\n',
        tmp_path,
    )
    assert config.errors == []
    assert len(config.language_servers) == 1


# --- project config discovery -----------------------------------------------


def test_find_project_config_walks_up(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", "tab_width = 2\n")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    found = yrc.find_project_config(deep)
    # the walk resolves, so compare against the canonical path (on
    # Windows TEMP may be an 8.3 short name such as RUNNER~1)
    assert found == rc.resolve()


def test_find_project_config_none(tmp_path: Path) -> None:
    assert yrc.find_project_config(tmp_path) is None


def test_find_project_config_from_file_path(tmp_path: Path) -> None:
    _write(tmp_path / "yaterc", 'keymap = "vim"\n')
    file_in_subdir = tmp_path / "src" / "main.py"
    (tmp_path / "src").mkdir()
    file_in_subdir.write_text("", encoding="utf-8")
    found = yrc.find_project_config(file_in_subdir)
    assert found == (tmp_path / "yaterc").resolve()


def test_default_rc_paths_user_then_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_rc = tmp_path / "user_yaterc"
    _write(user_rc, "")
    project_rc = _write(tmp_path / "yaterc", "")
    monkeypatch.setattr(yrc, "user_config_path", lambda: user_rc)
    paths = yrc.default_rc_paths(tmp_path)
    # returned paths are resolved (canonical) -- see Windows 8.3 note
    assert paths == [user_rc.resolve(), project_rc.resolve()]


def test_default_rc_paths_dedupes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _write(tmp_path / "yaterc", "")
    monkeypatch.setattr(yrc, "user_config_path", lambda: rc)
    paths = yrc.default_rc_paths(tmp_path)
    assert paths == [rc.resolve()]


def test_user_config_path_layout(isolated_home: Path) -> None:
    assert yrc.user_config_path() == (
        isolated_home / ".yate" / yrc.RC_FILENAME
    )


def test_default_rc_paths_without_any_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # user rc missing and no project rc anywhere up the tree -> empty
    missing_user = tmp_path / "no-yaterc-here"
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    monkeypatch.setattr(yrc, "user_config_path", lambda: missing_user)
    paths = yrc.default_rc_paths(deep)
    assert paths == []


# --- extensions option ------------------------------------------------------


def test_relative_paths_resolve_against_rc_dir(tmp_path: Path) -> None:
    ext_file = _write(tmp_path / "tool.py", "def setup(api):\n    pass\n")
    ext_dir = tmp_path / "exts"
    ext_dir.mkdir()
    rc = _write(tmp_path / "yaterc", 'extensions = ["tool.py", "exts"]\n')
    config = yrc.load_config([rc])
    assert config.errors == []
    assert config.extension_paths == [ext_file.resolve(), ext_dir.resolve()]


def test_extension_accepts_single_string(tmp_path: Path) -> None:
    ext_file = _write(tmp_path / "tool.py", "def setup(api):\n    pass\n")
    rc = _write(tmp_path / "yaterc", 'extensions = "tool.py"\n')
    config = yrc.load_config([rc])
    assert config.extension_paths == [ext_file.resolve()]


def test_tilde_expanded(tmp_path: Path, isolated_home: Path) -> None:
    ext_file = _write(isolated_home / "tool.py", "def setup(api):\n    pass\n")
    rc = _write(tmp_path / "yaterc", 'extensions = "~/tool.py"\n')
    # expanduser() reads HOME/USERPROFILE, redirected by the isolated home
    config = yrc.load_config([rc])
    assert config.errors == []
    assert config.extension_paths == [ext_file.resolve()]


def test_nonexistent_path_reported(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", 'extensions = ["missing.py"]\n')
    config = yrc.load_config([rc])
    assert config.extension_paths == []
    assert any("does not exist" in err for err in config.errors)


def test_bad_types_reported(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", "extensions = 42\n")
    config = yrc.load_config([rc])
    assert config.extension_paths == []
    assert any("extensions" in err for err in config.errors)

    rc2 = _write(tmp_path / "yaterc2", 'extensions = ["ok_missing", 7]\n')
    config2 = yrc.load_config([rc2])
    assert any("non-empty strings" in err for err in config2.errors)


def test_accumulates_across_rc_files_and_dedupes(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.py", "def setup(api):\n    pass\n")
    b = _write(tmp_path / "b.py", "def setup(api):\n    pass\n")
    user_rc = _write(tmp_path / "user_rc", 'extensions = ["./a.py"]\n')
    project_rc = _write(tmp_path / "project_rc", 'extensions = ["a.py", "b.py"]\n')
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    # a.py appears in both rc files but is loaded only once
    assert config.extension_paths == [a.resolve(), b.resolve()]


# --- disabled_extensions option --------------------------------------------


def test_disabled_extensions_default_empty() -> None:
    assert cfg.YateConfig().disabled_extensions == []


def test_disabled_extensions_accumulate_and_dedupe(tmp_path: Path) -> None:
    user_rc = _write(tmp_path / "user", 'disabled_extensions = ["python_lsp"]\n')
    project_rc = _write(
        tmp_path / "project",
        'disabled_extensions = ("python_lsp", "csharp_highlight")\n',
    )
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    assert config.disabled_extensions == ["python_lsp", "csharp_highlight"]


def test_disabled_extensions_single_string_and_whitespace_trimmed(
    tmp_path: Path,
) -> None:
    config = _load('disabled_extensions = " python_lsp "\n', tmp_path)
    assert config.disabled_extensions == ["python_lsp"]


def test_disabled_extensions_bad_type_reported(tmp_path: Path) -> None:
    config = _load("disabled_extensions = 42\n", tmp_path)
    assert config.disabled_extensions == []
    assert any("disabled_extensions" in e for e in config.errors), config.errors


def test_disabled_extensions_blank_entries_reported_but_siblings_kept(
    tmp_path: Path,
) -> None:
    config = _load('disabled_extensions = ["", "python_lsp", "   "]\n', tmp_path)
    assert config.disabled_extensions == ["python_lsp"]
    assert len(config.errors) == 2


# --- theme_dirs option ------------------------------------------------------


def _theme_file(directory: Path, name: str, theme_name: str) -> Path:
    body = (
        "from dataclasses import replace\n"
        "from yate.editor_view.theme import THEMES\n"
        f"register_theme(replace(THEMES['mocha'], name={theme_name!r}))\n"
    )
    return _write(directory / name, body)


@pytest.fixture
def registered_themes() -> Iterator[list[str]]:
    """Drop themes registered during the test; restore the default theme."""
    names: list[str] = []
    yield names
    for name in names:
        themes.THEMES.pop(name, None)
    themes.set_theme("mocha")


def test_theme_dir_single_string_loads_theme(
    tmp_path: Path, registered_themes: list[str]
) -> None:
    tdir = tmp_path / "themes"
    tdir.mkdir()
    _theme_file(tdir, "mytheme.py", "yate_test_dir_theme")
    rc = _write(
        tmp_path / "yaterc",
        'theme_dirs = "themes"\n'
        'theme = "yate_test_dir_theme"\n',
    )
    registered_themes.append("yate_test_dir_theme")
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.errors == []
    assert config.theme_dirs == [tdir.resolve()]
    # the registry already contains the externally defined theme
    assert "yate_test_dir_theme" in themes.available()
    activated = themes.set_theme("yate_test_dir_theme")
    assert activated.bg == themes.THEMES["mocha"].bg


def test_theme_dir_list_relative_and_single_file(
    tmp_path: Path, registered_themes: list[str]
) -> None:
    tdir = tmp_path / "more"
    tdir.mkdir()
    _theme_file(tdir, "a.py", "yate_test_dir_a")
    single = _theme_file(tmp_path, "solo.py", "yate_test_dir_solo")
    rc = _write(tmp_path / "yaterc", 'theme_dirs = ["more", "solo.py"]\n')
    registered_themes.extend(["yate_test_dir_a", "yate_test_dir_solo"])
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.errors == []
    assert config.theme_dirs == [tdir.resolve(), single.resolve()]
    assert "yate_test_dir_a" in themes.available()
    assert "yate_test_dir_solo" in themes.available()


def test_underscore_files_skipped(tmp_path: Path) -> None:
    tdir = tmp_path / "themes"
    tdir.mkdir()
    _theme_file(tdir, "_hidden.py", "yate_test_hidden")
    rc = _write(tmp_path / "yaterc", 'theme_dirs = "themes"\n')
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.errors == []
    assert "yate_test_hidden" not in themes.available()


def test_broken_theme_file_is_reported_others_still_load(
    tmp_path: Path, registered_themes: list[str]
) -> None:
    tdir = tmp_path / "themes"
    tdir.mkdir()
    _write(tdir / "bad.py", 'raise RuntimeError("theme boom")\n')
    _theme_file(tdir, "good.py", "yate_test_good")
    rc = _write(tmp_path / "yaterc", 'theme_dirs = "themes"\n')
    registered_themes.append("yate_test_good")
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert any("theme boom" in e for e in config.errors), config.errors
    assert "yate_test_good" in themes.available()


def test_nonexistent_theme_dir_reported(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", 'theme_dirs = ["missing"]\n')
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.theme_dirs == []
    assert any(
        "theme_dirs" in e and "does not exist" in e for e in config.errors
    )


def test_absolute_nonexistent_theme_dir_reported(tmp_path: Path) -> None:
    missing = (tmp_path / "nope" / "themes").as_posix()
    rc = _write(tmp_path / "yaterc", f'theme_dirs = [{missing!r}]\n')
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.theme_dirs == []
    assert any("does not exist" in e and "nope" in e for e in config.errors)


def test_bad_theme_dirs_types(tmp_path: Path) -> None:
    rc = _write(tmp_path / "yaterc", "theme_dirs = 42\n")
    config = yrc.load_config([rc])
    assert any("theme_dirs" in e for e in config.errors)
    rc2 = _write(tmp_path / "yaterc2", 'theme_dirs = ["ok", 7]\n')
    config2 = yrc.load_config([rc2])
    assert any("non-empty strings" in e for e in config2.errors)


def test_theme_dirs_accumulate_and_dedupe(tmp_path: Path) -> None:
    tdir = tmp_path / "themes"
    tdir.mkdir()
    user_rc = _write(tmp_path / "user_rc", 'theme_dirs = ["themes"]\n')
    project_rc = _write(tmp_path / "project_rc", 'theme_dirs = ["themes", "."]\n')
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    assert config.theme_dirs == [tdir.resolve(), tmp_path.resolve()]


def test_theme_files_use_injected_register_helper(
    tmp_path: Path, registered_themes: list[str]
) -> None:
    # The file relies solely on the injected register_theme/Theme names.
    fields = (
        '"inj_theme", "Injected", True,'
        '"#11111b","#181825","#313244","#1e1e2e","#45475a",'
        '"#585b70","#f9e2af","#fab387","#11111b",'
        '"#cdd6f4","#6c7086","#9399b2","#bac2de",'
        '"#89b4fa","#cba6f7","#a6e3a1","#f9e2af","#f38ba8","#fab387",'
        '"#89b4fa","#a6e3a1","#cba6f7","#fab387",'
        '"#cba6f7","#a6e3a1","#fab387","#6c7086","#89b4fa","#f9e2af",'
        '"#fab387","#f38ba8","#f5c2e7","#89dceb","#b4befe"'
    )
    tdir = tmp_path / "themes"
    tdir.mkdir()
    _write(tdir / "inj.py", f"register_theme(Theme({fields}))\n")
    rc = _write(tmp_path / "yaterc", 'theme_dirs = "themes"\n')
    registered_themes.append("inj_theme")
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.errors == []
    assert themes.set_theme("inj_theme").name == "inj_theme"


# --- screen_saver option ----------------------------------------------------


def test_screen_saver_defaults() -> None:
    config = cfg.YateConfig()
    assert config.screen_saver.enable is True
    assert config.screen_saver.interval == 120
    assert config.screen_saver.switch == 0
    assert config.screen_saver.dist_bounds is None
    assert config.screen_saver.characters == ()


def test_screen_saver_absent_keeps_defaults(tmp_path: Path) -> None:
    config = _load('tab_width = 2\n', tmp_path)
    assert config.errors == []
    assert config.screen_saver == cfg.ScreenSaverConfig()


def test_screen_saver_full_valid_dict(tmp_path: Path) -> None:
    config = _load(
        'screen_saver = {\n'
        '    "enable": True,\n'
        '    "interval": 60,\n'
        '    "switch": 5,\n'
        '    "characters": ["mario", "pacman", "mario"],\n'
        "}\n",
        tmp_path,
    )
    assert config.errors == []
    assert config.screen_saver.enable is True
    assert config.screen_saver.interval == 60
    assert config.screen_saver.switch == 5
    # entries keep order, duplicates collapse
    assert config.screen_saver.characters == ("mario", "pacman")


def test_screen_saver_partial_dict_keeps_defaults(tmp_path: Path) -> None:
    config = _load('screen_saver = {"interval": 30}\n', tmp_path)
    assert config.errors == []
    assert config.screen_saver.interval == 30
    assert config.screen_saver.enable is True
    assert config.screen_saver.switch == 0
    assert config.screen_saver.characters == ()


def test_screen_saver_unknown_keys_reported(tmp_path: Path) -> None:
    config = _load(
        'screen_saver = {"interval": 30, "speed": 5}\n', tmp_path
    )
    assert config.screen_saver.interval == 30
    assert any("speed" in e for e in config.errors)


def test_screen_saver_bad_value_types_reported(tmp_path: Path) -> None:
    cases = {
        '"interval": "x"': "interval",
        '"enable": 1': "enable",
        '"switch": True': "switch",
        '"characters": "mario"': "characters",
        '"interval": -1': "interval",
        '"switch": 3601': "switch",
    }
    for body, key in cases.items():
        config = _load(f"screen_saver = {{{body}}}\n", tmp_path)
        assert config.errors, body
        assert any(f"screen_saver {key}" in e for e in config.errors), (body, config.errors)
        # the failing key keeps its default
        assert config.screen_saver == cfg.ScreenSaverConfig(), body


def test_screen_saver_not_a_dict_reported(tmp_path: Path) -> None:
    config = _load("screen_saver = True\n", tmp_path)
    assert config.screen_saver == cfg.ScreenSaverConfig()
    assert any("screen_saver" in e for e in config.errors)


def test_screen_saver_later_rc_replaces_whole(tmp_path: Path) -> None:
    user_rc = _write(
        tmp_path / "user", 'screen_saver = {"interval": 30}\n'
    )
    project_rc = _write(
        tmp_path / "project",
        'screen_saver = {"enable": False, "switch": 7}\n',
    )
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    assert config.screen_saver.enable is False
    assert config.screen_saver.interval == 120  # back to the default
    assert config.screen_saver.switch == 7


def test_screen_saver_dist_bounds_fraction_strings(tmp_path: Path) -> None:
    config = _load(
        'screen_saver = {"dist_lower_bound": "1/8", "dist_upper_bound": "1/3"}\n',
        tmp_path,
    )
    assert config.errors == []
    assert config.screen_saver.dist_bounds == (0.125, 1 / 3)


def test_screen_saver_dist_bounds_accept_floats_and_mix(tmp_path: Path) -> None:
    config = _load(
        'screen_saver = {"dist_lower_bound": 0.1, "dist_upper_bound": 0.5}\n',
        tmp_path,
    )
    assert config.errors == []
    assert config.screen_saver.dist_bounds == (0.1, 0.5)
    mixed = _load(
        'screen_saver = {"dist_lower_bound": "1/4", "dist_upper_bound": 0.75}\n',
        tmp_path,
    )
    assert mixed.errors == []
    assert mixed.screen_saver.dist_bounds == (0.25, 0.75)


def test_screen_saver_dist_bounds_require_both_keys(tmp_path: Path) -> None:
    for body in ('"dist_lower_bound": "1/8"', '"dist_upper_bound": "1/3"'):
        config = _load(f"screen_saver = {{{body}}}\n", tmp_path)
        assert any("must be set together" in e for e in config.errors), body
        # the incomplete pair falls back to the timing rule entirely
        assert config.screen_saver.dist_bounds is None, body


def test_screen_saver_dist_bounds_reject_bad_order(tmp_path: Path) -> None:
    config = _load(
        'screen_saver = {"dist_lower_bound": 0.5, "dist_upper_bound": 0.1}\n',
        tmp_path,
    )
    assert any(
        "dist_lower_bound must be less than dist_upper_bound" in e
        for e in config.errors
    )
    assert config.screen_saver.dist_bounds is None


def test_screen_saver_dist_bounds_bad_values_reported(tmp_path: Path) -> None:
    cases = ['"dist_lower_bound": True', '"dist_upper_bound": "1/0"',
             '"dist_upper_bound": "abc"', '"dist_upper_bound": 1.5',
             '"dist_lower_bound": 0']
    for body in cases:
        config = _load(f"screen_saver = {{{body}}}\n", tmp_path)
        assert config.errors, body
        assert any("must be a float in (0, 1)" in e for e in config.errors), (body, config.errors)
        assert config.screen_saver.dist_bounds is None, body


# --- file_preview option ----------------------------------------------------


def test_file_preview_defaults() -> None:
    config = cfg.YateConfig()
    assert config.file_preview == cfg.FilePreviewConfig()
    assert config.file_preview.enable is True
    assert config.file_preview.position == "right"
    assert config.file_preview.size == 60
    assert config.file_preview.max_lines == 2000
    assert config.file_preview.max_size == 1048576


def test_file_preview_absent_keeps_defaults(tmp_path: Path) -> None:
    config = _load('tab_width = 2\n', tmp_path)
    assert config.errors == []
    assert config.file_preview == cfg.FilePreviewConfig()


def test_file_preview_full_valid_dict(tmp_path: Path) -> None:
    config = _load(
        'file_preview = {\n'
        '    "enable": False,\n'
        '    "position": "left",\n'
        '    "size": 60,\n'
        '    "max_lines": 500,\n'
        '    "max_size": 4096,\n'
        "}\n",
        tmp_path,
    )
    assert config.errors == []
    assert config.file_preview.enable is False
    assert config.file_preview.position == "left"
    assert config.file_preview.size == 60
    assert config.file_preview.max_lines == 500
    assert config.file_preview.max_size == 4096


def test_file_preview_partial_dict_keeps_defaults(tmp_path: Path) -> None:
    config = _load('file_preview = {"size": 60}\n', tmp_path)
    assert config.errors == []
    assert config.file_preview.size == 60
    assert config.file_preview.enable is True
    assert config.file_preview.position == "right"
    assert config.file_preview.max_lines == 2000
    assert config.file_preview.max_size == 1048576


def test_file_preview_unknown_key_reported(tmp_path: Path) -> None:
    config = _load('file_preview = {"width": 50}\n', tmp_path)
    assert any("unknown keys" in e for e in config.errors)
    assert any("width" in e for e in config.errors)
    assert config.file_preview == cfg.FilePreviewConfig()


def test_file_preview_not_a_dict_reported(tmp_path: Path) -> None:
    config = _load("file_preview = True\n", tmp_path)
    assert config.file_preview == cfg.FilePreviewConfig()
    assert any("file_preview must be a dict" in e for e in config.errors)


def test_file_preview_bad_position_rejected(tmp_path: Path) -> None:
    config = _load('file_preview = {"position": "up"}\n', tmp_path)
    assert config.errors
    assert any("file_preview position" in e for e in config.errors)
    assert config.file_preview.position == "right"


def test_file_preview_bad_enable_rejected(tmp_path: Path) -> None:
    for body in ('"enable": 1', '"enable": "yes"'):
        config = _load(f"file_preview = {{{body}}}\n", tmp_path)
        assert config.errors, body
        assert any("file_preview enable" in e for e in config.errors)
        assert config.file_preview.enable is True


def test_file_preview_bad_size_rejected(tmp_path: Path) -> None:
    for body in ('"size": True', '"size": 5', '"size": 90'):
        config = _load(f"file_preview = {{{body}}}\n", tmp_path)
        assert config.errors, body
        assert any("file_preview size" in e for e in config.errors), (body, config.errors)
        # the failing key keeps its default (bool masquerading as int is caught)
        assert config.file_preview.size == 60, body


def test_file_preview_bad_limits_rejected(tmp_path: Path) -> None:
    config = _load('file_preview = {"max_lines": 0}\n', tmp_path)
    assert any("file_preview max_lines" in e for e in config.errors)
    assert config.file_preview.max_lines == 2000
    config = _load('file_preview = {"max_size": 1}\n', tmp_path)
    assert any("file_preview max_size" in e for e in config.errors)
    assert config.file_preview.max_size == 1048576


def test_file_preview_later_declaration_replaces(tmp_path: Path) -> None:
    user_rc = _write(tmp_path / "user", 'file_preview = {"size": 60}\n')
    project_rc = _write(
        tmp_path / "project",
        'file_preview = {"enable": False, "position": "left"}\n',
    )
    config = yrc.load_config([user_rc, project_rc])
    assert config.errors == []
    assert config.file_preview == cfg.FilePreviewConfig(enable=False, position="left")


# --- shipped example --------------------------------------------------------


def test_shipped_example_loads_cleanly() -> None:
    example = Path(__file__).parent.parent / "yate" / "yaterc.example"
    assert example.is_file(), "yaterc.example must ship in yate/"
    config = yrc.load_config([example])
    assert config.errors == []
    assert config.sources == [example]
    # the example's active options are the documented defaults
    assert config.keymap == "vsc"
    assert config.theme == "mocha"
    assert config.tab_width == 4
    assert config.use_spaces


# --- custom theme registration ---------------------------------------------


def test_register_theme_from_rc(
    tmp_path: Path, registered_themes: list[str]
) -> None:
    body = (
        "from dataclasses import replace\n"
        "from yate.editor_view.theme import THEMES\n"
        "register_theme(replace(THEMES['mocha'], name='yate_test_theme'))\n"
        'theme = "yate_test_theme"\n'
    )
    registered_themes.append("yate_test_theme")
    rc = _write(tmp_path / "yaterc", body)
    config = yrc.load_config(
        [rc],
        register_theme=themes.register_theme,
        load_theme_paths=themes.load_theme_paths,
    )
    assert config.errors == []
    assert config.theme == "yate_test_theme"
    activated = themes.set_theme("yate_test_theme")
    assert activated.name == "yate_test_theme"
    # mocha palette copied through
    assert activated.bg == themes.THEMES["mocha"].bg


# --- headless mode (no injected theme callbacks) -----------------------------


def test_load_config_without_theme_hooks_records_register_theme_error(
    tmp_path: Path,
) -> None:
    # N30: with the default (None) hooks the namespace lacks register_theme;
    # the NameError is recorded per file and the remaining files still run.
    rc1 = _write(tmp_path / "user_rc", "register_theme(None)\n")
    rc2 = _write(tmp_path / "project_rc", "tab_width = 2\n")
    config = yrc.load_config([rc1, rc2])
    assert len(config.errors) == 1, config.errors
    assert "NameError" in config.errors[0]
    assert "register_theme" in config.errors[0]
    assert config.tab_width == 2
    assert config.theme == "mocha"


def test_load_config_without_theme_hooks_keeps_theme_dirs_unloaded(
    tmp_path: Path,
) -> None:
    # N30: theme_dirs is still extracted (the caller decides what loading
    # means); without the loader hook no theme file is ever exec'd.
    tdir = tmp_path / "themes"
    tdir.mkdir()
    _theme_file(tdir, "mytheme.py", "yate_test_unloaded")
    rc = _write(tmp_path / "yaterc", 'theme_dirs = "themes"\n')
    config = yrc.load_config([rc])
    assert config.theme_dirs == [tdir.resolve()]
    assert config.errors == []
    assert "yate_test_unloaded" not in themes.available()


# --- app integration --------------------------------------------------------


def test_app_applies_config() -> None:
    from yate.app import YateApp

    config = cfg.YateConfig(
        keymap="vim",
        theme="latte",
        tab_width=2,
        use_spaces=False,
    )
    try:
        app = YateApp(config=config)
        assert app.editor.keymaps.name == "vim"
        assert themes.active().name == "latte"
        assert app.editor.session.buffer.tab_width == 2
        assert not app.editor.session.buffer.use_spaces
        # buffers created afterwards inherit the options too
        app.editor.document_flows.new_buffer(show=False)
        assert app.editor.session.buffer.tab_width == 2
    finally:
        themes.set_theme("mocha")


def test_app_unknown_theme_records_error() -> None:
    from yate.app import YateApp

    config = cfg.YateConfig(theme="no-such-theme")
    try:
        app = YateApp(config=config)
        assert any("unknown theme" in e for e in app.config.errors)
    finally:
        themes.set_theme("mocha")
