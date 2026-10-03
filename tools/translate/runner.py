"""Core translation logic: prompt/command assembly, subprocess run, output cleaning.

:func:`run_translation` shells out to the ``codebuddy-code`` CLI in
non-interactive mode with only the ``Read`` tool enabled, so the agent can
load the source document but cannot write anything itself.  All file I/O
(stdin capture, temp files, ``OUT``) stays under the control of
:mod:`tools.translate.cli`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

#: Default translator CLI binary (``codebuddy-code``, alias ``cbc``).
DEFAULT_CMD: str = "codebuddy-code"

#: Default model.
DEFAULT_MODEL: str = "hy3"

#: Default fallback model, forwarded as ``--fallback-model`` (used on overload).
DEFAULT_FALLBACK_MODEL: str = "glm-5.3-flash"

#: Default max agent turns -- each Read tool call consumes one turn.
DEFAULT_MAX_TURNS: int = 10

#: Default per-document timeout in seconds (a single page takes ~14-22 s).
DEFAULT_TIMEOUT: int = 900

#: The only tool the translation agent is granted.
_ALLOWED_TOOLS: str = "Read"


class TranslateError(Exception):
    """Raised when the translation command fails or produces unusable output."""


def build_prompt(source_path: Path) -> str:
    """Build the English instruction prompt for translating *source_path*.

    The prompt tells the agent to Read the file itself, translate the
    Markdown to English while preserving structure, keep code blocks /
    commands / paths / identifiers verbatim, and emit only the translation
    with no explanations and no surrounding code fences.
    """
    return (
        f"Read the file at {source_path} and translate its Markdown content "
        "from Chinese into English. Preserve the document structure exactly: "
        "keep every heading, list, table, and code block in place. Never "
        "translate fenced code blocks, shell commands, file paths, or "
        "identifiers. Output only the translated Markdown -- no explanations "
        "and no surrounding code fences."
    )


def build_command(
    cmd: str,
    prompt: str,
    model: str,
    max_turns: int,
    fallback_model: str | None,
) -> list[str]:
    """Assemble the translator command as an argv list (no shell involved)."""
    argv = [
        cmd,
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "text",
        "--tools",
        _ALLOWED_TOOLS,
        "--permission-mode",
        "bypassPermissions",
        "--max-turns",
        str(max_turns),
        "--no-session-persistence",
    ]
    if fallback_model is not None:
        argv.extend(["--fallback-model", fallback_model])
    return argv


def clean_output(raw: str) -> str:
    """Strip whitespace and remove one wrapping pair of ``` fences.

    Returns the cleaned text.  An output that was *only* a fence pair
    collapses to the empty string; the caller treats that as a failure.
    """
    text = raw.strip()
    lines = text.splitlines()
    # Only a bare ``` (no language tag) counts as a wrapper: a translation
    # that legitimately starts with a fenced code block must survive.
    if len(lines) >= 2 and lines[0].strip() == "```" and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _resolve_executable(cmd: str) -> str:
    """Resolve *cmd* against ``PATH`` (``PATHEXT``-aware on Windows).

    The npm shim for ``codebuddy-code`` is a ``.cmd`` file, which a bare
    :func:`subprocess.run` argv cannot find on Windows (``WinError 2``).
    Resolving up front also turns a missing binary into a clear error.
    """
    found = shutil.which(cmd)
    if found is None:
        raise TranslateError(f"translator command not found on PATH: {cmd}")
    return found


def run_translation(argv: list[str], timeout: int) -> str:
    """Run the translator command and return its raw stdout.

    The command runs without a shell over UTF-8 text pipes.  Raises
    :class:`TranslateError` when the executable cannot be found, when it
    exceeds *timeout* seconds, or when it exits with a non-zero status
    (the CLI's stderr is carried in the message).
    """
    argv = [_resolve_executable(argv[0]), *argv[1:]]
    try:
        proc = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TranslateError(f"translation command timed out after {timeout}s") from None
    except FileNotFoundError as exc:
        raise TranslateError(f"translator command not found: {exc}") from None
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise TranslateError(
            f"translation command failed with exit code {proc.returncode}: {detail}"
        )
    return proc.stdout
