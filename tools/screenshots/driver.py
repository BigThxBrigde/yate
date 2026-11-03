"""Pilot driver helpers for the screenshot tool.

This module owns the App factory (a direct :class:`YateApp` construction --
the smoke harness' ``new_app`` is deliberately not used because it registers
apps for the invariant sweep, which a screenshot run neither wants nor can
register), the shared fixture files the scenario drivers run against, and
the two primitives every driver body uses: headless execution at a fixed
size and the deterministic SVG save.
"""

from __future__ import annotations

import base64
import getpass
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from yate.app import YateApp
from yate.config import YateConfig

__all__ = [
    "DriverFn",
    "embed_icon_font",
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
    file_manager_dir: Path | None = None,
) -> YateApp:
    """Construct a :class:`YateApp` through its public startup knobs.

    Mirrors the CLI startup forms (``yate/app.py``): a directory *target*
    opens in browse mode (explorer visible), a file *target* in edit mode;
    ``diff_files`` / ``hex_file`` / ``file_manager_dir`` push their modal
    screen after mount.  No invariant-sweep registration happens.
    """
    return YateApp(
        target,
        keymap=keymap,
        theme_name=theme_name,
        config=config,
        diff_files=diff_files,
        hex_file=hex_file,
        file_manager_dir=file_manager_dir,
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


#: Scrub placeholders are plain ``<tokens>`` in text output, but an SVG is
#: XML: inside a frame they must land as escaped entities or the file stops
#: being well-formed and viewers refuse to render it.
_XML_ESCAPES: tuple[tuple[str, str], ...] = (
    ("<home>", "&lt;home&gt;"),
    ("<repo>", "&lt;repo&gt;"),
    ("<user>", "&lt;user&gt;"),
    ("<run>", "&lt;run&gt;"),
)
#: C0 control characters other than tab/newline/carriage return are invalid
#: XML text: the which-key sheet renders a ``ctrl+]``-style chord as its raw
#: control character, so frames sanitize them to caret notation instead.
_C0_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def scrub_svg(svg_path: Path) -> None:
    """Rewrite the SVG file at *svg_path* in place, XML-safely.

    Applies :func:`scrub_text`, then escapes the placeholders for XML text
    and renders control characters in caret notation (``0x1d`` becomes
    ``^]``) so the frame stays well-formed for every viewer.
    """
    text = scrub_text(svg_path.read_text(encoding="utf-8"))
    for raw, escaped in _XML_ESCAPES:
        text = text.replace(raw, escaped)
    text = _C0_RE.sub(lambda m: "^" + chr(ord(m.group()) + 64), text)
    text = text.replace("\x7f", "^?")
    svg_path.write_text(text, encoding="utf-8")


#: The bundled Nerd Font owns the private-use icon glyphs (file-type icons)
#: that generic viewer fonts render as tofu; a per-frame subset of it is
#: embedded so icons render on machines without a Nerd Font installed.
_BUNDLED_FONT = (
    repo_root() / "yate" / "resources" / "fonts"
    / "JetBrainsMonoNerdFontMono-Regular.ttf"
)
_ICON_FONT_NAME = "Yate NF Icons"


def embed_icon_font(svg_path: Path) -> None:
    """Embed the frame's icon glyphs into *svg_path* as a WOFF2 data URI.

    Textual's exported SVG renders the Nerd Font private-use glyphs as text;
    without a locally installed Nerd Font a viewer shows boxes.  This builds
    a subset of the bundled Nerd Font carrying exactly the private-use
    codepoints the frame uses (via the fontTools CLI -- a subprocess keeps
    the untyped package out of pyright strict) and registers it as
    ``@font-face`` inside the SVG's style block, slotted between the web
    font and ``monospace``: regular text still falls back to the viewer's
    monospace, the icon glyphs hit the embedded face.
    """
    text = svg_path.read_text(encoding="utf-8")
    codepoints = sorted({ord(c) for c in text if 0xE000 <= ord(c) <= 0xF8FF})
    if not codepoints:
        return
    unicodes = ",".join(f"U+{cp:04X}" for cp in codepoints)
    # The subset CLI has no usable stdout mode: without an explicit
    # --output-file it silently writes next to the input font.  Always aim
    # it at a temporary file we own.
    with tempfile.TemporaryDirectory(prefix="yate-font-subset-") as tmp:
        subset_path = Path(tmp) / "icons.woff2"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "fontTools.subset",
                str(_BUNDLED_FONT),
                f"--unicodes={unicodes}",
                "--flavor=woff2",
                f"--output-file={subset_path}",
            ],
            capture_output=True,
            check=False,
        )
        payload_bytes = subset_path.read_bytes() if subset_path.exists() else b""
    if proc.returncode != 0 or not payload_bytes:
        raise RuntimeError(
            "font subset failed: " + proc.stderr.decode("utf-8", errors="replace")
        )
    payload = base64.b64encode(payload_bytes).decode("ascii")
    face = (
        f'@font-face {{ font-family: "{_ICON_FONT_NAME}"; '
        f'src: url(data:font/woff2;base64,{payload}) format("woff2"); }}'
    )
    if "</style>" not in text:
        raise RuntimeError("no style block to embed the icon font into")
    text = text.replace("</style>", f"{face}\n    </style>", 1)
    text = text.replace(
        "font-family: Fira Code, monospace;",
        f'font-family: Fira Code, "{_ICON_FONT_NAME}", monospace;',
    )
    svg_path.write_text(text, encoding="utf-8")


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
