"""Regression tests for the interactive win32-input-mode probe (m20).

Pins review finding m20 only: the probe enters an infinite key-reading loop
that rewrites the terminal's input mode, so it must never run at import
time -- any stray ``import tools.probes.win32im_probe`` (IDE indexing,
``python -c`` completion) previously hijacked the caller's console.
"""

from __future__ import annotations

import inspect

from tools.probes import win32im_probe


def test_probe_module_import_does_not_enter_main_loop() -> None:
    """Importing the module defines main() but does not call it (m20)."""
    assert callable(win32im_probe.main)


def test_probe_main_is_guarded_behind___main__() -> None:
    """The module-level call site is fenced by ``if __name__ == "__main__"``.

    Source-text pin: the defect only manifests through an import in an
    interactive console, which no unit test can simulate safely (the
    unguarded variant would hang the test process).
    """
    source = inspect.getsource(win32im_probe)
    assert 'if __name__ == "__main__":' in source
    assert "main()" in source.split('if __name__ == "__main__":', 1)[1]
