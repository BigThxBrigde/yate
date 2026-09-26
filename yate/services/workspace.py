"""Workspace / file system browsing for the explorer."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

# Directories that are always hidden regardless of user settings.
IGNORED_NAMES = {
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
IGNORE_FILENAMES = (".gitignore", ".yateignore")

TEXT_SUFFIXES = {
    ".txt", ".md", ".rst", ".py", ".pyw", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
    ".html", ".htm", ".css", ".scss", ".less", ".csv", ".tsv", ".sh",
    ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".sql", ".c", ".h", ".cpp",
    ".hpp", ".cc", ".cs", ".java", ".go", ".rs", ".rb", ".php", ".swift",
    ".kt", ".kts", ".lua", ".pl", ".vim", ".dockerfile", ".makefile",
    ".gitignore", ".env", ".lock", ".log", ".tex", ".org",
}


@dataclass
class Entry:
    """One file or directory shown in the explorer."""

    path: Path
    name: str
    is_dir: bool

    @property
    def hidden(self) -> bool:
        return self.name.startswith(".")


@dataclass
class _IgnorePattern:
    """One parsed line from an ignore file."""

    pattern: str  # fnmatch pattern (already lowercased for matching)
    negated: bool  # ``!`` prefix: re-include even if an earlier line ignored
    dir_only: bool  # trailing ``/``: only match directories


class Workspace:
    """A rooted directory tree, plus helpers for opening paths."""

    def __init__(self, root: Path | None = None) -> None:
        self.root: Path | None = root.resolve() if root is not None else None
        #: When ``False`` dotfiles are hidden (the default). Toggled by
        #: the user at runtime via ``:set show_hidden=on`` or the ``H``
        #: key in the explorer.
        self.show_hidden: bool = False
        #: Patterns loaded from ``.gitignore`` / ``.yateignore`` at the
        #: workspace root; reloaded when the root changes.
        self._root_ignores: list[_IgnorePattern] = []
        if self.root is not None:
            self._load_root_ignores()

    # ----------------------------------------------------------------- setup

    def set_root(self, path: Path) -> None:
        self.root = path.resolve()
        self._load_root_ignores()

    def open_target(self, target: Path) -> str:
        """Resolve a startup target.

        Returns ``"dir"`` (root set to the directory) or ``"file"`` (root set
        to the file's parent directory).
        """
        p = target.resolve()
        if p.is_dir():
            self.root = p
            self._load_root_ignores()
            return "dir"
        self.root = p.parent
        self._load_root_ignores()
        return "file"

    # --------------------------------------------------------- ignore loading

    def _load_root_ignores(self) -> None:
        """Read ``.gitignore`` / ``.yateignore`` from the workspace root."""
        self._root_ignores = []
        if self.root is None:
            return
        for name in IGNORE_FILENAMES:
            ignore_file = self.root / name
            try:
                text = ignore_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            self._root_ignores.extend(self._parse_ignore(text))

    @staticmethod
    def _parse_ignore(text: str) -> list[_IgnorePattern]:
        """Parse gitignore-style lines into patterns.

        Supported syntax:
        * ``#`` comment and blank lines — skipped
        * ``!pattern`` — negation (re-include)
        * ``pattern/`` — directory only
        * ``pattern`` — match basename via ``fnmatch``
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
            patterns.append(
                _IgnorePattern(line.lower(), negated, dir_only)
            )
        return patterns

    def _dir_ignores(self, directory: Path) -> list[_IgnorePattern]:
        """Load ignore patterns from a specific directory (directory-level)."""
        patterns: list[_IgnorePattern] = []
        for name in IGNORE_FILENAMES:
            ignore_file = directory / name
            try:
                text = ignore_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            patterns.extend(self._parse_ignore(text))
        return patterns

    def _is_ignored(
        self,
        name: str,
        is_dir: bool,
        dir_ignores: list[_IgnorePattern] | None = None,
    ) -> bool:
        """Check ignore patterns (root + directory-level) for one entry.

        Later patterns win (last match decides), mirroring ``.gitignore``
        semantics.
        """
        lower = name.lower()
        ignored = False
        for pat in self._root_ignores:
            if pat.dir_only and not is_dir:
                continue
            if fnmatch.fnmatch(lower, pat.pattern):
                ignored = not pat.negated
        if dir_ignores is not None:
            for pat in dir_ignores:
                if pat.dir_only and not is_dir:
                    continue
                if fnmatch.fnmatch(lower, pat.pattern):
                    ignored = not pat.negated
        return ignored

    # ------------------------------------------------------------- listing

    def list_dir(self, path: Path) -> list[Entry]:
        """List *path*, directories first, respecting ignore rules.

        ``IGNORED_NAMES`` are always hidden.  Dotfiles are hidden unless
        ``show_hidden`` is set.  ``.gitignore`` / ``.yateignore`` patterns
        (root + per-directory) are applied on top.
        """
        dir_ignores = self._dir_ignores(path)
        entries: list[Entry] = []
        try:
            children = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (PermissionError, OSError):
            return entries
        for child in children:
            name = child.name
            if name in IGNORED_NAMES:
                continue
            is_dir = child.is_dir()
            if not self.show_hidden and name.startswith("."):
                continue
            if self._is_ignored(name, is_dir, dir_ignores):
                continue
            entries.append(Entry(child, name, is_dir))
        return entries

    def walk_files(self, limit: int = 5000) -> list[Path]:
        """Recursively collect files under :attr:`root` for quick open.

        Ignored directories (``.git``, ``__pycache__``, ...) are pruned
        during the walk.  Dotfiles and ``.gitignore`` / ``.yateignore``
        patterns are also applied.  Results are ordered depth-first,
        directories first per level.  Returns an empty list when no folder
        is open.

        The traversal is an explicit stack, not recursion, so pathologically
        deep trees cannot raise ``RecursionError`` (S11); symlinked
        directories are never followed -- a link pointing at an ancestor
        would otherwise expand forever.
        """
        if self.root is None:
            return []
        files: list[Path] = []

        def children(directory: Path) -> list[tuple[Path, bool]]:
            """Filtered sub-entries of *directory*, reversed for stack order.

            Applies the same filters as the recursive walk it replaces
            (``IGNORED_NAMES``, hidden files, per-directory ignore rules) and
            drops symlinked directories entirely.  Reversing the sorted,
            directories-first list lets the consumer ``pop()`` entries in the
            exact pre-order the recursive version produced.
            """
            dir_ignores = self._dir_ignores(directory)
            try:
                found = sorted(
                    directory.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except (PermissionError, OSError):
                return []
            kept: list[tuple[Path, bool]] = []
            for child in found:
                name = child.name
                if name in IGNORED_NAMES:
                    continue
                is_dir = child.is_dir()
                if not self.show_hidden and name.startswith("."):
                    continue
                if self._is_ignored(name, is_dir, dir_ignores):
                    continue
                if is_dir and child.is_symlink():
                    # Never follow symlinked directories: a link pointing at
                    # an ancestor would recurse forever.
                    continue
                kept.append((child, is_dir))
            kept.reverse()
            return kept

        # Work items are (path, is_dir): popping a directory pushes its own
        # children on top of the stack, which keeps the depth-first order.
        stack: list[tuple[Path, bool]] = children(self.root)
        while stack and len(files) < limit:
            path, is_dir = stack.pop()
            if is_dir:
                stack.extend(children(path))
            else:
                files.append(path)
        return files

    def visible_tree(self, expanded: set[Path]) -> list[tuple[int, Entry]]:
        """Flatten the tree according to the set of *expanded* directories.

        Rows come out in the same depth-first order as before, but the
        flattening is computed with an explicit stack so deep trees cannot
        raise ``RecursionError``.  Expanded symlinked directories are not
        descended into -- the same loop guard :meth:`walk_files` applies,
        since a link pointing at an ancestor would otherwise re-expand its
        own subtree forever (S11).
        """
        result: list[tuple[int, Entry]] = []
        if self.root is None:
            return result

        result.append((0, Entry(self.root, self.root.name or str(self.root), True)))
        stack: list[tuple[Entry, int]] = [
            (entry, 1) for entry in reversed(self.list_dir(self.root))
        ]
        while stack:
            entry, depth = stack.pop()
            result.append((depth, entry))
            if (
                entry.is_dir
                and entry.path in expanded
                and not entry.path.is_symlink()
            ):
                stack.extend(
                    (child, depth + 1)
                    for child in reversed(self.list_dir(entry.path))
                )
        return result

    # ------------------------------------------------------- file mutation

    @staticmethod
    def validate_name(name: str) -> str:
        """Strip and sanity-check a file/folder name from user input.

        Returns the cleaned name; raises ``ValueError`` when the name is
        empty or contains path separators (single-segment names only).
        """
        name = name.strip()
        if not name or name in (".", ".."):
            raise ValueError("empty name")
        for sep in ("/", "\\", ":"):
            if sep in name:
                raise ValueError(f"name must not contain {sep!r}")
        return name

    def create_entry(self, directory: Path, name: str, *, is_dir: bool) -> Path:
        """Create a file (or folder) inside *directory*; returns its path.

        Raises ``FileExistsError`` if the target already exists and
        ``OSError`` bubbling from the file system on failure.
        """
        target = directory / self.validate_name(name)
        if target.exists():
            raise FileExistsError(f"{target.name} already exists")
        if is_dir:
            target.mkdir(parents=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        return target

    def rename_entry(self, path: Path, name: str) -> Path:
        """Rename *path* within its own directory; returns the new path."""
        target = path.parent / self.validate_name(name)
        if target == path:
            return target
        if target.exists():
            raise FileExistsError(f"{target.name} already exists")
        return path.rename(target)

    def remove_entry(self, path: Path) -> None:
        """Delete a file, or a directory tree (with :mod:`shutil`)."""
        import shutil

        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    # ------------------------------------------------------------ file info

    @staticmethod
    def is_text_file(path: Path) -> bool:
        """Best-effort check that *path* is editable text."""
        name = path.name.lower()
        if name in ("dockerfile", "makefile", "readme", "license"):
            return True
        if path.suffix.lower() in TEXT_SUFFIXES:
            return True
        if path.suffix == "":
            # Extension-less files: sniff the first bytes.
            try:
                with path.open("rb") as fh:
                    chunk = fh.read(2048)
                chunk.decode("utf-8")
                return b"\x00" not in chunk
            except (OSError, UnicodeDecodeError):
                return False
        return False
