"""Entry shim: ``python -m tools.mdlint``."""

from __future__ import annotations

import sys


def _run() -> int:
    """Import the CLI late so a missing backend reports one line, not a stack."""
    try:
        from tools.mdlint.cli import main
    except ModuleNotFoundError as exc:
        if not (exc.name or "").startswith("pymarkdown"):
            raise
        print(
            f"error: pymarkdownlnt is required by mdlint ({exc}); "
            "install the dev extras (pip install -e .[dev])",
            file=sys.stderr,
        )
        return 2
    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
