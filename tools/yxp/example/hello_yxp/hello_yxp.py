"""Example yate extension packaged as ``hello_yxp.yxp``.

Build and install from the repository root::

    python -m tools.yxp build tools/yxp/example/hello_yxp
    yate --install-extension hello_yxp-1.0.0.yxp

Restart yate afterwards (the startup loader picks up new top-level
``*.py`` files) and run ``:hello-yxp``.
"""

from __future__ import annotations

from yate.services.extensions import ExtensionAPI


def setup(api: ExtensionAPI) -> None:
    """Register the greeting command."""

    def hello(_args: str) -> None:
        """Show a greeting from the packaged extension."""
        api.message("hello from hello_yxp 1.0.0!")

    api.register_command("hello-yxp", hello, "greet from the .yxp package")
