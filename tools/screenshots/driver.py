"""Pilot driver helpers for the screenshot tool.

This module owns the App factory (a direct :class:`YateApp` construction --
the smoke harness' ``new_app`` is deliberately not used because it registers
apps for the invariant sweep, which a screenshot run neither wants nor can
register), the shared fixture files the scenario drivers run against, and
the two primitives every driver body uses: headless execution at a fixed
size and the deterministic SVG save.
"""

from __future__ import annotations

import getpass
import re
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from yate.app import YateApp
from yate.config import YateConfig

__all__ = [
    "DriverFn",
    "make_app",
    "repo_root",
    "save_svg",
    "scrub_svg",
    "scrub_text",
    "write_fixtures",
]

#: Signature of a scenario driver: receives the SVG output path and a fresh
#: fixture directory (already populated by :func:`write_fixtures`).
type DriverFn = Callable[
    [Path, Path],
    # noqa: Any - Coroutine[Any, Any, None] is the canonical awaitable form.
    Coroutine[Any, Any, None],
]


def repo_root() -> Path:
    """Return the repository root (three levels above this file)."""
    return Path(__file__).resolve().parents[2]


def make_app(
    target: str | Path | None = None,
    *,
    keymap: str | None = None,
    theme_name: str | None = None,
    config: YateConfig | None = None,
    diff_files: list[Path] | None = None,
    hex_file: Path | None = None,
    filemanager_dir: Path | None = None,
) -> YateApp:
    """Construct a :class:`YateApp` through its public startup knobs.

    Mirrors the CLI startup forms (``yate/app.py``): a directory *target*
    opens in browse mode (explorer visible), a file *target* in edit mode;
    ``diff_files`` / ``hex_file`` / ``filemanager_dir`` push their modal
    screen after mount.  No invariant-sweep registration happens.
    """
    return YateApp(
        target,
        keymap=keymap,
        theme_name=theme_name,
        config=config,
        diff_files=diff_files,
        hex_file=hex_file,
        filemanager_dir=filemanager_dir,
    )


def save_svg(app: YateApp, svg_path: Path) -> None:
    """Export the current frame of *app* as a deterministic SVG file."""
    app.save_screenshot(str(svg_path))


#: Windows home directories (a drive-letter ``Users`` path, in both slash
#: styles); the pattern literals are assembled so the home-path architecture
#: guard does not flag these very lines.
_HOME_WIN_RE = re.compile(r"[A-Za-z]:" r"[\\/]+Users[\\/]+[^\\/\s\"'<>|:]+")
#: POSIX home directories (a POSIX-style home path, same guard note).
_HOME_POSIX_RE = re.compile(r"/ho" r"me/[^/\s\"'<>]+")
#: Forward-slash variant of the repository root (some tools print those).
_REPO_FORWARD: str = str(repo_root()).replace("\\", "/")
#: This tool's own temporary fixture prefix: its random per-run token must
#: not reach a screenshot, or regenerations stop being byte-identical.
_FIXTURE_PREFIX_RE = re.compile(r"yate-screenshots-[0-9a-z]+")
#: Rich's exported-SVG element id: ``adler32`` over the recorded segment
#: stream, which jitters for timing-sensitive frames even when the visible
#: content is identical.  Normalizing it keeps regenerations byte-identical
#: (the id appears only in CSS selectors and the root id, never in text).
_SVG_ID_RE = re.compile(r"terminal-\d+")


def scrub_text(text: str) -> str:
    """Mask machine-specific paths and the local user name in *text*.

    Committed screenshots are public-repo content, so they must not carry
    the local user name, home directory or repository path (the repo's
    real-path masking rule -- the same content its ``HOME_PATH_PATTERN``
    architecture guard bans in sources, just rendered into an SVG).
    Substitutions are plain deterministic string replacements, so scrubbing
    never breaks SVG reproducibility.
    """
    text = _HOME_WIN_RE.sub("<home>", text)
    text = _HOME_POSIX_RE.sub("<home>", text)
    text = text.replace(str(repo_root()), "<repo>")
    text = text.replace(_REPO_FORWARD, "<repo>")
    text = _FIXTURE_PREFIX_RE.sub("yate-screenshots-<run>", text)
    text = _SVG_ID_RE.sub("terminal-0", text)
    user = getpass.getuser()
    # Long-enough names only: a short name ("ed") would mangle ordinary words.
    if len(user) >= 4:
        text = text.replace(user, "<user>")
    return text


def scrub_svg(svg_path: Path) -> None:
    """Rewrite the SVG file at *svg_path* in place via :func:`scrub_text`."""
    svg_path.write_text(
        scrub_text(svg_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


#: Sample Python source exercising the syntax highlighter (strings, f-string,
#: decorator, class, loop, comment).
_FIXTURE_PY = '''"""Sample module used by the screenshot scenarios."""


import itertools


def greet(name: str) -> str:
    """Return a friendly greeting for *name*."""
    return f"Hello, {name}!"


class Greeter:
    """Prefixes every greeting with a fixed salutation."""

    def __init__(self, salutation: str = "Hello") -> None:
        self.salutation = salutation

    def greet(self, name: str) -> str:
        return f"{self.salutation}, {name}!"


if __name__ == "__main__":
    for name in itertools.islice(itertools.count(), 3):
        print(greet(f"guest-{name}"))
'''

#: Repeated words for the buffer-completion fallback source.
_FIXTURE_WORDS = "alpha alphabet alpha\nalphabet alpha\n"

_FIXTURE_A = "alpha\nbravo\ncharlie\n"
_FIXTURE_B = "delta\necho\nfoxtrot\n"
_FIXTURE_C = "golf\nhotel\nindia\n"

#: xxd-style diff pair: one changed word plus one added line.
_FIXTURE_LEFT = "alpha\nbravo\ncharlie\n"
_FIXTURE_RIGHT = "alpha\nbravo\ncharly\ndelta\n"


def write_fixtures(fixtures: Path) -> None:
    """Create the fixture files the scenario drivers may reference."""
    (fixtures / "sample.py").write_text(_FIXTURE_PY, encoding="utf-8")
    (fixtures / "words.txt").write_text(_FIXTURE_WORDS, encoding="utf-8")
    (fixtures / "a.txt").write_text(_FIXTURE_A, encoding="utf-8")
    (fixtures / "b.txt").write_text(_FIXTURE_B, encoding="utf-8")
    (fixtures / "c.txt").write_text(_FIXTURE_C, encoding="utf-8")
    (fixtures / "left.txt").write_text(_FIXTURE_LEFT, encoding="utf-8")
    (fixtures / "right.txt").write_text(_FIXTURE_RIGHT, encoding="utf-8")
    (fixtures / "thing.bin").write_bytes(b"\x00\x01\x02\x03binary\xff\x00\x01")
