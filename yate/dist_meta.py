"""Requires-Dist parsing for yate's own dist metadata, shared by two sides.

``importlib.metadata.requires("yate")`` returns the raw Requires-Dist
headers hatchling bakes from ``pyproject.toml`` at build time.
:func:`requirement_groups` turns them into ``{extra: {canonical: display}}``
groups.  Two consumers share this module so the parsing rules live in
exactly one place: :mod:`yate.diagnostics` builds the ``[packages]``
report section from it at runtime, and the PyInstaller specs under
``pack/`` derive the core-dependency dist-info list from it at build
time.  Stdlib-only on purpose (``re`` + ``importlib.metadata``): the
specs import it before any editor / textual machinery exists.
"""

from __future__ import annotations

import re
from importlib import metadata as importlib_metadata

#: Distribution name at the start of a Requires-Dist string.
_REQ_DIST_RE: re.Pattern[str] = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

#: Extra group inside a requirement marker (``; extra == 'ts'``).
_REQ_EXTRA_RE: re.Pattern[str] = re.compile(r"\bextra\s*==\s*['\"]([^'\"]+)['\"]")


def requirement_groups() -> dict[str, dict[str, str]]:
    """Parse ``requires("yate")`` into ``{extra: {canonical: display}}``.

    Requirements without an extra marker land in the ``core`` group; when
    the yate distribution is missing (``requires()`` returning ``None``)
    the result is ``{}``.  Entries without a leading distribution name are
    skipped -- hatchling output is always valid, so this is purely
    defensive.  Keys are PEP 503-canonical names, values keep the declared
    display spelling.
    """
    raw = importlib_metadata.requires("yate")
    if raw is None:
        return {}
    groups: dict[str, dict[str, str]] = {}
    for req in raw:
        name_match = _REQ_DIST_RE.match(req)
        if name_match is None:
            continue  # malformed entry -- hatchling output is always valid
        name = name_match.group(1)
        marker = _REQ_EXTRA_RE.search(req)
        group = marker.group(1) if marker else "core"
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        groups.setdefault(group, {})[canonical] = name
    return groups
