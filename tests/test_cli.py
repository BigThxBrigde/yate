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

import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import yate
from conftest import make_yxp
from yate.cli import build_parser, main, version_lines

_CUSTOM_THEME_SRC: str = """\
from dataclasses import replace

from yate.editor_view.theme import THEMES, register_theme

register_theme(replace(
    THEMES["mocha"], name="cli-custom", label="CLI Custom", accent="#ff0000"
))
"""


class _FakeFlows:
    """The slice of ExtensionFlows that main() touches on the --diag path."""

    def __init__(self) -> None:
        self.extensions_loaded = False
        self.servers_registered = False

    def load_extensions(self) -> list[str]:
        """Record the startup load and report no extension output."""
        self.extensions_loaded = True
        return []

    def register_configured_servers(self) -> None:
        """Record the LSP server registration."""
        self.servers_registered = True


class _FakeEditor:
    """The slice of Editor that main() touches on the --diag path."""

    def __init__(self) -> None:
        self.extension_flows = _FakeFlows()


class _FakeApp:
    """Records constructor kwargs instead of launching the TUI."""

    last_kwargs: dict[str, object] | None = None
    last_instance: "_FakeApp | None" = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        type(self).last_instance = self
        self.editor = _FakeEditor()

    def run(self) -> None:
        """Do nothing; the TUI is never launched."""
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


def test_readonly_flag() -> None:
    assert build_parser().parse_args([]).readonly is False
    assert build_parser().parse_args(["--readonly"]).readonly is True
    assert build_parser().parse_args(["f.txt", "--readonly"]).readonly is True


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


# --- extension packages ------------------------------------------------------


def test_extension_package_flags_parse() -> None:
    args = build_parser().parse_args(
        ["--install-extension", "a.yxp", "--install-extension", "b.yxp"]
    )
    assert args.install_extensions == ["a.yxp", "b.yxp"]
    assert args.uninstall_extensions == []
    assert args.list_extensions is False
    args = build_parser().parse_args(["--uninstall-extension", "x"])
    assert args.uninstall_extensions == ["x"]
    args = build_parser().parse_args(["--list-extensions"])
    assert args.list_extensions is True


def test_extension_package_flags_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["--list-extensions", "--install-extension", "a.yxp"]
        )


def test_main_installs_and_lists_extension_packages(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"print('hi')\n"})
    with patch("yate.logs.crash.install"):
        assert main(["--install-extension", str(pkg)]) == 0
        out = capsys.readouterr().out
        assert "installed hello 1.0.0" in out
        assert main(["--list-extensions"]) == 0
    assert "hello 1.0.0" in capsys.readouterr().out
    # The isolated-home fixture points ~/.yate at a temp dir.
    assert (Path.home() / ".yate" / "extensions" / "hello.py").exists()


