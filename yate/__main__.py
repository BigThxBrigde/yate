"""Allow ``python -m yate``."""

from __future__ import annotations

from yate.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
