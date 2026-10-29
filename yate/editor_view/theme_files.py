"""Loading of custom user theme files (``*.py``) into the theme registry.

A theme file is user-authored Python executed by design: it gets a tiny
namespace injected (:func:`_theme_namespace`) and may call
:func:`yate.editor_view.themes.register_theme` any number of times.  A broken
theme file never raises -- :func:`load_theme_file` returns a human-readable
problem string and :func:`load_theme_paths` collects those into an error list.

Split from :mod:`yate.editor_view.theme` (big-module-split wave d); import
direction is one-way: this module depends on
:mod:`yate.editor_view.themes`, :mod:`yate.paths` and
:mod:`yate.services.trust` (the last an L0 down edge for the
workspace-theme trust gate).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yate.editor_view.themes import Theme, register_theme
from yate.paths import yate_home
from yate.services.trust import is_trusted

__all__ = [
    # ``_theme_namespace`` is private by naming convention but re-exported by
    # ``theme`` for the existing test surface (test_theme_palettes execs the
    # shipped templates under exactly this namespace); listing it here marks
    # it as exported so the re-export stays pyright-clean (wave-a precedent).
    "_theme_namespace",
    "default_theme_dirs",
    "load_theme_file",
    "load_theme_paths",
]

#: Files already exec'd this process; a theme file reached through several
#: sources (rc dir, default dir, --theme-dir) must run once to avoid
#: re-registering the same themes repeatedly.
_loaded_theme_files: set[Path] = set()


def _theme_namespace() -> dict[str, Any]:
    """Globals injected into an external theme file.

    ``Any`` is deliberate: the dict is the ``globals()`` mapping of a
    ``compile()``/``exec()`` run over untyped user code, so its values
    cannot be narrowed statically.
    """
    return {
        "__name__": "__yatetheme__",
        "Theme": Theme,
        "register_theme": register_theme,
    }


def default_theme_dirs(errors: list[str]) -> list[Path]:
    """Resolve the built-in theme directories, gating workspace themes on trust.

    The user-level ``~/.yate/themes`` is the user's own data and loads
    unconditionally.  ``./themes`` inside the opened workspace executes
    workspace-authored Python, so it auto-loads only in workspaces trusted
    via :command:`:trust` -- theme directories are resolved once at
    startup, so a fresh ``:trust`` takes effect on the next start
    (mirroring the ``./extensions`` gate in
    :mod:`yate.services.extensions.loader`).  A skipped workspace directory
    appends a ``"themes: skipped untrusted ..."`` note to *errors*, the
    same user-visible channel as rc discovery notes.
    """
    theme_dirs: list[Path] = []
    cwd = Path.cwd().resolve()
    cwd_themes = cwd / "themes"
    if cwd_themes.is_dir():
        if is_trusted(cwd):
            theme_dirs.append(cwd_themes)
        else:
            errors.append(
                f"themes: skipped untrusted {cwd_themes} "
                "(trust it and restart yate to load them)"
            )
    theme_dirs.append(yate_home() / "themes")
    return theme_dirs


def load_theme_file(path: Path | str) -> str | None:
    """Exec one ``*.py`` theme file.

    The file may call :func:`register_theme` any number of times; regular
    ``import`` statements work as usual.  Returns ``None`` on success or a
    human-readable error string; a broken theme file never raises.
    """
    path = Path(path)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    if resolved in _loaded_theme_files:
        return None
    # Record the file as loaded before exec: a broken file must report its
    # error once, not on every later reload attempt (plan-b m-13).
    _loaded_theme_files.add(resolved)
    try:
        source = path.read_text(encoding="utf-8")
        code = compile(source, str(path), "exec")
        # Theme files are user-authored Python executed by design.
        exec(code, _theme_namespace())  # noqa: S102 - intentional theme exec
    except Exception as exc:  # noqa: BLE001 - theme errors must not crash yate
        return f"{type(exc).__name__}: {exc}"
    return None


def load_theme_paths(
    paths: list[Path] | list[str] | Sequence[Path] | Sequence[str],
    errors: list[str],
) -> None:
    """Load custom themes from the given files and/or directories.

    Each entry is either a directory (every non-underscore ``*.py`` inside
    is loaded in name order) or a single ``*.py`` theme file.  Missing
    paths are skipped silently (they are usually optional default
    locations); broken files record a ``"<path>: <problem>"`` error
    instead of raising.  Later files override earlier ones when they
    register a theme of the same name.
    """
    for raw in paths:
        folder = Path(raw)
        if folder.is_dir():
            for path in sorted(folder.glob("*.py")):
                if path.name.startswith("_"):
                    continue
                problem = load_theme_file(path)
                if problem is not None:
                    errors.append(f"{path}: {problem}")
        elif folder.is_file():
            problem = load_theme_file(folder)
            if problem is not None:
                errors.append(f"{folder}: {problem}")
