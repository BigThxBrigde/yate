# tests/

Tests are organized **by behavior domain**, not one-to-one per module under
test. Examples: `actions.py` + `commands.py` are both covered by
`test_action_table.py`; the L3 flow modules (`document_flows.py`,
`window_flows.py`, `overlays.py`, `prompt_flows.py`, `lsp_sync.py`,
`extension_flows.py`) are exercised indirectly through the Textual pilot
integration tests (`test_app_textual.py` and friends) rather than by
same-named test files.

## Indirect coverage map

Root modules without a same-named `test_<module>.py`, and the test files that
cover them:

| Root module          | Covered by |
|----------------------|------------|
| `dist_meta.py`       | `test_diagnostics.py` |
| `document_flows.py`  | `test_action_table.py`, `test_app_textual.py`, `test_config.py` |
| `window_flows.py`    | `test_app_textual.py` |
| `extension_flows.py` | `test_app_textual.py`, `test_cli.py`, `test_diagnostics.py` |
| `overlays.py`        | `test_action_table.py`, `test_app_textual.py`, `test_changelog_view.py`, `test_vim_keymap.py` |
| `prompt_flows.py`    | `test_action_table.py`, `test_app_textual.py`, `test_vim_keymap.py` |
| `lsp_sync.py`        | `test_explorer.py` |

(`test_extensions.py` covers `yate/services/extensions.py`, the extension
loader — not `extension_flows.py`. `test_architecture.py` references several
of these modules but enforces layer boundaries; it is a guard, not behavior
coverage.)

## Conventions

- Naming / isolation conventions live in the `tests/conftest.py` docstring;
  the autouse `isolated_home` fixture redirects `Path.home()` (and
  `USERPROFILE` / `HOME`) to a per-test temp dir so no test touches the real
  user `~/.yate`.
- Architecture guards: `test_architecture.py`, backed by
  `.trae/rules/architecture-boundaries.md` §六.
- Dependency-group drift guard (dev vs ts, review item A6):
  `test_dependency_groups.py`.
