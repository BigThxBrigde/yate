"""Scenarios for the modules split out by big-module-split / extensions-split.

Two end-to-end paths that span the newly split submodules and that no other
scenario group covers:

* extension round-trip: ``load_startup_extensions``
  (:mod:`yate.services.extension_loader`) -> ``ExtensionAPI`` rollback scope
  (:mod:`yate.services.extension_api`) -> registries -> ``:`` command and
  action dispatch -> ``teardown_all``;
* custom theme file: ``load_theme_paths`` (:mod:`yate.editor_view.theme_files`)
  -> ``themes.register_theme`` -> ``:theme <name>`` -> ``theme.active()``.
"""

from __future__ import annotations

from pathlib import Path

from tools.smoke_test.harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg
from tools.smoke_test.scenarios._base import message_text, run_command
from yate.editor_view import theme
from yate.editor_view.theme_files import load_theme_paths
from yate.editor_view.themes import THEMES
from yate.paths import package_root
from yate.services.extensions import load_startup_extensions

__all__ = ["SCENARIOS"]


async def _extension_roundtrip(tmp: Path) -> ScenarioResult:
    """A temp extension registers action+command, they dispatch, teardown runs.

    The teardown MARK flip itself is asserted by ``tests/test_extensions.py``
    (the loader owns the module instance, so the scenario cannot re-import
    it); here teardown is proven by ``teardown_all()`` completing without
    error and the load record staying clean.
    """
    ext = tmp / "ext_roundtrip.py"
    ext.write_text(
        "MARK = {'torn_down': False}\n"
        "def setup(api):\n"
        "    api.message('EXT-SETUP')\n"
        # Action callables receive the ActionContext (ActionRegistry.execute
        # invokes func(ctx)), hence the one-parameter lambda.
        "    api.register_action('ext_rt_action',\n"
        "                        lambda ctx: api.message('RT-ACTION-OK'))\n"
        "    def cmd(args):\n"
        "        api.message('RT-CMD-OK:' + args)\n"
        "    api.command('ext_rt_cmd')(cmd)\n"
        "def teardown(api):\n"
        "    MARK['torn_down'] = True\n",
        encoding="utf-8",
    )
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        messages = load_startup_extensions(
            app.editor.extension_loader,
            app.editor.config,
            ext_files=[ext],
        )
        checks.append(Check("setup_message", True,
                            "EXT-SETUP" in message_text(app)))
        # Scoped to this extension on purpose: load_startup_extensions
        # de-duplicates already-loaded scripts by resolved path, so re-running
        # it here would re-report pre-existing load errors of *other*
        # extensions from the app's own startup pass.
        checks.append(Check("no_load_errors", True,
                            not any("extension ext_roundtrip:" in m
                                    for m in messages)))
        await run_command(pilot, "ext_rt_cmd with args")
        checks.append(Check("command_dispatched", True,
                            "RT-CMD-OK:with args" in message_text(app)))
        app.editor.execute_action("ext_rt_action")
        await pilot.pause()
        checks.append(Check("action_dispatched", True,
                            "RT-ACTION-OK" in message_text(app)))
        record = next(
            (r for r in app.editor.extension_loader.loaded
             if r.name == "ext_roundtrip"),
            None,
        )
        checks.append(Check("loaded_record_clean", True,
                            record is not None and record.error is None))
        app.editor.extension_loader.teardown_all()
        await pilot.pause()
        # the teardown MARK flip is visible through the record's module
        # instance (the loader owns the import), locking the teardown leg
        # end-to-end (same shape as tests/test_extensions.py teardown cases)
        checks.append(Check("teardown_ran", True,
                            record is not None and record.module is not None
                            and record.module.MARK["torn_down"] is True))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("integration_extension_roundtrip", checks, rows)


async def _custom_theme_file(tmp: Path) -> ScenarioResult:
    """A user theme file registers a theme that :theme can switch to.

    The shipped template registers three variants; after the rename the
    names are ``rt_custom-dark`` / ``rt_custom-mirage`` / ``rt_custom-light``
    (its ``Theme(name=...)`` arguments carry the ``ayu-`` prefix).  The
    registrations are removed from the process-global ``THEMES`` dict before
    returning: the full smoke suite runs every scenario in one process and
    ``regress_theme_expansion`` enumerates ``theme.available()`` against its
    stored baseline, so leftover registrations would drift it.
    """
    template = (
        package_root() / "resources" / "theme_examples" / "ayu_theme.example"
    )
    # Renaming every "ayu" occurrence keeps the file valid Python (the
    # _ayu helper and its three register_theme call sites rename together).
    body = template.read_text(encoding="utf-8").replace("ayu", "rt_custom")
    (tmp / "themes").mkdir()
    (tmp / "themes" / "rt_custom_theme.py").write_text(body, encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    try:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            errors: list[str] = []
            load_theme_paths([tmp / "themes"], errors)
            checks.append(Check("theme_registered", True,
                                not errors
                                and "rt_custom-dark" in theme.available()))
            await run_command(pilot, "theme rt_custom-dark")
            checks.append(Check("switched", "rt_custom-dark",
                                theme.active().name))
            await run_command(pilot, "theme mocha")
            checks.append(Check("restored", "mocha", theme.active().name))
            rows = snapshot_svg(app, tmp)
    finally:
        # Undo the process-global registrations (THEMES.pop -- the same
        # cleanup the test suite uses) so later scenarios in the same
        # process see the pre-scenario theme name space.  The finally guard
        # matters because regress_theme_expansion enumerates
        # theme.available() in this same process: a mid-scenario failure
        # must not leak rt_custom-* into its baseline drift.
        for leftover in [n for n in list(THEMES) if n.startswith("rt_custom-")]:
            THEMES.pop(leftover)
    return ScenarioResult("integration_custom_theme_file", checks, rows)


SCENARIOS: list[Scenario] = [
    Scenario("integration_extension_roundtrip", _extension_roundtrip,
             ("integration",)),
    Scenario("integration_custom_theme_file", _custom_theme_file,
             ("integration",)),
]
