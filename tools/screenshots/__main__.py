"""CLI entry point: ``python -m tools.screenshots``.

Generates one deterministic SVG per scenario into ``<repo>/screenshots/``
and renders the gallery (``screenshots/README.md``) for every scenario
whose SVG exists in the output directory: a full run lists the whole
registry, a partial ``--only`` run regenerates images without clobbering
the full gallery, and a scenario that never produced an image is never
referenced.  Each scenario runs against a fresh temporary fixture
directory.
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

from tools.screenshots.driver import repo_root, write_fixtures
from tools.screenshots.gallery import render_gallery
from tools.screenshots.scenarios import SCENARIOS, Scenario

__all__ = ["main"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the CLI arguments (``--out/--only/--list/--skip-cli``)."""
    parser = argparse.ArgumentParser(
        prog="tools.screenshots",
        description=(
            "Generate the README screenshot gallery: one deterministic SVG "
            "per scenario plus screenshots/README.md."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="output directory (default: <repo>/screenshots)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="NAME",
        help="run only the named scenario (repeatable)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the scenario registry and exit",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="skip the three slow subprocess report scenarios",
    )
    return parser.parse_args(argv)


def _select(only: list[str] | None) -> list[Scenario]:
    """Resolve the requested scenario subset, validating the names."""
    if only is None:
        return list(SCENARIOS)
    known = {scenario.name for scenario in SCENARIOS}
    unknown = [name for name in only if name not in known]
    if unknown:
        raise SystemExit(f"unknown scenario(s): {', '.join(unknown)}")
    wanted = set(only)
    return [scenario for scenario in SCENARIOS if scenario.name in wanted]


def _run_one(scenario: Scenario, svg_path: Path) -> None:
    """Run one scenario against a fresh temporary fixture directory."""
    with tempfile.TemporaryDirectory(prefix="yate-screenshots-") as tmp:
        fixtures = Path(tmp)
        write_fixtures(fixtures)
        asyncio.run(scenario.driver(svg_path, fixtures))


def main(argv: list[str] | None = None) -> int:
    """CLI body: generate the requested SVGs plus the gallery."""
    args = _parse_args(argv)
    if args.list:
        for scenario in SCENARIOS:
            skip = " (skip-cli)" if scenario.skip_cli else ""
            print(f"{scenario.name:22s} {scenario.title_en}{skip}")
        print(f"total: {len(SCENARIOS)} scenarios")
        return 0

    requested = _select(args.only)
    selected = [
        scenario for scenario in requested
        if not (args.skip_cli and scenario.skip_cli)
    ]
    skipped = len(requested) - len(selected)

    out_dir = args.out if args.out is not None else repo_root() / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    failed: set[str] = set()
    for scenario in selected:
        svg_path = out_dir / f"{scenario.name}.svg"
        try:
            _run_one(scenario, svg_path)
            print(f"ok   {scenario.name}")
        except Exception as exc:  # noqa: BLE001 - one failure must not abort the batch
            failed.add(scenario.name)
            print(f"FAIL {scenario.name}: {type(exc).__name__}: {exc}")

    succeeded = [s for s in selected if s.name not in failed]
    # The gallery always describes the full registry, filtered down to the
    # scenarios whose SVG exists: a partial --only regen then leaves the
    # full gallery byte-identical instead of shrinking it to the subset.
    gallery_scenarios = [
        scenario for scenario in SCENARIOS
        if (out_dir / f"{scenario.name}.svg").exists()
    ]
    if gallery_scenarios:
        gallery = render_gallery(gallery_scenarios, out_dir)
        print(f"gallery: {gallery}")
    print(
        f"generated: {len(succeeded)}/{len(selected)}  "
        f"skipped: {skipped}  failed: {len(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
