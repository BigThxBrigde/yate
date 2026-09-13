"""Chinese translation overrides stored in ``tools/changelog/zh_overrides.json``.

The file is human-maintained through ``python -m tools.changelog zh-commit``
so the generated changelogs stay hands-off.  Keys are 7-char short hashes;
the JSON is written with sorted keys, UTF-8, ``ensure_ascii=False`` and
indent 2 so diffs stay stable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

DEFAULT_OVERRIDES_PATH: Final[Path] = Path(__file__).resolve().with_name(
    "zh_overrides.json"
)


@dataclass(frozen=True)
class OverrideEntry:
    """A human Chinese summary (and optional detail) for one commit."""

    summary: str
    detail: str | None = None


def load_overrides(
    path: Path = DEFAULT_OVERRIDES_PATH,
) -> dict[str, OverrideEntry]:
    """Load the override table; a missing file yields an empty map."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    data = cast("dict[str, dict[str, str]]", json.loads(text))
    overrides: dict[str, OverrideEntry] = {}
    for short_sha, payload in data.items():
        overrides[short_sha] = OverrideEntry(
            summary=str(payload.get("summary", "")),
            detail=payload.get("detail"),
        )
    return overrides


def save_overrides(
    overrides: Mapping[str, OverrideEntry],
    path: Path = DEFAULT_OVERRIDES_PATH,
) -> None:
    """Write the override table in a diff-stable layout."""
    payload: dict[str, dict[str, str]] = {}
    for short_sha, entry in sorted(overrides.items()):
        item = {"summary": entry.summary}
        if entry.detail is not None:
            item["detail"] = entry.detail
        payload[short_sha] = item
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def upsert_override(
    overrides: dict[str, OverrideEntry],
    short_sha: str,
    summary: str,
    detail: str | None = None,
) -> bool:
    """Insert or replace one entry in place; ``True`` when the map changed."""
    summary = summary.strip()
    detail = detail.strip() if detail else None
    existing = overrides.get(short_sha)
    if (
        existing is not None
        and existing.summary == summary
        and existing.detail == detail
    ):
        return False
    overrides[short_sha] = OverrideEntry(summary=summary, detail=detail)
    return True
