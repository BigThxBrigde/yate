"""Unit tests for the extension loader (discovery, exclude, de-duplication)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from yate.services.extensions import (
    ExtensionAPI,
    ExtensionContext,
    ExtensionLoader,
)

_SETUP_OK = "def setup(api):\n    pass\n"
_SETUP_BAD = "def setup(api):\n    raise RuntimeError('boom')\n"


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