def test_main_uninstall_extension_package(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pkg = make_yxp(tmp_path / "hello.yxp", {"hello.py": b"x"})
    with patch("yate.logs.crash.install"):
        main(["--install-extension", str(pkg)])
        capsys.readouterr()
        assert main(["--uninstall-extension", "hello"]) == 0
    assert "removed hello" in capsys.readouterr().out
    assert not (Path.home() / ".yate" / "extensions" / "hello.py").exists()


def test_main_install_extension_failure_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = Path.home() / "missing.yxp"
    with patch("yate.logs.crash.install"):
        assert main(["--install-extension", str(missing)]) == 1
    assert "error:" in capsys.readouterr().err


# --- --diff -----------------------------------------------------------------


def test_cli_diff_two_files_defaults_two_way() -> None:
    args = build_parser().parse_args(["--diff", "a", "b"])
    assert args.diff_files == ["a", "b"]
    assert args.three_way is False
    assert args.two_way is False


def test_cli_diff_three_files_with_flag_parses() -> None:
    args = build_parser().parse_args(["--diff", "a", "b", "c", "--3way"])
    assert args.diff_files == ["a", "b", "c"]
    assert args.three_way is True


def _expect_cli_error(argv: list[str]) -> None:
    """main() rejects *argv* through ``parser.error`` (exit code 2)."""
    with (
        patch("yate.logs.crash.install"),
        pytest.raises(SystemExit) as ctx,
    ):
        main(argv)
    assert ctx.value.code == 2


def test_cli_diff_rejects_positional_conflict() -> None:
    _expect_cli_error(["f", "--diff", "a", "b"])


def test_cli_diff_rejects_wrong_file_count() -> None:
    _expect_cli_error(["--diff", "a"])


def test_cli_three_way_requires_three_files() -> None:
    _expect_cli_error(["--diff", "a", "b", "--3way"])


def test_cli_two_way_rejects_three_files() -> None:
    _expect_cli_error(["--diff", "a", "b", "c", "--2way"])


def test_cli_two_and_three_way_mutually_exclusive() -> None:
    with pytest.raises(SystemExit) as ctx:
        build_parser().parse_args(["--diff", "a", "b", "--2way", "--3way"])
    assert ctx.value.code == 2


# --- --changelog ------------------------------------------------------------


def _run_changelog(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    with (
        patch("yate.app.YateApp") as fake_app,
        patch("yate.yaterc.load_config") as load_config,
        patch("yate.logs.crash.install"),
    ):
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
    with (
        patch("yate.app.YateApp") as fake_app,
        patch("yate.yaterc.load_config") as load_config,
        patch("yate.logs.crash.install"),
    ):
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


def test_version_lines_content() -> None:
    text = version_lines()
    lines = text.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("yate ")
    # the description is part of the first line
    assert "yet another terminal editor" in lines[0]
    assert "Python" in lines[1]
    # platform line is non-empty and comes from platform.platform()
    assert lines[2]


def test_version_never_imports_the_tui_stack() -> None:
    """--version stays instant: it must not import the TUI stack.

    Runs in a subprocess because in-process the TUI is usually already
    imported by other tests, so a ``sys.modules`` check would lie.
    """
    code = (
        "import sys; from yate.cli import main; main(['--version']);"
        "assert 'yate.editor' not in sys.modules, 'yate.editor imported';"
        "assert 'textual' not in sys.modules, 'textual imported'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True
    )
    assert proc.returncode == 0, (
        f"child exited {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


def test_diag_prints_report_without_running_tui(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "DIAG-REPORT-SENTINEL"
    with (
        patch("yate.app.YateApp", _FakeApp),
        patch("yate.diagnostics.format_report", return_value=sentinel) as fmt,
        patch("yate.logs.crash.install"),
    ):
        rc = main(["-u", "NONE", "--diag"])
    assert rc == 0
    assert sentinel in capsys.readouterr().out
    # format_report was called once with the constructed app's editor
    assert fmt.call_count == 1
    editor_arg = fmt.call_args.args[0]
    assert isinstance(editor_arg, _FakeEditor)
    # extension startup ran so the report reflects real state
    assert editor_arg.extension_flows.extensions_loaded
    assert editor_arg.extension_flows.servers_registered


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
_THEME_FIXTURES: tuple[object, ...] = (_custom_theme_cleanup,)


def _run_main(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    with (
        patch("yate.app.YateApp", _FakeApp),
        patch("yate.logs.crash.install") as install_crash,
    ):
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
    assert any("unknown theme" in err for err in app.config.errors), app.config.errors


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
    with (
        patch("yate.app.YateApp") as fake_app,
        patch("yate.yaterc.load_config") as load_config,
        patch("yate.logs.crash.install"),
        patch.object(user_setup, "setup_defaults", setup) as s,
        patch.object(user_setup, "cleanup_defaults", cleanup) as c,
    ):
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


# --- --hex validation (coverage plan-c) --------------------------------------


def test_cli_hex_rejects_startup_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--hex cannot be combined with a startup path argument."""
    _expect_cli_error(["f.txt", "--hex", "dump.bin"])
    assert "--hex cannot be combined with a startup path" in (
        capsys.readouterr().err
    )


def test_cli_hex_rejects_diff_combination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--hex cannot be combined with --diff."""
    _expect_cli_error(["--diff", "a", "b", "--hex", "dump.bin"])
    assert "--hex cannot be combined with --diff" in capsys.readouterr().err


# --- extension package errors ------------------------------------------------


def test_cli_uninstall_reports_yxp_error_and_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failing uninstall prints 'error:' to stderr and exits 1."""
    from yate.services.yxp import YxpError

    with (
        patch("yate.logs.crash.install"),
        patch(
            "yate.services.yxp.uninstall_package",
            side_effect=YxpError("pkg missing"),
        ),
    ):
        rc = main(["--uninstall-extension", "hello"])
    assert rc == 1
    assert "error: pkg missing" in capsys.readouterr().err


# --- --install-font ----------------------------------------------------------


def test_cli_install_font_success_and_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--install-font reports an existing font and maps the result to rc."""
    from yate.services.fonts import FontStatus

    with (
        patch("yate.logs.crash.install"),
        patch(
            "yate.services.fonts.font_status",
            return_value=FontStatus(has_nerd_font=True, installed_fonts=["X NFM"]),
        ),
        patch(
            "yate.services.fonts.ensure_font",
            return_value=FontStatus(has_nerd_font=True, detail="installed"),
        ),
    ):
        assert main(["--install-font"]) == 0
    out = capsys.readouterr().out
    assert "Nerd Font already available" in out
    assert "installed" in out

    with (
        patch("yate.logs.crash.install"),
        patch(
            "yate.services.fonts.font_status",
            return_value=FontStatus(has_nerd_font=False),
        ),
        patch(
            "yate.services.fonts.ensure_font",
            return_value=FontStatus(has_nerd_font=False, detail="no fonts bundled"),
        ),
    ):
        assert main(["--install-font"]) == 1
    out = capsys.readouterr().out
    assert "Nerd Font already available" not in out
    assert "no fonts bundled" in out


# --- rc discovery ------------------------------------------------------------


def test_cli_main_yaterc_explicit_path_and_default_discovery(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """An explicit -u path wins; the default discovery feeds load_config."""
    from yate.config import YateConfig

    rc = tmp_path / "my.rc"
    rc.write_text("", encoding="utf-8")
    sentinel = [Path("discovered.rc")]
    with (
        patch("yate.app.YateApp", _FakeApp),
        patch("yate.logs.crash.install"),
        patch("yate.yaterc.load_config", return_value=YateConfig()) as load_cfg,
    ):
        assert main(["-u", str(rc)]) == 0
        assert load_cfg.call_args.args[0] == [Path(rc)]

        with patch("yate.yaterc.default_rc_paths", return_value=sentinel):
            assert main([]) == 0
        assert load_cfg.call_args.args[0] == sentinel
    capsys.readouterr()


def test_cli_main_logs_config_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """config.errors are surfaced through the module logger as a warning."""
    from yate.config import YateConfig

    cfg = YateConfig()
    cfg.errors = ["boom-a", "boom-b"]
    fake_log = MagicMock()
    with (
        patch("yate.app.YateApp", _FakeApp),
        patch("yate.logs.crash.install"),
        patch("yate.yaterc.load_config", return_value=cfg),
        patch("yate.cli.log", fake_log),
    ):
        assert main(["-u", "NONE"]) == 0
    capsys.readouterr()
    fake_log.warning.assert_called_once()
    assert "config errors" in str(fake_log.warning.call_args.args[0])
    assert "boom-a; boom-b" in str(fake_log.warning.call_args.args[1])


def test_cli_main_keymap_normal_alias_maps_to_vsc(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--keymap normal is the documented alias for vsc."""
    kwargs = _run_main(["--keymap", "normal", "-u", "NONE"], capsys)
    assert kwargs["keymap"] == "vsc"
    kwargs = _run_main(["--keymap", "vim", "-u", "NONE"], capsys)
    assert kwargs["keymap"] == "vim"
    kwargs = _run_main(["-u", "NONE"], capsys)
    assert kwargs["keymap"] is None


# --- module entry point ------------------------------------------------------


def test_dunder_main_entry_exits_through_main() -> None:
    """``python -m yate.cli`` raises SystemExit(main()) and honors --version."""
    proc = subprocess.run(
        [sys.executable, "-m", "yate.cli", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert f"yate {yate.__version__}" in proc.stdout
