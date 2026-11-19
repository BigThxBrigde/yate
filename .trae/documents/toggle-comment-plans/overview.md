# Toggle comment (IKWNOG) sub-plans overview

Single source of truth: [`../toggle-comment-plan.md`](../toggle-comment-plan.md).
This overview only splits its four waves into exclusive-file sub-plans.

| Wave | Sub-plan | Product | Files owned |
|---|---|---|---|
| a | [plan-a.md](plan-a.md) | key constants + reversible pure comment engine | `keymaps/keys.py`, `editor_core/commenting.py`, `tests/test_commenting.py`, `tests/test_key_notation.py` |
| b | [plan-b.md](plan-b.md) | action, command, dispatch interception, keymap rows, help overlay | `actions.py`, `commands.py`, `editor_dispatch.py`, `keymaps/vsc.py`, `keymaps/vim.py` (binding rows only), `editor_components/modals.py`, `tests/test_toggle_comment.py`, `tests/test_editor_dispatch.py` |
| c | [plan-c.md](plan-c.md) | vim `gc{motion}` / `gcc` / visual `gc` state machine and hints | `keymaps/vim.py` (state machine), `tests/test_vim_keymap.py`, `tests/test_whichkey_flows.py` |
| d | [plan-d.md](plan-d.md) | architecture guard #45 + bilingual docs + changelog | `tests/test_architecture.py`, `.trae/rules/architecture-boundaries.md`, `resources/manual.en.md`, `resources/manual.zh.md`, `docs/which-key.en.md`, `docs/which-key.zh.md`, `CHANGELOG.md`, `CHANGELOG.zh.md` |

Waves run strictly in order; each wave is committed separately. Review and
final gates are described in the main plan §3.
