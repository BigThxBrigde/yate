"""Build the Windows executable icon from the yate logo.

PyInstaller's ``EXE(icon=...)`` accepts a ``.ico`` on Windows (or ``.icns``
on macOS) -- the JPEG logo cannot be handed to it directly, so
``yate/yate.jpg`` is converted into the multi-resolution ``pack/yate.ico``
that both specs (``pack/yate.spec``, ``pack/yate-onefile.spec``) reference.

The conversion needs Pillow, which is only ever required on the machine
that regenerates the icon (the resulting ``.ico`` is committed): install it
with the ``[build]`` extra (``pip install -e ".[build]"``) or on demand with
``pip install pillow``. Because it stays an optional dependency -- and is
absent from a plain ``[dev]`` virtualenv -- the module is imported
dynamically and handled as ``Any``, so static analysis never has to resolve
it.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

#: Module providing the image conversion (Pillow).
_IMAGE_MODULE = "PIL.Image"

def repo_root() -> Path:
    """The repository root: two levels above this module (tools/pack/icon.py)."""
    return Path(__file__).resolve().parents[2]


#: Logo shipped with the package -- the single source for the icon.
DEFAULT_SOURCE = repo_root() / "yate" / "yate.jpg"
#: Icon consumed by the PyInstaller specs.
DEFAULT_TARGET = repo_root() / "pack" / "yate.ico"

#: Windows icon sizes: Explorer scales between them, 256 is the modern max.
ICON_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)


def square(image: Any) -> Any:
    """Center-crop to a square -- icons must be square, never stretched."""
    if image.width == image.height:
        return image
    side: int = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    return image.crop((left, top, left + side, top + side))


def build_icon(
    source: Path = DEFAULT_SOURCE,
    target: Path = DEFAULT_TARGET,
    sizes: tuple[int, ...] = ICON_SIZES,
) -> Path:
    """Write *target* as a multi-resolution Windows icon built from *source*.

    Returns *target*. Raises :class:`RuntimeError` when Pillow is missing,
    :class:`FileNotFoundError` when *source* does not exist and
    :class:`ValueError` when no size was given.
    """
    try:
        pillow: Any = importlib.import_module(_IMAGE_MODULE)
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Pillow is required to build the icon: pip install pillow"
        ) from exc
    if not source.is_file():
        raise FileNotFoundError(f"source image not found: {source}")
    if not sizes:
        raise ValueError("at least one icon size is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    with pillow.open(source) as image:
        image.load()
        # Pillow wants one (width, height) pair per icon entry.
        square(image).save(target, format="ICO", sizes=[(s, s) for s in sizes])
    return target
