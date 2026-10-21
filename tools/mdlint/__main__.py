"""Entry shim: ``python -m tools.mdlint``."""

from __future__ import annotations

import sys

from tools.mdlint.cli import main

sys.exit(main())
