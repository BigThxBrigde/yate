"""Writable per-user data under ``~/.yate/data``.

Extensions persist small UTF-8 documents here through ``api.data`` (see
:class:`yate.services.extensions.bridges.DataExtensionBridge`): the bundled
game pack keeps one JSON document per game under ``games/``.  The path rules
live in this one L0 leaf module, so scripts never concatenate a home directory
themselves and every write goes through the same checks.

:mod:`yate.logs` owns the sibling ``~/.yate/data/logs`` and the crash files;
those are diagnostics rather than user data and deliberately do not route
through this module.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from yate.logs import tracing

#: Trace logger ("yate.services.data_store"); silent unless yate_trace is on.
log = tracing.get_logger(__name__)

#: Directory name under ``~/.yate`` holding writable user data.
DATA_DIRNAME: str = "data"


def data_root() -> Path:
    """Return ``~/.yate/data`` (the directory itself is not created here)."""
    return Path.home() / ".yate" / DATA_DIRNAME


def resolve(relative: str) -> Path:
    """Resolve the relative document *relative* under :func:`data_root`.

    Only clean, relative names are accepted: an empty name, an absolute path,
    a drive letter, a backslash separator or any ``..`` component raises
    :class:`ValueError`.  The drive and backslash checks are applied
    portably -- on POSIX a backslash is a legal filename character and a
    ``C:/`` prefix an ordinary relative directory, so both must be rejected
    here as well rather than accepted with a platform-dependent meaning.
    The resolved path is verified to stay inside :func:`data_root` as a
    second line of defence, so a future normalisation change cannot
    silently widen the writable area.
    """
    if not relative:
        raise ValueError("data name must be a non-empty string")
    if "\\" in relative:
        raise ValueError(f"data name must use forward slashes: {relative!r}")
    candidate = Path(relative)
    # pathlib parses a drive letter only on Windows; reject the "X:" prefix
    # portably so POSIX cannot smuggle one in as an ordinary directory name.
    # "C:foo/bar" keeps the drive inside the first part ("C:foo"), hence >= 2.
    first = candidate.parts[0] if candidate.parts else ""
    drive_prefix = len(first) >= 2 and first[1] == ":"
    if candidate.is_absolute() or candidate.drive or drive_prefix:
        raise ValueError(f"data name must be relative: {relative!r}")
    if ".." in candidate.parts:
        raise ValueError(f"data name must not contain '..': {relative!r}")
    root = data_root()
    target = root / candidate
    if not target.is_relative_to(root):
        raise ValueError(f"data name escapes {root}: {relative!r}")
    return target


def read_text(relative: str) -> str | None:
    """Return the document's text, or ``None`` when it is missing/unreadable.

    A missing file is the normal "no saved data yet" case and stays silent; an
    I/O or decoding failure is logged and reported as ``None`` so callers keep
    the same fallback path.
    """
    path = resolve(relative)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("data read failed for %s: %s", relative, exc)
        return None


def write_text(relative: str, text: str) -> None:
    """Write *text* to *relative*, atomically, creating parent directories.

    The document is written to a temporary sibling file and then moved onto
    the target with :meth:`pathlib.Path.replace`, so a crash mid-write leaves
    the previous version intact rather than a truncated JSON document.

    Windows file locks (antivirus scanners, sync clients) can make the rename
    fail with a spurious ``OSError`` even though the directory is writable.
    Saving must not lose data over that, so the fallback is a direct write of
    the target -- it gives up the atomicity guarantee but keeps the save.
    """
    path = resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        try:
            temp.replace(path)
        except OSError as exc:
            log.warning("atomic replace failed for %s, writing directly: %s", relative, exc)
            path.write_text(text, encoding="utf-8", newline="")
    finally:
        temp.unlink(missing_ok=True)


def remove(relative: str) -> bool:
    """Delete *relative*; ``True`` when a file was actually removed."""
    path = resolve(relative)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("data remove failed for %s: %s", relative, exc)
        return False
    return True


def names(relative_dir: str) -> list[str]:
    """Return the file names inside *relative_dir*, sorted (missing = ``[]``)."""
    directory = resolve(relative_dir)
    try:
        return sorted(entry.name for entry in directory.iterdir() if entry.is_file())
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError as exc:
        log.warning("data list failed for %s: %s", relative_dir, exc)
        return []
