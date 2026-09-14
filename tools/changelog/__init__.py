"""Bilingual changelog generator driven by git history.

Generates ``CHANGELOG.md`` (English) and ``CHANGELOG.zh.md`` (Chinese) from
the repository's git history, following the frozen conventions in
``.trae/documents/changelog_plan.md``:

* version segments come from ``vX.Y.Z`` tags first, version bumps in
  ``yate/__init__.py`` second, cold start (no tag, never bumped) last;
* commits are grouped by Conventional Commits type;
* Chinese summaries come from the human-maintained override table
  ``tools/changelog/zh_overrides.json`` and fall back to English with a
  ``[缺中文]`` marker.

Entry point: ``python -m tools.changelog --help``.
"""

__version__ = "0.1.1"
__all__ = ["__version__"]