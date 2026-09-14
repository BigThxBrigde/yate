"""Global test isolation: no test may touch the real user ~/.yate.

A single autouse fixture (function-scoped) redirects home for every test:

- ``Path.home()`` is patched to a per-test temp directory (config.py, crash.py,
  app.py, cli.py, user_setup.py, diagnostics.py, fonts.py all call it).
- ``USERPROFILE`` (Windows ntpath) and ``HOME`` (POSIX posixpath) are set so
  ``expanduser("~")`` string paths resolve to the same temp dir.

The temp home is empty, so ``~/.yate/yaterc``, themes and extensions never
exist during tests: user extensions are not executed, user config/themes are
not read. Tests that need "user config present" write it explicitly under the
returned directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point home (Path.home + USERPROFILE/HOME) at a per-test temp dir.

    The home directory lives *outside* ``tmp_path`` (created via
    ``tmp_path_factory``): tests legitimately use ``tmp_path`` as a workspace
    root and assert on its contents, so it must stay unpolluted.
    """
    home = tmp_path_factory.mktemp("isolated_home")

    def _fake_home(cls: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(_fake_home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home
