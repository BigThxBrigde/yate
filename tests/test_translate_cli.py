"""Regression tests for the wiki translator's temp-file write failure (m15).

``tests/test_tools_translate.py`` owns the general translator coverage; this
module pins review finding m15 only: writing the stdin spill file to the
temporary directory that can fail with ``OSError`` must be reported with the
``wiki-translate:`` prefix (exit 1) instead of a bare traceback -- the
module promises "failure always reports as one prefixed line".
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from tools.translate import cli


@pytest.fixture
def stdin_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed the translator through a stdin stub (the temp-write path)."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("# zh source\n"))


def test_temp_write_failure_reports_prefixed_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stdin_text: None,
) -> None:
    """An OSError while spilling stdin to the temp file exits 1, prefixed."""
    real_write_text = Path.write_text

    def failing_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self.name == "stdin.md":
            raise OSError("disk full")
        return real_write_text(self, data, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    assert cli.main([]) == 1

    err = capsys.readouterr().err
    assert err.startswith("wiki-translate:")
    assert "cannot write" in err
    assert "disk full" in err
