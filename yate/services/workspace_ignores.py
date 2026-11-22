"""Workspace ignore-pattern subsystem: gitignore-style filtering state.

Extracted from :mod:`yate.services.workspace` so the explorer-facing
:class:`Workspace` class stays a thin delegation over this module.  The
module owns the ``IGNORED_NAMES`` / ``IGNORE_FILENAMES`` constants, the
pattern parser, the anchored matcher and the :class:`IgnoreIndex` state
object (root pattern list plus the mtime-keyed per-directory cache).

``yate.services.workspace`` re-exports ``IGNORED_NAMES`` for backward
compatibility (:mod:`yate.editor_components.explorer` and existing tests
import it from there) -- a limited re-export of a public constant, in
the spirit of the leaf-module re-export exception note required by the
architecture-boundaries rule.

No behaviour change relative to the former inline implementation:
last-match-wins, negation, anchored rules, comment/blank skipping and
the mtime cache identity with the wholesale reset at the cache cap are
kept identical.

``_IgnorePattern`` and ``_parse_ignore`` are package-private (consumed
only by :mod:`yate.services.workspace`, which re-exports
``IGNORED_NAMES`` and keeps its historical method seams); they are
listed in ``__all__`` so those imports read as deliberate re-exports
to pyright (the ``editor_lsp.parsing`` precedent), not as
``reportPrivateUsage`` violations.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

# Directories that are always hidden regardless of user settings.
IGNORED_NAMES: set[str] = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

#: Files whose contents are read as ignore-pattern sources.
IGNORE_FILENAMES: tuple[str, ...] = (".gitignore", ".yateignore")

#: Cap on the per-directory ignore-pattern cache (deep trees list many
#: directories; the wholesale reset keeps the memory bounded).
_DIR_IGNORE_CACHE_MAX: int = 256

__all__ = [
    "IGNORED_NAMES",
    "IGNORE_FILENAMES",
    "_IgnorePattern",
    "_parse_ignore",
    "IgnoreIndex",
]


@dataclass
class _IgnorePattern:
    """One parsed line from an ignore file."""

    pattern: str  # fnmatch pattern (already lowercased for matching)
    negated: bool  # ``!`` prefix: re-include even if an earlier line ignored
    dir_only: bool  # trailing ``/``: only match directories
    #: A ``/`` at the start or middle (git anchoring): match the entry's
    #: path relative to the ignore file's own directory, not its basename.
    anchored: bool


def _parse_ignore(text: str) -> list[_IgnorePattern]:
    """Parse gitignore-style lines into patterns.

    Supported syntax:
    * ``#`` comment and blank lines -- skipped
    * ``!pattern`` -- negation (re-include)
    * ``pattern/`` -- directory only
    * ``pattern`` -- match the basename via ``fnmatch`` at any depth
    * ``a/b/pattern`` or ``/pattern`` -- path-anchored: matched against
      the entry's path relative to the ignore file's own directory
      (a leading ``/`` just pins the pattern to that directory and is
      stripped)
    """
    patterns: list[_IgnorePattern] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        dir_only = line.endswith("/")
        if dir_only:
            line = line[:-1]
        line = line.strip()
        if not line:
            continue
        # A leading "/" anchors too, so detect before stripping it.
        anchored = "/" in line
        if line.startswith("/"):
            line = line.lstrip("/")
            if not line:
                continue
        patterns.append(
            _IgnorePattern(line.lower(), negated, dir_only, anchored)
        )
    return patterns


def _anchored_match(rel: str, pattern: str) -> bool:
    """Match an anchored pattern against a root-relative posix path.

    ``fnmatch`` translates ``*`` into "any run of characters", which would
    let it cross ``/``; git keeps ``*`` inside one path segment.  While the
    pattern holds no ``**``, requiring equal segment counts first restores
    that per-segment behaviour cheaply (``pack/*.spec`` then still matches
    ``pack/x.spec`` but no longer ``pack/sub/x.spec``).  Patterns with
    ``**`` fall back to plain ``fnmatch`` (crossing allowed), which is the
    documented approximation for multi-directory globs.
    """
    if "**" not in pattern and rel.count("/") != pattern.count("/"):
        return False
    return fnmatch.fnmatch(rel, pattern)


class IgnoreIndex:
    """Ignore state for one workspace root, plus the per-directory cache.

    Holds the root-level pattern list, the anchored fast-path flag and
    the mtime-keyed per-directory pattern cache.  ``Workspace`` keeps
    its method names and delegates here, so cache identity and eviction
    behave exactly as before the extraction.
    """

    def __init__(self) -> None:
        #: Root the pattern lists were loaded from (``None`` = no root);
        #: used to resolve anchored patterns against root-relative paths.
        self._root: Path | None = None
        #: Patterns loaded from ``.gitignore`` / ``.yateignore`` at the
        #: workspace root; reloaded when the root changes.
        self.root_ignores: list[_IgnorePattern] = []
        #: ``True`` when any root pattern is anchored; cached so the
        #: per-entry check in :meth:`ignored` stays O(1): rescanning the
        #: pattern list for every walked entry would multiply over long
        #: directory traversals.
        self.root_has_anchored: bool = False
        #: Per-directory ignore-pattern cache keyed on the ignore files'
        #: own mtimes: re-listing a directory (every explorer refresh and
        #: quick-open walk) must not re-read and re-parse the files, but an
        #: edited ``.gitignore`` must take effect.
        self.dir_ignore_cache: dict[
            tuple[Path, tuple[float, ...]], list[_IgnorePattern]
        ] = {}

    def set_root(self, root: Path | None) -> None:
        """(Re)load the ignore files of *root*; ``None`` clears them."""
        self._root = root
        self.root_ignores = []
        if root is None:
            self.root_has_anchored = False
            return
        for name in IGNORE_FILENAMES:
            ignore_file = root / name
            try:
                text = ignore_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            self.root_ignores.extend(_parse_ignore(text))
        self.root_has_anchored = any(
            pat.anchored for pat in self.root_ignores
        )

    def dir_ignores(self, directory: Path) -> list[_IgnorePattern]:
        """Load ignore patterns from a specific directory (directory-level).

        Cached on the ignore files' own mtimes (see ``dir_ignore_cache``);
        the cache is bounded and reset wholesale when the cap is hit.
        """
        stamps: list[float] = []
        for name in IGNORE_FILENAMES:
            try:
                stamps.append((directory / name).stat().st_mtime)
            except OSError:
                stamps.append(-1.0)
        key = (directory, tuple(stamps))
        cached = self.dir_ignore_cache.get(key)
        if cached is not None:
            return cached
        patterns: list[_IgnorePattern] = []
        for name in IGNORE_FILENAMES:
            ignore_file = directory / name
            try:
                text = ignore_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            patterns.extend(_parse_ignore(text))
        if len(self.dir_ignore_cache) >= _DIR_IGNORE_CACHE_MAX:
            self.dir_ignore_cache.clear()
        self.dir_ignore_cache[key] = patterns
        return patterns

    def ignored(
        self,
        path: Path,
        is_dir: bool,
        dir_ignores: list[_IgnorePattern] | None = None,
    ) -> bool:
        """Check ignore patterns (root + directory-level) for one entry.

        Basename patterns match the entry name at any depth; anchored
        patterns (a ``/`` at the start or middle) match the entry's path
        relative to the ignore file's own directory -- the workspace root
        for root files.  Per-directory patterns only ever see the direct
        children of their own directory, whose relative path is the bare
        name, so they match on the name either way.  Later patterns win
        (last match decides), mirroring ``.gitignore`` semantics.
        """
        lower = path.name.lower()
        # Anchored root rules need the root-relative path; compute it lazily
        # so pattern-free workspaces (e.g. the synthetic 1500-level chain
        # tests) never pay the O(depth) relative_to per entry.
        rel: str | None = None
        if self._root is not None and self.root_has_anchored:
            try:
                rel = path.relative_to(self._root).as_posix().lower()
            except ValueError:
                # Listed outside the workspace root (the file manager can
                # browse any tree): anchored root rules cannot apply, while
                # basename rules keep their previous behaviour.
                rel = None
        ignored = False
        for pat in self.root_ignores:
            if pat.dir_only and not is_dir:
                continue
            if pat.anchored:
                if rel is not None and _anchored_match(rel, pat.pattern):
                    ignored = not pat.negated
            elif fnmatch.fnmatch(lower, pat.pattern):
                ignored = not pat.negated
        if dir_ignores is not None:
            for pat in dir_ignores:
                if pat.dir_only and not is_dir:
                    continue
                if fnmatch.fnmatch(lower, pat.pattern):
                    ignored = not pat.negated
        return ignored
