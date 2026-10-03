"""Shared helpers for the development-time tool packages.

The repository-root lookup used to be re-derived in six places as
``Path(__file__).resolve().parents[2]`` (changelog, release, pack, wiki and
smoke_test baselines); this module is the single point for it.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["repo_root"]


def repo_root() -> Path:
    """The yate repository root (the parent directory of ``tools/``)."""
    return Path(__file__).resolve().parents[1]
