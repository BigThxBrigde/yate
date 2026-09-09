"""Allow ``python -m yate``."""

from yate.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
