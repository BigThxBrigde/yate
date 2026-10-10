"""Command-line entry point for ``python -m tools.smoke_test``."""

from __future__ import annotations

from tools.smoke_test.testsuite import main

if __name__ == "__main__":
    raise SystemExit(main())
