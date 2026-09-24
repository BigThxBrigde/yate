"""Unit tests for the extension loader (discovery, exclude, de-duplication)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from yate.config import YateConfig
from yate.services import trust
from yate.services.extensions import (
    ExtensionAPI,
    ExtensionContext,
    ExtensionLoader,
    load_startup_extensions,
)

_SETUP_OK = "def setup(api):\n    pass\n"
_SETUP_BAD = "def setup(api):\n    raise RuntimeError('boom')\n"


class _LogCapture(logging.Handler):
    """Collect messages from one logger.

    The ``yate`` root logger never propagates (``propagate = False``), so
    pytest's caplog cannot see child-logger records; attach this instead.
    """

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _extension_api() -> ExtensionAPI:
    """ExtensionAPI over a minimal context (loaded scripts only call setup)."""
    ctx = ExtensionContext(
        session=cast(Any, MagicMock()),
        workspace=cast(Any, MagicMock()),
        lsp=cast(Any, MagicMock()),
        keymaps=cast(Any, MagicMock()),
        actions=cast(Any, MagicMock()),
        commands=cast(Any, MagicMock()),
        message=lambda _text: None,
        run_shell=lambda _command, _show: None,
        open_path=lambda _path: None,
        save=lambda: None,
    )
    return ExtensionAPI(ctx)


@pytest.fixture
def loader() -> ExtensionLoader:
    return ExtensionLoader(_extension_api())


# --- workspace trust gating --------------------------------------------------


def _startup_config() -> YateConfig:
    return cast(
        YateConfig,
        MagicMock(extension_paths=[], disabled_extensions=[]),
    )


def test_startup_skips_untrusted_cwd_extensions(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "extensions").mkdir()
    (tmp_path / "extensions" / "a.py").write_text(_SETUP_OK, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(trust, "TRUST_FILE", tmp_path / "trusted.txt")
    messages = load_startup_extensions(loader, _startup_config())
    assert any("skipped untrusted" in message for message in messages)
    assert all(record.name != "a" for record in loader.loaded)


def test_startup_loads_cwd_extensions_in_trusted_workspace(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "extensions").mkdir()
    (tmp_path / "extensions" / "a.py").write_text(_SETUP_OK, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "trusted.txt"
    monkeypatch.setattr(trust, "TRUST_FILE", store)
    trust.trust_workspace(tmp_path, store)
    messages = load_startup_extensions(loader, _startup_config())
    assert not any("skipped untrusted" in message for message in messages)
    assert any(record.name == "a" for record in loader.loaded)


def _symlinked_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Build ``real/extensions/a.py`` plus a ``link -> real`` symlink.

    Returns ``(real, link)``.  Symlink creation is unavailable on a stock
    Windows setup, so callers must skip when it raises.
    """
    real = tmp_path / "real"
    (real / "extensions").mkdir(parents=True)
    (real / "extensions" / "a.py").write_text(_SETUP_OK, encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not supported on this platform")
    return real, link


def test_startup_resolves_a_symlinked_cwd_for_trust_and_loading(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symlinked cwd loads through the resolved root the trust store holds.

    The trust store keeps resolved roots, so the project directory must be
    resolved *before* it is loaded; judging one path and loading another is
    exactly what the resolved ``cwd`` prevents.
    """
    real, link = _symlinked_workspace(tmp_path)
    store = tmp_path / "trusted.txt"
    monkeypatch.setattr(trust, "TRUST_FILE", store)
    monkeypatch.chdir(link)

    trust.trust_workspace(real, store)
    messages = load_startup_extensions(loader, _startup_config())
    assert not any("skipped untrusted" in message for message in messages)
    loaded = next(record for record in loader.loaded if record.name == "a")
    # The directory that was actually loaded is the resolved one, not the link.
    assert loaded.path.parent.parent == real.resolve()


def test_startup_reports_the_resolved_path_when_skipping_a_symlinked_cwd(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The untrusted-skip message names the resolved directory, not the link."""
    real, link = _symlinked_workspace(tmp_path)
    monkeypatch.setattr(trust, "TRUST_FILE", tmp_path / "trusted.txt")
    monkeypatch.chdir(link)

    messages = load_startup_extensions(loader, _startup_config())
    skipped = [message for message in messages if "skipped untrusted" in message]
    assert skipped, messages
    assert str(real.resolve() / "extensions") in skipped[0]
    assert str(link / "extensions") not in skipped[0]
    assert all(record.name != "a" for record in loader.loaded)


def test_startup_treats_a_literal_symlink_entry_as_its_resolved_root(
    loader: ExtensionLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A literal symlink entry in the store equals the resolved root.

    ``load_trusted_workspaces`` resolves every entry, so storing the symlink
    spelling (instead of the real root) does *not* create a distinct trust
    state: it resolves to the same root and the project extensions load.
    """
    real, link = _symlinked_workspace(tmp_path)
    store = tmp_path / "trusted.txt"
    store.write_text(f"{link}\n", encoding="utf-8")
    monkeypatch.setattr(trust, "TRUST_FILE", store)
    monkeypatch.chdir(link)

    # The literal spelling resolves to the same root the loader judges.
    assert trust.is_trusted(real, store)
    messages = load_startup_extensions(loader, _startup_config())
    assert not any("skipped untrusted" in message for message in messages)
    assert any(record.name == "a" for record in loader.loaded)


# --- discovery --------------------------------------------------------------


def test_load_directory_loads_sorted_py_files(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    (tmp_path / "b.py").write_text(_SETUP_OK, encoding="utf-8")
    (tmp_path / "a.py").write_text(_SETUP_OK, encoding="utf-8")
    (tmp_path / "_hidden.py").write_text(_SETUP_OK, encoding="utf-8")
    (tmp_path / "note.txt").write_text(_SETUP_OK, encoding="utf-8")
    records = loader.load_directory(tmp_path)
    assert [r.name for r in records] == ["a", "b"]
    assert all(r.error is None for r in records)


def test_load_directory_exclude_skips_stems(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    (tmp_path / "keep.py").write_text(_SETUP_OK, encoding="utf-8")
    (tmp_path / "skip.py").write_text(_SETUP_BAD, encoding="utf-8")
    records = loader.load_directory(tmp_path, exclude=["skip"])
    assert [r.name for r in records] == ["keep"]


def test_missing_directory_is_empty(loader: ExtensionLoader) -> None:
    assert loader.load_directory(Path("/no/such/dir")) == []


# --- de-duplication ---------------------------------------------------------


def test_same_file_loaded_once_across_sources(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    script = tmp_path / "one.py"
    script.write_text(_SETUP_OK, encoding="utf-8")
    first = loader.load_file(script)
    second = loader.load_file(script.resolve())
    assert first is second
    assert len(loader.loaded) == 1


# --- error handling ---------------------------------------------------------


def test_setup_error_is_recorded_not_raised(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    script = tmp_path / "broken.py"
    script.write_text(_SETUP_BAD, encoding="utf-8")
    record = loader.load_file(script)
    assert record.error is not None
    assert "RuntimeError" in (record.error or "")


def test_missing_setup_function_is_an_error(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    script = tmp_path / "nosetup.py"
    script.write_text("x = 1\n", encoding="utf-8")
    record = loader.load_file(script)
    assert "no setup(api)" in (record.error or "")


def test_failing_module_exec_leaves_no_sys_modules_entry(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    """S33: a module that dies at import must not linger under sys.modules.

    A half-initialized leftover would make a later import of the same name
    hit the broken remains instead of a clean retry.
    """
    script = tmp_path / "broken_import.py"
    script.write_text("raise RuntimeError('import boom')\n", encoding="utf-8")

    record = loader.load_file(script)

    assert record.error is not None
    assert "yate_ext_broken_import" not in sys.modules


def test_bind_key_with_unknown_keymap_warns_and_does_not_raise() -> None:
    """S34: a misspelled keymap name is reported, not silently dropped."""

    def _noop(_api: ExtensionContext) -> None:
        pass

    ctx = cast(Any, MagicMock())
    ctx.keymaps.get.return_value = None
    ctx.keymaps.names.return_value = ["vsc", "vim"]
    api = ExtensionAPI(cast(ExtensionContext, ctx))
    capture = _LogCapture()
    logger = logging.getLogger("yate.services.extensions")
    logger.addHandler(capture)
    try:
        bound = api.bind_key("<f5>", _noop, keymap="typo")
    finally:
        logger.removeHandler(capture)

    assert any("typo" in message and "vim" in message for message in capture.messages)
    # The decorator form still returns the callback and never raises.
    assert bound is not None


# --- teardown hooks ---------------------------------------------------------


def test_teardown_hook_is_captured_and_called(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    script = tmp_path / "res.py"
    script.write_text(
        "calls = []\n"
        "def setup(api):\n"
        "    calls.append('setup')\n"
        "def teardown(api):\n"
        "    calls.append('teardown')\n",
        encoding="utf-8",
    )
    record = loader.load_file(script)
    assert record.error is None
    assert record.teardown is not None
    assert record.module is not None
    assert record.module.calls == ["setup"]
    loader.teardown_all()
    assert record.module.calls == ["setup", "teardown"]


def test_teardown_error_does_not_block_other_extensions(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    (tmp_path / "a_bad.py").write_text(
        "def setup(api):\n"
        "    pass\n"
        "def teardown(api):\n"
        "    raise RuntimeError('cleanup boom')\n",
        encoding="utf-8",
    )
    (tmp_path / "b_good.py").write_text(
        "calls = []\n"
        "def setup(api):\n"
        "    pass\n"
        "def teardown(api):\n"
        "    calls.append('done')\n",
        encoding="utf-8",
    )
    loader.load_directory(tmp_path)
    loader.teardown_all()  # must not raise
    good = next(r for r in loader.loaded if r.name == "b_good")
    assert good.module is not None
    assert good.module.calls == ["done"]


def test_teardown_skipped_when_setup_failed(
    loader: ExtensionLoader, tmp_path: Path
) -> None:
    script = tmp_path / "broken.py"
    script.write_text(
        "def setup(api):\n"
        "    raise RuntimeError('boom')\n"
        "def teardown(api):\n"
        "    raise AssertionError('must not run')\n",
        encoding="utf-8",
    )
    record = loader.load_file(script)
    assert record.error is not None
    assert record.teardown is None
    loader.teardown_all()  # must not invoke the skipped hook
