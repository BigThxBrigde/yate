"""Headless tests for the command line entry point (yate.cli).

Argument parsing plus the pre-TUI startup path (config + custom theme
loading).  Launching the real TUI needs a terminal, so ``main()`` is run
with ``yate.app.YateApp`` replaced by a fake that records its kwargs and
never enters Textual.

``main()`` tests always pass ``-u NONE`` (or an explicit rc path):
``find_project_config`` walks up from the cwd looking for a yaterc, which is
a cwd-facing pollution surface the home isolation fixture cannot cover.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import yate
from yate.cli import build_parser, main

_CUSTOM_THEME_SRC = """\
from dataclasses import replace

from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"], name="cli-custom", label="CLI Custom", accent="#ff0000"
))
"""


class _FakeEditor:
    """The slice of Editor that main() touches on the --diag path."""

    def __init__(self) -> None:
        self.load_startup_services_called = False

    def load_startup_services(self) -> None:
        self.load_startup_services_called = True


class _FakeApp:
    """Records constructor kwargs instead of launching the TUI."""

    last_kwargs: dict[str, object] | None = None
    last_instance: "_FakeApp | None" = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        type(self).last_instance = self
        self.editor = _FakeEditor()

    def run(self) -> None:
        return None


# --- parser -----------------------------------------------------------------


def test_extension_dests_default_to_empty_lists() -> None:
    args = build_parser().parse_args([])
    assert args.ext_files == []
    assert args.ext_dirs == []


def test_ext_flags_are_repeatable_into_expected_dests() -> None:
    args = build_parser().parse_args(
        ["--ext", "a.py", "--ext", "b.py", "--ext-dir", "exts", "--ext-dir", "more"]
    )
    assert args.ext_files == ["a.py", "b.py"]
    assert args.ext_dirs == ["exts", "more"]


def test_theme_dir_flag_repeatable_into_expected_dest() -> None:
    assert build_parser().parse_args([]).theme_dirs == []
    args = build_parser().parse_args(
        ["--theme-dir", "themes", "--theme-dir", "extra"]
    )
    assert args.theme_dirs == ["themes", "extra"]


def test_theme_flag() -> None:
    assert build_parser().parse_args([]).theme is None
    assert build_parser().parse_args(["--theme", "latte"]).theme == "latte"


def test_keymap_flag_and_alias() -> None:
    assert build_parser().parse_args(["--keymap", "vim"]).keymap == "vim"
    # "normal" is the documented vsc alias and must parse without error.
    assert build_parser().parse_args(["--keymap", "normal"]).keymap == "normal"


def test_yaterc_none_and_path() -> None:
    assert build_parser().parse_args(["-u", "NONE"]).yaterc == "NONE"
    assert build_parser().parse_args(["-u", "rc.py"]).yaterc == "rc.py"


def test_positional_path() -> None:
    assert build_parser().parse_args(["some/file.txt"]).path == "some/file.txt"
    assert build_parser().parse_args([]).path is None


def test_version_flag_is_store_true() -> None:
    assert not build_parser().parse_args([]).version
    assert build_parser().parse_args(["--version"]).version


def test_diag_flag_is_store_true() -> None:
    assert not build_parser().parse_args([]).diag
    assert build_parser().parse_args(["--diag"]).diag


def test_changelog_flag_defaults_to_en() -> None:
    assert build_parser().parse_args([]).changelog is None
    assert build_parser().parse_args(["--changelog"]).changelog == "en"
    assert build_parser().parse_args(["--changelog", "zh"]).changelog == "zh"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--changelog", "fr"])


# --- --changelog ------------------------------------------------------------


def _run_changelog(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    with patch("yate.app.YateApp") as fake_app, \
            patch("yate.config.load_config") as load_config, \
            patch("yate.logs.crash.install"):
        rc = main(argv)
    out = capsys.readouterr().out
    fake_app.assert_not_called()
    load_config.assert_not_called()
    return rc, out


def test_changelog_prints_bundled_content_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, out = _run_changelog(["--changelog"], capsys)
    assert rc == 0
    assert out.startswith("# Changelog")


def test_changelog_lang_selects_edition(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, out = _run_changelog(["--changelog", "zh"], capsys)
    assert rc == 0
    assert out.startswith("# 变更日志")


def test_changelog_missing_resource_degrades_without_raising(
    capsys: pytest.CaptureFixture[str],
) -> None:
    placeholder = "# Changelog\n\nNo changelog is shipped with this build."
    with patch("yate.editor_view.manual.load_changelog_markdown",
               return_value=placeholder):
        rc, out = _run_changelog(["--changelog"], capsys)
    assert rc == 0
    assert "No changelog is shipped" in out


# --- --version / --diag -----------------------------------------------------


def test_version_prints_basic_info_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("yate.app.YateApp") as fake_app, \
            patch("yate.config.load_config") as load_config, \
            patch("yate.logs.crash.install"):
        rc = main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert f"yate {yate.__version__}" in out
    # the description is part of the first line
    assert "yet another terminal editor" in out.splitlines()[0]
    assert "Python" in out
    # platform string is present on the third line
    assert len(out.splitlines()) > 2
    # --version must not construct the app or read any config
    fake_app.assert_not_called()
    load_config.assert_not_called()


def test_diag_prints_report_without_running_tui(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "DIAG-REPORT-SENTINEL"
    with patch("yate.app.YateApp", _FakeApp), \
            patch("yate.diagnostics.format_report", return_value=sentinel) as fmt, \
            patch("yate.logs.crash.install"):
        rc = main(["-u", "NONE", "--diag"])
    assert rc == 0
    assert sentinel in capsys.readouterr().out
    # format_report was called once with the constructed app's editor
    assert fmt.call_count == 1
    editor_arg = fmt.call_args.args[0]
    assert isinstance(editor_arg, _FakeEditor)
    # startup services were loaded so the report reflects real state
    assert editor_arg.load_startup_services_called


def test_diag_with_none_yaterc_reports_no_rc_loaded(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """-u NONE --diag must report that no yaterc was loaded."""
    monkeypatch.setattr("yate.logs.crash.install", lambda: None)
    rc = main(["-u", "NONE", "--diag"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[yaterc]" in out
    assert "no yaterc loaded" in out


# --- theme startup ----------------------------------------------------------


@pytest.fixture
def _custom_theme_cleanup() -> Any:
    yield
    from yate.editor_view import theme as theme_mod

    theme_mod.THEMES.pop("cli-custom", None)
    theme_mod.set_theme("mocha")


# pytest resolves fixtures by parameter name (see the two tests below), so
# nothing ever refers to the definition itself. Keep one explicit reference
# so static analysis does not report it as dead code.
_THEME_FIXTURES = (_custom_theme_cleanup,)


def _run_main(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    with patch("yate.app.YateApp", _FakeApp), \
            patch("yate.logs.crash.install") as install_crash:
        rc = main(argv)
    capsys.readouterr()  # drain main()'s stdout
    assert rc == 0
    # diagnostics are armed before anything else in main()
    install_crash.assert_called_once_with()
    assert _FakeApp.last_kwargs is not None
    return _FakeApp.last_kwargs


def test_theme_dir_auto_loads_and_theme_selects_custom_theme(
    capsys: pytest.CaptureFixture[str], _custom_theme_cleanup: None, tmp_path: Path
) -> None:
    from yate.editor_view import theme as theme_mod

    folder = tmp_path / "mythemes"
    folder.mkdir()
    (folder / "custom.py").write_text(_CUSTOM_THEME_SRC, encoding="utf-8")
    kwargs = _run_main(
        ["-u", "NONE", "--theme-dir", str(folder), "--theme", "cli-custom"],
        capsys,
    )
    # the custom theme was registered before the app was built...
    assert "cli-custom" in theme_mod.available()
    assert kwargs["theme_name"] == "cli-custom"
    # ...and the real constructor selects it as the process theme
    from yate.app import YateApp

    YateApp(theme_name="cli-custom")
    assert theme_mod.active().name == "cli-custom"


def test_theme_dir_tilde_is_expanded(
    capsys: pytest.CaptureFixture[str],
    _custom_theme_cleanup: None,
    isolated_home: Path,
) -> None:
    """PowerShell/cmd pass '~' literally; main() must expand it.

    Home is the fixture's isolated temp home, so ``~/mythemes`` is created
    there explicitly.
    """
    from yate.editor_view import theme as theme_mod

    folder = isolated_home / "mythemes"
    folder.mkdir(parents=True)
    (folder / "custom.py").write_text(_CUSTOM_THEME_SRC, encoding="utf-8")
    kwargs = _run_main(
        ["-u", "NONE", "--theme-dir", "~/mythemes", "--theme", "cli-custom"],
        capsys,
    )
    assert "cli-custom" in theme_mod.available()
    assert kwargs["theme_name"] == "cli-custom"


def test_unknown_theme_override_is_recorded_as_config_error() -> None:
    from yate.app import YateApp

    app = YateApp(theme_name="definitely-not-a-theme")
    assert any("unknown theme" in err for err in app.config.errors), \
        app.config.errors


def test_theme_name_defaults_to_none_when_flag_absent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    kwargs = _run_main(["-u", "NONE"], capsys)
    assert kwargs["theme_name"] is None


# --- --setup-defaults / --cleanup-defaults ----------------------------------


def _run_setup(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    *,
    setup: MagicMock | None = None,
    cleanup: MagicMock | None = None,
) -> tuple[int, str, MagicMock, MagicMock]:
    from yate.services import user_setup

    if setup is None:
        setup = MagicMock()
    if cleanup is None:
        cleanup = MagicMock()
    with patch("yate.app.YateApp") as fake_app, \
            patch("yate.config.load_config") as load_config, \
            patch("yate.logs.crash.install"), \
            patch.object(user_setup, "setup_defaults", setup) as s, \
            patch.object(user_setup, "cleanup_defaults", cleanup) as c:
        rc = main(argv)
    out = capsys.readouterr().out
    fake_app.assert_not_called()
    load_config.assert_not_called()
    return rc, out, s, c


def _setup_report(**kwargs: Any) -> object:
    from yate.services.user_setup import SetupReport

    return SetupReport(base_dir=Path.home() / ".yate", **kwargs)


def _cleanup_report(**kwargs: Any) -> object:
    from yate.services.user_setup import CleanupReport

    return CleanupReport(base_dir=Path.home() / ".yate", **kwargs)


def test_parser_flags_and_mutual_exclusion() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert not args.setup_defaults
    assert not args.cleanup_defaults
    assert not args.force
    assert not args.include_data
    assert parser.parse_args(["--setup-defaults"]).setup_defaults
    assert parser.parse_args(["--cleanup-defaults"]).cleanup_defaults
    assert parser.parse_args(
        ["--cleanup-defaults", "--force", "--include-data"]
    ).include_data
    with pytest.raises(SystemExit) as ctx:
        parser.parse_args(["--setup-defaults", "--cleanup-defaults"])
    assert ctx.value.code == 2


def test_help_text_lists_both_options() -> None:
    help_text = build_parser().format_help()
    assert "--setup-defaults" in help_text
    assert "--cleanup-defaults" in help_text
    assert "--include-data" in help_text


def test_setup_defaults_invokes_service_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup = MagicMock(return_value=_setup_report())
    rc, out, s, _ = _run_setup(["--setup-defaults"], capsys, setup=setup)
    assert rc == 0
    s.assert_called_once_with(force=False)
    assert "yate user directory" in out


def test_setup_defaults_force_passthrough_and_error_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ok = MagicMock(return_value=_setup_report())
    rc, _out, s, _ = _run_setup(["--setup-defaults", "--force"], capsys, setup=ok)
    assert rc == 0
    s.assert_called_once_with(force=True)

    failed = MagicMock(
        return_value=_setup_report(errors=["yaterc: disk full"])
    )
    rc, out, _, _ = _run_setup(["--setup-defaults"], capsys, setup=failed)
    assert rc == 1
    assert "disk full" in out


def test_cleanup_defaults_passes_force_and_include_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cleanup = MagicMock(return_value=_cleanup_report())
    with patch("yate.logs.crash.uninstall") as uninstall:
        rc, _, _, c = _run_setup(
            ["--cleanup-defaults", "--force", "--include-data"],
            capsys,
            cleanup=cleanup,
        )
    assert rc == 0
    c.assert_called_once_with(force=True, include_data=True)
    # The open crash report handle must be released first so data/ can
    # actually be removed (notably on Windows).
    uninstall.assert_called_once_with()


def test_cleanup_without_include_data_keeps_crash_handle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cleanup = MagicMock(return_value=_cleanup_report())
    with patch("yate.logs.crash.uninstall") as uninstall:
        rc, _, _, _ = _run_setup(
            ["--cleanup-defaults", "--force"], capsys, cleanup=cleanup
        )
    assert rc == 0
    uninstall.assert_not_called()


def test_cleanup_cancelled_still_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cleanup = MagicMock(return_value=_cleanup_report(cancelled=True))
    rc, out, _, _ = _run_setup(
        ["--cleanup-defaults", "--force"], capsys, cleanup=cleanup
    )
    assert rc == 0
    assert "cancelled" in out


def test_cleanup_confirmation_required_exits_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from yate.services.user_setup import ConfirmationRequiredError

    cleanup = MagicMock(side_effect=ConfirmationRequiredError("non-tty"))
    rc, out, _, _ = _run_setup(["--cleanup-defaults"], capsys, cleanup=cleanup)
    assert rc == 2
    assert "non-tty" in out
