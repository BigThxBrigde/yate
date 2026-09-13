"""One-time user-directory setup and cleanup (``~/.yate/``).

Two operations back the matching CLI flags; both touch only the user
configuration directory and never launch the TUI:

* :func:`setup_defaults` -- create ``~/.yate/``, install a copy of the
  bundled ``yaterc.example`` as the initial ``yaterc``, and refresh the
  bundled theme/extension ``*.example`` templates under ``themes/`` and
  ``extensions/``. Templates keep the ``.example`` suffix, so the existing
  ``*.py``-only startup scans ignore them until a user renames one -- no
  loader code is involved;
* :func:`cleanup_defaults` -- remove the managed configuration (``yaterc``,
  ``themes/``, ``extensions/``). The runtime ``data/`` directory (crash
  diagnostics) is preserved unless ``include_data`` is requested, and files
  yate did not create are left untouched.

Everything is idempotent and takes an explicit *base_dir* so callers/tests
never have to monkeypatch :func:`pathlib.Path.home`.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from yate.paths import bundled_extensions_dir, package_root

#: Name of the user configuration directory (relative to the home dir).
USER_DIRNAME = ".yate"
RC_FILENAME = "yaterc"
RC_TEMPLATE = "yaterc.example"
RC_BACKUP = "yaterc.yate-bak"
DATA_DIRNAME = "data"
MANAGED_DIRS = ("themes", "extensions")

#: Theme templates shipped as package resources (extension templates are
#: discovered dynamically via the bundled extensions dir's ``*.py.example``
#: glob, so real built-in ``*.py`` extensions can never be selected).
_THEME_EXAMPLES_DIR = ("resources", "theme_examples")
_THEME_TEMPLATES = (
    "dracula_theme.example",
    "ayu_theme.example",
)


# ----------------------------------------------------------------- reports


@dataclass(frozen=True)
class SetupReport:
    """Outcome of :func:`setup_defaults` (paths relative to ``base_dir``)."""

    base_dir: Path
    created_dirs: list[str] = field(default_factory=list[str])
    installed_rc: bool = False
    rc_skipped: bool = False
    rc_backup: Path | None = None
    refreshed_templates: list[str] = field(default_factory=list[str])
    skipped_templates: list[str] = field(default_factory=list[str])
    errors: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class CleanupReport:
    """Outcome of :func:`cleanup_defaults` (paths relative to ``base_dir``)."""

    base_dir: Path
    removed_files: list[str] = field(default_factory=list[str])
    removed_dirs: list[str] = field(default_factory=list[str])
    preserved: list[str] = field(default_factory=list[str])
    base_removed: bool = False
    cancelled: bool = False
    nothing_to_remove: bool = False
    errors: list[str] = field(default_factory=list[str])


class ConfirmationRequiredError(RuntimeError):
    """Raised when cleanup needs confirmation but has no interactive stdin."""


# ------------------------------------------------------------- source maps


def default_base_dir() -> Path:
    """The user configuration root (``~/.yate``)."""
    return Path.home() / USER_DIRNAME


def _template_sources() -> list[tuple[Path, str]]:
    """Pairs of (bundled source path, destination path relative to base)."""
    examples = package_root().joinpath(*_THEME_EXAMPLES_DIR)
    pairs: list[tuple[Path, str]] = [
        (
            examples / filename,
            f"{MANAGED_DIRS[0]}/{filename}",
        )
        for filename in _THEME_TEMPLATES
    ]
    ext_dir = bundled_extensions_dir()
    if ext_dir.is_dir():
        for source in sorted(ext_dir.glob("*.py.example")):
            pairs.append((source, f"{MANAGED_DIRS[1]}/{source.name}"))
    return pairs


# ------------------------------------------------------------------- setup


def setup_defaults(
    *,
    force: bool = False,
    base_dir: Path | None = None,
) -> SetupReport:
    """Create the user directory and install/refresh the default files.

    * ``yaterc`` is installed from the bundled ``yaterc.example``. An
      existing file is left alone unless *force*; with *force* the old file
      is copied to ``yaterc.yate-bak`` first (an existing backup is kept, so
      the earliest version always survives);
    * every bundled ``*.example`` template is refreshed unconditionally --
      yate owns these files, and customizations belong in a renamed ``*.py``
      copy;
    * missing template sources (incomplete install) are reported in
      ``skipped_templates``; per-file :class:`OSError` failures are collected
      in ``errors`` while the remaining files still install.
    """
    base = base_dir if base_dir is not None else default_base_dir()
    created_dirs: list[str] = []
    refreshed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for dirname in MANAGED_DIRS:
        target_dir = base / dirname
        try:
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                created_dirs.append(dirname)
        except OSError as exc:
            errors.append(f"{dirname}/: {exc}")

    installed_rc, rc_skipped, rc_backup = _install_rc(
        base, force=force, errors=errors
    )

    for source, rel_path in _template_sources():
        target = base / rel_path
        try:
            if not source.is_file():
                skipped.append(rel_path)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            refreshed.append(rel_path)
        except OSError as exc:
            errors.append(f"{rel_path}: {exc}")

    return SetupReport(
        base_dir=base,
        created_dirs=created_dirs,
        installed_rc=installed_rc,
        rc_skipped=rc_skipped,
        rc_backup=rc_backup,
        refreshed_templates=refreshed,
        skipped_templates=skipped,
        errors=errors,
    )


def _install_rc(
    base: Path, *, force: bool, errors: list[str]
) -> tuple[bool, bool, Path | None]:
    """Install/skip/force-replace the yaterc copy.

    Returns ``(installed, skipped, backup)``; IO problems go into *errors*
    and leave the flags at their defaults.
    """
    source = package_root() / RC_TEMPLATE
    target = base / RC_FILENAME
    backup: Path | None = None
    try:
        if target.exists():
            if not force:
                return False, True, None
            backup_path = base / RC_BACKUP
            if not backup_path.exists():
                shutil.copyfile(target, backup_path)
            backup = backup_path
        if not source.is_file():
            errors.append(f"{RC_FILENAME}: bundled {RC_TEMPLATE} missing")
            return False, False, backup
        shutil.copyfile(source, target)
        return True, False, backup
    except OSError as exc:
        errors.append(f"{RC_FILENAME}: {exc}")
        return False, False, backup


# ---------------------------------------------------------------- cleanup


def cleanup_defaults(
    *,
    force: bool = False,
    include_data: bool = False,
    base_dir: Path | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> CleanupReport:
    """Remove yate-managed configuration under the user directory.

    Deletes ``yaterc`` plus ``themes/`` and ``extensions/`` (including any
    user-renamed ``*.py`` files -- that is the point of "clear
    configuration"). ``data/`` is preserved unless *include_data* is set;
    unknown entries are never deleted. When the directory ends up empty the
    ``~/.yate`` directory itself is removed.

    Without *force* the plan must be confirmed on an interactive terminal;
    a non-interactive stdin raises :class:`ConfirmationRequiredError` so the
    CLI can exit distinctively. Deletions only happen after confirmation.
    """
    base = base_dir if base_dir is not None else default_base_dir()
    stream_in = stdin if stdin is not None else sys.stdin
    stream_out = stdout if stdout is not None else sys.stdout

    if not base.exists():
        return CleanupReport(base_dir=base)

    remove_files, remove_dirs, preserved, nothing = _cleanup_plan(
        base, include_data=include_data
    )
    if nothing:
        return CleanupReport(base_dir=base, preserved=preserved,
                             nothing_to_remove=True)

    if not force:
        if not _interactive(stream_in, stream_out):
            raise ConfirmationRequiredError(
                "refusing to remove configuration without a TTY; re-run with "
                "--force for non-interactive use"
            )
        _print_confirmation_prompt(
            stream_out, base, remove_files, remove_dirs, preserved,
            include_data=include_data,
        )
        answer = stream_in.readline().strip().lower()
        if answer not in ("y", "yes"):
            return CleanupReport(base_dir=base, preserved=preserved,
                                 cancelled=True)

    removed_files: list[str] = []
    removed_dirs: list[str] = []
    errors: list[str] = []
    for path in remove_files:
        try:
            path.unlink()
            removed_files.append(path.name)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
    for path in remove_dirs:
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed_dirs.append(path.name)
        except OSError as exc:
            errors.append(f"{path.name}/: {exc}")

    base_removed = False
    if not any(base.iterdir()):
        try:
            base.rmdir()
            base_removed = True
        except OSError:
            pass
    return CleanupReport(
        base_dir=base,
        removed_files=removed_files,
        removed_dirs=removed_dirs,
        preserved=preserved,
        base_removed=base_removed,
        errors=errors,
    )


def _cleanup_plan(
    base: Path, *, include_data: bool
) -> tuple[list[Path], list[Path], list[str], bool]:
    """Collect deletion targets and preserved entry names."""
    remove_files: list[Path] = []
    remove_dirs: list[Path] = []
    preserved: list[str] = []

    rc_path = base / RC_FILENAME
    if rc_path.exists():
        remove_files.append(rc_path)
    for dirname in MANAGED_DIRS:
        path = base / dirname
        if path.exists():
            remove_dirs.append(path)
    data_path = base / DATA_DIRNAME
    if data_path.exists():
        if include_data:
            remove_dirs.append(data_path)
        else:
            preserved.append(DATA_DIRNAME)

    managed = {RC_FILENAME, *MANAGED_DIRS, DATA_DIRNAME}
    try:
        entries = sorted(base.iterdir(), key=lambda p: p.name)
    except OSError:
        entries = []
    for entry in entries:
        if entry.name not in managed:
            preserved.append(entry.name)

    nothing = not remove_files and not remove_dirs
    return remove_files, remove_dirs, preserved, nothing


def _interactive(stream_in: TextIO, stream_out: TextIO) -> bool:
    try:
        return bool(stream_in.isatty() and stream_out.isatty())
    except (AttributeError, OSError):
        return False


def _file_count(directory: Path) -> int:
    try:
        return sum(1 for entry in directory.rglob("*") if entry.is_file())
    except OSError:
        return 0


def _print_confirmation_prompt(
    stream_out: TextIO,
    base: Path,
    remove_files: list[Path],
    remove_dirs: list[Path],
    preserved: list[str],
    *,
    include_data: bool,
) -> None:
    lines = [f"about to remove configuration under {base}:"]
    for path in remove_files:
        lines.append(f"  {path.name}")
    for path in remove_dirs:
        if path.is_dir():
            count = _file_count(path)
            lines.append(
                f"  {path.name}/  ({count} file{'s' if count != 1 else ''})"
            )
        else:  # a symlink/other entry occupying the managed name
            lines.append(f"  {path.name}")
    if preserved:
        lines.append("preserved:")
        for name in preserved:
            if name == DATA_DIRNAME:
                note = "crash logs; --include-data to remove"
            else:
                note = "unknown, not created by yate"
            lines.append(f"  {name}/  ({note})" if name == DATA_DIRNAME
                         else f"  {name}  ({note})")
    elif not include_data:
        lines.append("(data/ kept unless --include-data)")
    lines.append("proceed? [y/N]: ")
    stream_out.write("\n".join(lines))
    stream_out.flush()


# -------------------------------------------------------------- rendering


def format_setup_report(report: SetupReport) -> str:
    """Human-readable summary printed by ``yate --setup-defaults``."""
    lines = [f"yate user directory: {report.base_dir}"]
    for dirname in report.created_dirs:
        lines.append(f"  created     {dirname}/")
    if report.installed_rc:
        action = "replaced" if report.rc_backup is not None else "installed"
        lines.append(f"  {action:<11} {RC_FILENAME}  (from {RC_TEMPLATE})")
    if report.rc_skipped:
        lines.append(
            "  skipped     yaterc already exists "
            "(--force replaces it, keeping a .yate-bak backup)"
        )
    if report.rc_backup is not None:
        lines.append(f"  backed up   {RC_BACKUP}")
    for rel_path in report.refreshed_templates:
        lines.append(f"  refreshed   {rel_path}")
    for rel_path in report.skipped_templates:
        lines.append(f"  skipped     {rel_path}  (bundled source missing)")
    for error in report.errors:
        lines.append(f"  error       {error}")
    if not report.errors:
        lines.append("")
        lines.append(
            "edit yaterc to customize; rename a *.example to *.py to "
            "activate it (themes/ or extensions/)."
        )
    return "\n".join(lines)


def format_cleanup_report(report: CleanupReport) -> str:
    """Human-readable summary printed by ``yate --cleanup-defaults``."""
    if report.cancelled:
        return "cancelled; nothing was removed."

    lines: list[str] = []
    if report.nothing_to_remove:
        lines.append(f"no yate-managed configuration found under {report.base_dir}")
    elif report.removed_files or report.removed_dirs:
        lines.append("removed:")
        for name in report.removed_files:
            lines.append(f"  {name}")
        for name in report.removed_dirs:
            lines.append(f"  {name}/")
    for name in report.preserved:
        if name == DATA_DIRNAME:
            lines.append("data/ preserved (crash diagnostics).")
        else:
            lines.append(f"{name} preserved (not created by yate).")
    if report.base_removed:
        lines.append(f"the now-empty {report.base_dir} directory was removed.")
    if not report.nothing_to_remove:
        lines.append("data/ is recreated automatically on the next launch.")
    for error in report.errors:
        lines.append(f"error: {error}")
    return "\n".join(lines)
