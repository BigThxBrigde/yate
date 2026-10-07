"""Guard against drift between the ``dev`` and ``ts`` dependency groups.

``pyproject.toml`` lists the 26 tree-sitter requirements twice -- once in the
``dev`` group and once in the ``ts`` group -- because a bare ``.[dev]`` install
must pass the pyright strict gate (the stubs ``tests/test_ts_backend.py`` and
``yate/editor_syntax/ts_backend/`` need come from the same packages).  The only
sync mechanism is the ``# keep in sync`` comment; when the ts group is upgraded
and dev is forgotten, the strict type check silently drifts from the runtime
backend.  These tests fail on any such divergence.

PEP 735 ``dependency-groups`` would remove the duplication, but the tooling
baseline needs ``pip >= 25.1`` while the repo venv still runs pip 24.3.1, so
the migration is deferred (see the main plan, §四.3).  When it lands, delete
this file and remove this guard from the wave registration.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

_PYPROJECT_PATH: Path = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _package_name(requirement: str) -> str:
    """Return the normalized package name of a PEP 508 requirement string.

    Everything from the first version/extras/marker delimiter on is dropped,
    and the bare name is lowercased (``tree-sitter >=0.24`` and
    ``tree-sitter-c-sharp>=0.23`` both keep their exact spelling otherwise).
    """
    head = re.split(r"[><=!~;@\[( ]", requirement, maxsplit=1)[0]
    return head.strip().lower()


def _load_group(group: str) -> dict[str, str]:
    """Parse *group* out of ``pyproject.toml`` as ``{package name: requirement}``.

    The package name is normalized to lowercase; the value keeps the full
    requirement string (extras and version specifiers included) so the drift
    comparison is exact, character for character.
    """
    with _PYPROJECT_PATH.open("rb") as stream:
        raw = tomllib.load(stream)
    project = cast("dict[str, object]", raw["project"])
    optional = cast("dict[str, object]", project["optional-dependencies"])
    entries = cast("list[object]", optional.get(group))
    requirements: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, str):
            raise AssertionError(f"non-string requirement in {group!r}: {entry!r}")
        requirements[_package_name(entry)] = entry
    return requirements


def test_ts_group_subset_of_dev_group() -> None:
    """Every ``ts`` requirement appears in ``dev`` with an identical string."""
    dev = _load_group("dev")
    ts = _load_group("ts")
    differences: list[str] = []
    for name, requirement in ts.items():
        if name not in dev:
            differences.append(f"{name}: missing from dev (ts has {requirement!r})")
        elif dev[name] != requirement:
            differences.append(f"{name}: dev {dev[name]!r} != ts {requirement!r}")
    assert not differences, (
        "the dev and ts dependency groups drifted apart: "
        f"{'; '.join(differences)}. Keep the tree-sitter entries in sync."
    )


def test_dev_group_keeps_pyright_gate_dependencies() -> None:
    """pyright, pytest and pytest-cov stay in the dev group.

    The CI merge gate (zero pyright diagnostics, pytest suite) installs
    through ``.[dev]``; a future dependency-group refactor must not drop
    these silently.
    """
    dev = _load_group("dev")
    for gate in ("pyright", "pytest", "pytest-cov"):
        assert gate in dev, (
            f"{gate!r} is missing from the dev group; the CI merge gate "
            "installs its tooling through .[dev]."
        )
