"""Guards for the app-level stylesheet bundled at ``yate/resources/app.tcss``."""

from __future__ import annotations

from importlib.resources import files

from yate.app import YateApp


def test_app_tcss_resource_exists_and_is_nonempty() -> None:
    """resources/app.tcss ships with the package and holds real rules."""
    text = files("yate.resources").joinpath("app.tcss").read_text(encoding="utf-8")
    assert "#editor-col" in text


def test_yateapp_css_matches_bundled_tcss() -> None:
    """``YateApp.CSS`` comes from the bundled tcss, not an inline literal."""
    text = files("yate.resources").joinpath("app.tcss").read_text(encoding="utf-8")
    assert YateApp.CSS == text
