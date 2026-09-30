"""Argparse front end for the Markdown translator (``python -m tools.translate``).

Reads the source document from ``IN`` or, when absent, from stdin (written
to a temporary file so the agent can Read it), prints the translation -- and
only the translation -- to stdout, and additionally writes it to ``OUT``
(UTF-8, no BOM) when given.  Any failure reports ``wiki-translate: ...`` on
stderr and returns exit code 1 without ever touching ``OUT``.
"""

from __future__ import annotations

import argparse
import dataclasses
import shlex
import sys
import tempfile
from pathlib import Path

from tools.translate import runner


@dataclasses.dataclass(frozen=True)
class _Options:
    """Resolved command-line options for one invocation."""

    input: Path | None
    output: Path | None
    cmd: str
    model: str
    fallback_model: str | None
    max_turns: int
    timeout: int
    dry_run: bool


def _parse_args(argv: list[str] | None) -> _Options:
    """Parse *argv* into resolved :class:`_Options`."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.translate",
        description="Translate a Markdown document to English via codebuddy-code.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        type=Path,
        help="source Markdown file (default: read stdin)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        type=Path,
        help="also write the translation here as UTF-8 (default: stdout only)",
    )
    parser.add_argument(
        "--model",
        default=runner.DEFAULT_MODEL,
        help="translator model (default: %(default)s)",
    )
    parser.add_argument(
        "--fallback-model",
        default=None,
        help="model to fall back to on overload (default: none)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=runner.DEFAULT_MAX_TURNS,
        help="max agent turns; Read calls consume turns (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=runner.DEFAULT_TIMEOUT,
        help="per-document timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--cmd",
        default=runner.DEFAULT_CMD,
        help="translator CLI binary (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command and prompt, then exit without translating",
    )
    args = parser.parse_args(argv)
    return _Options(
        input=args.input,
        output=args.output,
        cmd=args.cmd,
        model=args.model,
        fallback_model=args.fallback_model,
        max_turns=args.max_turns,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )


def _translate_file(source_path: Path, source_text: str, options: _Options) -> int:
    """Translate *source_path* and handle output/reporting.

    Returns the process exit code: 0 on success, 1 on any failure.  ``OUT``
    is written only after the translation has passed both validity checks.
    """
    prompt = runner.build_prompt(source_path)
    command = runner.build_command(
        options.cmd, prompt, options.model, options.max_turns, options.fallback_model
    )
    if options.dry_run:
        print("command: " + shlex.join(command))
        print()
        print(prompt)
        return 0
    try:
        raw = runner.run_translation(command, options.timeout)
    except runner.TranslateError as exc:
        print(f"wiki-translate: {exc}", file=sys.stderr)
        return 1
    translated = runner.clean_output(raw)
    if not translated:
        print("wiki-translate: translator produced empty output", file=sys.stderr)
        return 1
    if translated == source_text.strip():
        print("wiki-translate: translation is identical to the source", file=sys.stderr)
        return 1
    print(translated)
    if options.output is not None:
        try:
            # Trailing newline so OUT matches the stdout payload byte-for-byte.
            options.output.write_text(f"{translated}\n", encoding="utf-8")
        except OSError as exc:
            print(f"wiki-translate: cannot write {options.output}: {exc}", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the translator; see :mod:`tools.translate` for the I/O protocol."""
    options = _parse_args(argv)
    if options.input is not None:
        try:
            source_text = options.input.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"wiki-translate: cannot read {options.input}: {exc}", file=sys.stderr)
            return 1
        return _translate_file(options.input, source_text, options)
    source_text = sys.stdin.read()
    with tempfile.TemporaryDirectory(prefix="wiki-translate-") as tmp:
        temp_path = Path(tmp) / "stdin.md"
        temp_path.write_text(source_text, encoding="utf-8")
        return _translate_file(temp_path, source_text, options)
