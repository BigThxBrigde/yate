"""Workspace / file system browsing for the explorer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Directories that are never worth showing in the tree.
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


class Workspace:
    """A rooted directory tree, plus helpers for opening paths."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root: Optional[Path] = root.resolve() if root is not None else None

    # ----------------------------------------------------------------- setup

    def set_root(self, path: Path) -> None:
        self.root = path.resolve()

    def open_target(self, target: Path) -> str:
        """Resolve a startup target.

        Returns ``"dir"`` (root set to the directory) or ``"file"`` (root set
        to the file's parent directory).
        """
        p = target.resolve()
        if p.is_dir():
            self.root = p
            return "dir"
        self.root = p.parent
        return "file"

    # ------------------------------------------------------------- listing

    def list_dir(self, path: Path) -> list[Entry]:
        """List *path*, directories first, ignoring noise / hidden opt-out."""
        entries: list[Entry] = []
        try:
            children = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (PermissionError, OSError):
            return entries
        for child in children:
            if child.name in IGNORED_NAMES:
                continue
            entries.append(Entry(child, child.name, child.is_dir()))
        return entries

    def walk_files(self, limit: int = 5000) -> list[Path]:
        """Recursively collect files under :attr:`root` for quick open.

        Ignored directories (``.git``, ``__pycache__``, ...) are pruned
        during the walk.  Results are sorted by path, directories first
        per level.  Returns an empty list when no folder is open.
        """
        if self.root is None:
            return []
        files: list[Path] = []

        def walk(directory: Path) -> None:
            if len(files) >= limit:
                return
            try:
                children = sorted(
                    directory.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except (PermissionError, OSError):
                return
            for child in children:
                if len(files) >= limit:
                    return
                if child.is_dir():
                    if child.name in IGNORED_NAMES:
                        continue
                    walk(child)
                else:
                    files.append(child)

        walk(self.root)
        return files

    def visible_tree(self, expanded: set[Path]) -> list[tuple[int, Entry]]:
        """Flatten the tree according to the set of *expanded* directories."""
        result: list[tuple[int, Entry]] = []
        if self.root is None:
            return result

        def walk(directory: Path, depth: int) -> None:
            for entry in self.list_dir(directory):
                result.append((depth, entry))
                if entry.is_dir and entry.path in expanded:
                    walk(entry.path, depth + 1)

        result.append((0, Entry(self.root, self.root.name or str(self.root), True)))
        for entry in self.list_dir(self.root):
            result.append((1, entry))
            if entry.is_dir and entry.path in expanded:
                walk(entry.path, 2)
        return result

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
