"""Sentinel: the global isolation fixture must stay active.

If any of these assertions fail, the autouse ``isolated_home`` fixture in
conftest.py was removed or broken and tests would touch the real ~/.yate.
"""

from __future__ import annotations

import os
from pathlib import Path


def test_home_is_isolated(isolated_home: Path) -> None:
    assert Path.home() == isolated_home
    assert os.environ["USERPROFILE"] == str(isolated_home)
    assert os.environ["HOME"] == str(isolated_home)


def test_yaterc_does_not_exist(isolated_home: Path) -> None:
    assert not (isolated_home / ".yate" / "yaterc").exists()


def test_expanduser_resolves_to_isolated_home(isolated_home: Path) -> None:
    assert Path("~/foo").expanduser() == isolated_home / "foo"
