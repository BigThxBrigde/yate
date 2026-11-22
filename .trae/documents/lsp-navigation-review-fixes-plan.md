# LSP navigation review fixes plan (post-review iteration)

Review record: [../reviews/2026-11-22-lsp-navigation.md](../reviews/2026-11-22-lsp-navigation.md).
B1 rejected by direct probe (8 conflicts unchanged; `gd`/`gr` not reserved).
Accepted for fixing: B2, M1-M6 plus cheap minors m3/m7/m8/m9/m13.
Registered follow-ups (not fixed here): m1, m2 (partially mitigated by M4
tests), m4, m5, m6, m10, m11, m12.

## Fix wave F1 — tests, docs, comments (parallel with F2)

Exclusive files:
`tools/smoke_test/scenarios/lsp_navigation.py`, `tests/test_action_table.py`,
`tests/test_vim_keymap.py`, `tests/test_architecture.py`,
`yate/keymaps/vim.py`, `yate/docs/lsp.zh.md`, `yate/docs/lsp.en.md`,
`yate/resources/manual.zh.md`, `yate/resources/manual.en.md`.

1. M1: change `_open_call_site(pilot: object, ...)` to
   `pilot: Any,  # noqa: Any - naming Pilot would import textual here`
   (follow `scenarios/_base.py:111`). Run pyright on that file.
2. M2: in `tests/test_action_table.py` add `lsp_navigation` to
   `_FLOW_NAMESPACES` and six `lsp_navigation.*` entries to `FORWARDED_HOOKS`
   (names match `yate/actions.py`); in `tests/test_vim_keymap.py:1975-1978`
   append the two new `g`-prefix hint rows. Run both test files.
3. B2: rewrite the `vim.py:280-282` comment to say `gd`/`gr` rows are help
   mirrors consumed by the `g`-prefix branches, while `K` is a real dispatch
   row used by `_handle_normal`'s table lookup. In
   `tests/test_architecture.py::test_lsp_navigation_keys_are_shared_and_identical`
   add runtime assertions that both `<f7>` and `K` resolve to
   `show_hover_docs` in vim and vsc (dual-row coexistence).
4. M3: replace every `:lsp outline` mention in the four docs with "command
   palette: `show_outline`" (or the corresponding Chinese wording); do not
   add a new `:lsp` command in this iteration. Verify no `lsp outline` hits.
5. m13: update the stale comment at `tests/test_lsp_real_server.py:184`
   **only if that file is also touched by F2** (it is); otherwise leave to F2.

Acceptance: pyright on the smoke scenario; the three touched test files
green; architecture 47 passed; grep for `lsp outline` returns 0.

## Fix wave F2 — product robustness and direct tests (parallel with F1)

Exclusive files:
`yate/editor_lsp/manager.py`, `yate/editor_lsp/navigation.py`,
`tests/test_lsp_navigation.py`, `yate/flows/lsp_navigation_flows.py`,
`tests/test_lsp_navigation_flows.py`,
`yate/editor_components/lsp_chooser.py`, `tests/test_lsp_chooser.py`,
`yate/editor_components/commandline.py`, `tests/test_lsp_real_server.py`.

1. M6: add `reason` to `LspFeatureUnavailable` (`"unsupported"` default);
   `manager._request` passes `"no-ready-server"` when client is None;
   `_failure_text` emits "language server is not ready" vs "server does not
   support X". Add tests for all three degradation paths.
2. M4: direct manager tests for `request_document_symbols`, `request_rename`,
   `request_code_actions`, `request_signature_help`, and `execute_command`.
   Cover documentChanges, non-ASCII UTF-16 columns, diagnostic round-trip,
   and command failure logging. Mitigate reviewer m2: `_clamp_range` must use
   the target URI's `LspManager._open[uri].doc` when available; for other
   URIs pass columns through untouched rather than clamping to the source doc.
3. M5: track the documents opened by rename; on failure restore text/cursor
   and disclose in the message; on success change the message to
   `Renamed N occurrence(s) in M file(s) (unsaved; save to apply)`. Add a
   test with an unopened target and an invalid second edit.
4. Cheap minors: m3 wrap `send_cancel` failure in `try/except (LspError,
   OSError)` with `log.debug` (add module logger, R12); m7 dismiss chooser in
   `try/finally`; m8 add `PREFIXES["lsp_rename"] = ("Rename: ", "yellow")`;
   m9 remove the dead `NAV_TIMEOUT_MESSAGE` branch or map the wrapped failure
   (LspFeatureFailed carries the method); m13 fix the stale comment.
5. Re-measure `editor_lsp/manager.py` `splitlines()`; if it changed, update
   the rule table and `SIZE_EXEMPT_LINE_COUNTS` in F1's `tests/test_architecture.py`
   **by reporting the number to the main agent**, which will apply the
   cross-wave sync (no file overlap violation).

Acceptance: new/updated test files green; pyright on touched product files;
no full suite here (main agent runs final gates).

## Final

After F1+F2, the main agent reruns the five gates, updates the review record
with post-fix results, and commits each fix wave separately. No push/merge.
