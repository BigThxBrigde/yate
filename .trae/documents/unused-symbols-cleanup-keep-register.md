# IKTR5Q 不可删登记表

> 与 [`unused-symbols-cleanup-delete-list.md`](unused-symbols-cleanup-delete-list.md) 同时交付，
> 数量可对账；来源事实表由 `_ast_probe.py` / `_ast_report.py` 的 AST 复扫产出，
> 逐条经源码回读复核（临时探针，最终不入库）。

格式：`文件:行号 → 类别 → 保留理由`（表中另列符号名与符号种类）。

## 对账总表

| 项 | 数量 |
| --- | --- |
| 本轮复扫候选总数 | 1255 |
| 判定删除 | 12 |
| 判定保留 | 1243 |
| 保留 + 删除 | 1255 |

按类别小计：

| 类别 | 小计 |
| --- | --- |
| test-stub-signature | 399 |
| semantic-store:unpack | 349 |
| unpack-placeholder | 215 |
| pytest-fixture | 112 |
| semantic-store:loop_target | 90 |
| framework-fixed-signature:command-registry | 27 |
| protocol:host-mirror | 16 |
| protocol | 6 |
| semantic-store:nonlocal | 5 |
| ast-false-positive:nested-class-attribute | 4 |
| framework-fixed-signature:scenario-driver | 4 |
| override | 3 |
| framework-fixed-signature | 2 |
| framework-fixed-signature:platform-placeholder | 2 |
| internal-callback-fixed-signature | 2 |
| test-stub-signature:monkeypatch | 2 |
| framework-fixed-signature:keymap-callback | 1 |
| framework-fixed-signature:progress-adapter | 1 |
| intentional-ignore | 1 |
| open-api:cli-surface | 1 |
| semantic-store:global | 1 |

## 逐条登记

### ast-false-positive:nested-class-attribute（4 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tests/test_changelog_view.py:208` | `overlays` | local | the store is a class attribute inside a nested class, read by the test through the instance; deleting it changes behaviour |
| `tests/test_overlay_flows_hex.py:238` | `st_mtime` | local | the store is a class attribute inside a nested class, read by the test through the instance; deleting it changes behaviour |
| `tests/test_overlay_flows_hex.py:238` | `st_size` | local | the store is a class attribute inside a nested class, read by the test through the instance; deleting it changes behaviour |
| `tests/test_shell.py:384` | `pid` | local | the store is a class attribute inside a nested class, read by the test through the instance; deleting it changes behaviour |

### framework-fixed-signature（2 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/diff/screen.py:164` | `event` | param | decorator/registry supplies positional arguments |
| `tools/probes/pb6_real_input_harness.py:121` | `_lparam` | param | decorator/registry supplies positional arguments |

### framework-fixed-signature:command-registry（27 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/commands.py:266` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:272` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:275` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:278` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:306` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:309` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:354` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:357` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:360` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:363` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:366` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:369` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:372` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:375` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:378` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:381` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:486` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:489` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:492` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:513` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:516` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:519` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:522` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:525` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:563` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:594` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |
| `yate/commands.py:612` | `args` | param | CommandRegistry stores CommandFunc = Callable[[str], object]; the argument string is supplied positionally by the registry |

### framework-fixed-signature:keymap-callback（1 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/diff/pane.py:106` | `pane` | param | keymap table calls each binding with the pane as a fixed argument |

### framework-fixed-signature:platform-placeholder（2 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_term/pty_proc.py:754` | `owner` | param | placeholder __init__ mirrors the real POSIX/NT implementation, which consumes owner; PtyProcess.__init__ calls _UnixPty(self) / _ConPty(self) |
| `yate/editor_term/pty_proc.py:759` | `owner` | param | placeholder __init__ mirrors the real POSIX/NT implementation, which consumes owner; PtyProcess.__init__ calls _UnixPty(self) / _ConPty(self) |

### framework-fixed-signature:progress-adapter（1 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/pack/wiki/lint.py:275` | `total` | param | advance(done, total) is the pool progress adapter contract; `del total` explicitly marks the ignored argument |

### framework-fixed-signature:scenario-driver（4 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/screenshots/scenarios.py:137` | `fixtures` | param | Scenario.driver has the fixed (svg_path, fixtures) signature; other drivers consume fixtures |
| `tools/screenshots/scenarios.py:334` | `fixtures` | param | Scenario.driver has the fixed (svg_path, fixtures) signature; other drivers consume fixtures |
| `tools/screenshots/scenarios.py:471` | `fixtures` | param | Scenario.driver has the fixed (svg_path, fixtures) signature; other drivers consume fixtures |
| `tools/screenshots/scenarios.py:476` | `fixtures` | param | Scenario.driver has the fixed (svg_path, fixtures) signature; other drivers consume fixtures |

### intentional-ignore（1 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/yxp/example/hello_yxp/hello_yxp.py:20` | `_args` | param | `_*` prefix marks deliberate ignoring of a fixed signature |

### internal-callback-fixed-signature（2 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/flows/file_manager_flows.py:165` | `value` | param | callback is injected into a symmetric handler family / workspace subscription whose other members use the same signature |
| `yate/flows/mouse_flows.py:108` | `view` | param | callback is injected into a symmetric handler family / workspace subscription whose other members use the same signature |

### open-api:cli-surface（1 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/pack/wiki/run.py:198` | `force` | param | wiki run() is the public CLI surface; callers pass force=... by keyword |

### override（3 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/manual.py:265` | `container` | param | pyright reportImplicitOverride requires signature parity |
| `yate/editor_components/manual.py:265` | `viewport` | param | pyright reportImplicitOverride requires signature parity |
| `yate/editor_components/manual.py:265` | `width` | param | pyright reportImplicitOverride requires signature parity |

### protocol（6 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/view.py:63` | `leaf_id` | param | signature is the protocol contract (R2 frozen whitelist) |
| `yate/editor_components/view.py:67` | `leaf_id` | param | signature is the protocol contract (R2 frozen whitelist) |
| `yate/editor_components/view.py:70` | `leaf_id` | param | signature is the protocol contract (R2 frozen whitelist) |
| `yate/editor_syntax/engine.py:41` | `filetype` | param | signature is the protocol contract (R2 frozen whitelist) |
| `yate/editor_syntax/engine.py:45` | `lines` | param | signature is the protocol contract (R2 frozen whitelist) |
| `yate/editor_syntax/engine.py:45` | `filetype` | param | signature is the protocol contract (R2 frozen whitelist) |

### protocol:host-mirror（16 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/highlighting.py:115` | `repaint` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:115` | `layout` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:115` | `recompose` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:115` | `regions` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:125` | `delay` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:125` | `callback` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:125` | `name` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:125` | `pause` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `work` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `name` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `group` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `description` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `exit_on_error` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `start` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `exclusive` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |
| `yate/editor_components/highlighting.py:136` | `thread` | param | HighlightMixin mirrors Textual Widget.refresh / set_timer / run_worker; the signature is the host protocol (R2 whitelist) |

### pytest-fixture（112 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tests/conftest.py:239` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_app_file_manager.py:222` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_app_find.py:1134` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_app_find_replace.py:424` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_app_lsp.py:177` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:728` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:744` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:755` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:772` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:791` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:809` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:825` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:857` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:906` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:953` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:972` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:995` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:1008` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:1030` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:1140` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_changelog_tool.py:1159` | `stub_gitdata` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_cli.py:448` | `_custom_theme_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_cli.py:470` | `_custom_theme_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_crash.py:137` | `crash_state` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_crash.py:160` | `crash_state` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_crash.py:182` | `crash_state` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_crash.py:261` | `crash_state` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_editor_core.py:665` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_events.py:359` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_explorer.py:351` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:149` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:162` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:180` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:200` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:223` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:253` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_extension_examples.py:262` | `clean_registries` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_fonts.py:455` | `fake_winreg` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_fonts.py:849` | `fake_winreg` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_fonts.py:896` | `fake_winreg` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_highlight.py:194` | `clean_custom_language` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_input_assist.py:801` | `empty_clipboard` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_input_assist.py:812` | `empty_clipboard` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_lsp.py:1066` | `session` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_lsp.py:2213` | `session` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_lsp.py:2425` | `session` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_lua_extensions.py:510` | `bundle` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_lua_extensions.py:787` | `bundle` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_pack_wiki.py:248` | `capsys` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_pack_wiki.py:342` | `repo` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_pack_wiki.py:533` | `repo` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_pack_wiki_errors.py:231` | `cli_repo` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_paths.py:17` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_paths.py:25` | `monkeypatch` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_paths.py:25` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_smoke_harness.py:163` | `restore_theme` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_smoke_harness.py:175` | `restore_theme` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_support_mouse.py:194` | `tmp_path` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_terminal.py:378` | `fake_pty` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_terminal.py:395` | `fake_pty` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:103` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:109` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:114` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:121` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:130` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:144` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:156` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:192` | `template_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:236` | `template_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:252` | `template_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:267` | `template_cleanup` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:308` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:347` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:360` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:365` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:370` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:376` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:383` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:392` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:401` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:411` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:422` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:432` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:449` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:481` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_palettes.py:486` | `builtin_baseline` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_trust.py:49` | `trust_store` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_trust.py:66` | `trust_store` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_trust.py:80` | `trust_store` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_trust.py:92` | `trust_store` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_theme_trust.py:106` | `trust_store` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:73` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:91` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:113` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:124` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:138` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:157` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:166` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:176` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:186` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:191` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:205` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:224` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:236` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:249` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:263` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:295` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:313` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:329` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:346` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_tracing.py:362` | `isolated_home` | param | pytest injects by parameter name; removing kills side effects |
| `tests/test_vim_keymap.py:1616` | `fake_clip` | param | pytest injects by parameter name; removing kills side effects |

### semantic-store:global（1 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/smoke_test/harness.py:114` | `_seed` | local | store has structural or side-effect meaning |

### semantic-store:loop_target（90 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/find_replace.py:500` | `_match` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:698` | `_col` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:698` | `_length` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:727` | `_c` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:727` | `_l` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:206` | `_h` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:206` | `_p` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:234` | `_display` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:234` | `_hint` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:234` | `_payload` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:272` | `_payload` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:306` | `_score` | local | store has structural or side-effect meaning |
| `yate/editor_components/welcome.py:102` | `_centered` | local | store has structural or side-effect meaning |
| `yate/editor_core/diff.py:133` | `_end` | local | store has structural or side-effect meaning |
| `yate/editor_core/diff.py:133` | `_j1` | local | store has structural or side-effect meaning |
| `yate/editor_core/diff.py:133` | `_j2` | local | store has structural or side-effect meaning |
| `yate/editor_core/diff.py:153` | `_end` | local | store has structural or side-effect meaning |
| `yate/editor_lsp/manager.py:224` | `_root` | local | store has structural or side-effect meaning |
| `yate/editor_lsp/manager.py:254` | `_root` | local | store has structural or side-effect meaning |
| `yate/services/extensions/bridges.py:642` | `_seq` | local | store has structural or side-effect meaning |
| `yate/session.py:370` | `_child` | local | store has structural or side-effect meaning |
| `yate/session.py:370` | `_size` | local | store has structural or side-effect meaning |
| `tests/lua_game_harness.py:220` | `_key` | local | store has structural or side-effect meaning |
| `tests/lua_game_harness.py:220` | `_unused` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:435` | `_args` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:435` | `_kwargs` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:465` | `_desc` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:465` | `_name` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:561` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:561` | `_k` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:561` | `_n` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:567` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:567` | `_k` | local | store has structural or side-effect meaning |
| `tests/test_app_explorer.py:567` | `_n` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:224` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:249` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:225` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:250` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_app_manual.py:348` | `_col` | local | store has structural or side-effect meaning |
| `tests/test_app_manual.py:348` | `_length` | local | store has structural or side-effect meaning |
| `tests/test_app_manual.py:360` | `_col` | local | store has structural or side-effect meaning |
| `tests/test_app_manual.py:360` | `_length` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:113` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:113` | `_hint` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:113` | `_p` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:158` | `_hint` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:158` | `_payload` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:116` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:116` | `_hint` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:116` | `_p` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:166` | `_hint` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:166` | `_payload` | local | store has structural or side-effect meaning |
| `tests/test_canvas_screen.py:88` | `_style` | local | store has structural or side-effect meaning |
| `tests/test_canvas_screen.py:95` | `_style` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:49` | `_e` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:49` | `_s` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:60` | `_e` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:60` | `_s` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:79` | `_e` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:79` | `_s` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:101` | `_f` | local | store has structural or side-effect meaning |
| `tests/test_chrome.py:101` | `_i` | local | store has structural or side-effect meaning |
| `tests/test_explorer.py:91` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_file_manager_flows.py:184` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_file_manager_flows.py:279` | `_kind` | local | store has structural or side-effect meaning |
| `tests/test_lua_tetris.py:282` | `_batch` | local | store has structural or side-effect meaning |
| `tests/test_lua_tetris.py:300` | `_batch` | local | store has structural or side-effect meaning |
| `tests/test_lua_tetris.py:389` | `_batch` | local | store has structural or side-effect meaning |
| `tests/test_mdlint_parallel.py:156` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_mdlint_parallel.py:194` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_mdlint_parallel.py:172` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_mdlint_parallel.py:208` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_lint.py:273` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_lint.py:307` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_lint.py:287` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_lint.py:320` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_parallel.py:368` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_parallel.py:452` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_parallel.py:399` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_pack_wiki_parallel.py:483` | `_lang` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:71` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:71` | `_p` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:121` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:121` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:76` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:76` | `_p` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:126` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:126` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_welcome.py:48` | `_rest` | local | store has structural or side-effect meaning |
| `tests/test_whichkey_flows.py:372` | `_desc` | local | store has structural or side-effect meaning |

### semantic-store:nonlocal（5 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tests/test_app_find_replace.py:1074` | `resolve_calls` | local | store has structural or side-effect meaning |
| `tests/test_app_render.py:231` | `calls` | local | store has structural or side-effect meaning |
| `tests/test_canvas_screen.py:233` | `calls` | local | store has structural or side-effect meaning |
| `tests/test_chunked.py:52` | `disk_reads` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:245` | `resolve_calls` | local | store has structural or side-effect meaning |

### semantic-store:unpack（349 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/editor_components/file_manager/screen.py:456` | `_parent` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:727` | `_col` | local | store has structural or side-effect meaning |
| `yate/editor_components/manual.py:727` | `_length` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:358` | `_hits` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:358` | `_score` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:530` | `_display` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:530` | `_hint` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:530` | `_hits` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:530` | `_kind` | local | store has structural or side-effect meaning |
| `yate/editor_components/palette.py:530` | `_score` | local | store has structural or side-effect meaning |
| `yate/editor_syntax/engine.py:196` | `_row_tokens` | local | store has structural or side-effect meaning |
| `yate/editor_syntax/regex_backend.py:106` | `_close` | local | store has structural or side-effect meaning |
| `yate/flows/completion_flows.py:186` | `_start_col` | local | store has structural or side-effect meaning |
| `yate/flows/completion_flows.py:351` | `_start` | local | store has structural or side-effect meaning |
| `tools/smoke_test/scenarios/regression.py:139` | `_end` | local | store has structural or side-effect meaning |
| `tests/lua_game_harness.py:267` | `_description` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:157` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:170` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:182` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:193` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:207` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:223` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:238` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:250` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:264` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:281` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:291` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:308` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:322` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:338` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:447` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:457` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_action_table.py:465` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_app_find.py:701` | `_col` | local | store has structural or side-effect meaning |
| `tests/test_app_find.py:707` | `_col` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:79` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:79` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:99` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:99` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:121` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:121` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:138` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:138` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:167` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:198` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:224` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:286` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:286` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:311` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:311` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:326` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:326` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:348` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:348` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:372` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:372` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:823` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:823` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:841` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:841` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:864` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:864` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:894` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:894` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:921` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:921` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:969` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:969` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:989` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:989` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1022` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1022` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1048` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1048` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:80` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:80` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:100` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:100` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:122` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:122` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:139` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:139` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:168` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:200` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:225` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:287` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:287` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:312` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:312` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:327` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:327` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:349` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:349` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:373` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:373` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:825` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:825` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:843` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:843` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:872` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:872` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:901` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:901` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:929` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:929` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:972` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:972` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:993` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:993` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1024` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1024` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1056` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_app_find_replace.py:1056` | `_notices` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:202` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:249` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:249` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:203` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:253` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_mouse.py:253` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_palette.py:196` | `_score` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:507` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:553` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:553` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:594` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:594` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:512` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:559` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:559` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:599` | `_right_view` | local | store has structural or side-effect meaning |
| `tests/test_app_panes.py:599` | `_split` | local | store has structural or side-effect meaning |
| `tests/test_changelog_view.py:179` | `_callback` | local | store has structural or side-effect meaning |
| `tests/test_cli.py:583` | `_out` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:355` | `_start` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:370` | `_start` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:384` | `_prefix` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:384` | `_start` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:413` | `_start` | local | store has structural or side-effect meaning |
| `tests/test_completion_popup.py:419` | `_start` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:105` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:105` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:124` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:124` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:145` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:145` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:177` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:177` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:203` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:203` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:218` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:218` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:231` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:231` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:251` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:251` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:271` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:271` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:290` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:290` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:303` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:303` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:315` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:315` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:334` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:334` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:356` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:356` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:367` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:367` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:367` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:373` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:373` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:373` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:385` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:385` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:401` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:401` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:417` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:417` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:431` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:452` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:452` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:472` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:472` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:486` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:486` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:510` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:510` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:521` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:521` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:521` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:527` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:527` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:539` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:539` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:559` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:559` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:559` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:580` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:580` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:580` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:596` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:596` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extension_api.py:596` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:457` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:457` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:487` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:487` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:543` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:543` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:559` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:559` | `_keymaps` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:575` | `_actions` | local | store has structural or side-effect meaning |
| `tests/test_extensions.py:575` | `_commands` | local | store has structural or side-effect meaning |
| `tests/test_fonts.py:365` | `_skipped` | local | store has structural or side-effect meaning |
| `tests/test_fonts.py:455` | `_skipped` | local | store has structural or side-effect meaning |
| `tests/test_fonts.py:471` | `_skipped` | local | store has structural or side-effect meaning |
| `tests/test_highlighting.py:189` | `_state` | local | store has structural or side-effect meaning |
| `tests/test_highlighting.py:208` | `_states` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:74` | `_handler` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:74` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:84` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:96` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:108` | `_description` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:108` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:122` | `_description` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:122` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:137` | `_description` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:137` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:149` | `_description` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:149` | `_runtime` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:164` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:184` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:199` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:210` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:264` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:281` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_engine.py:300` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:23` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:35` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:49` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:62` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:75` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_lua_layout.py:91` | `_api` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:172` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:172` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:177` | `_d` | local | store has structural or side-effect meaning |
| `tests/test_palette.py:177` | `_h` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:70` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:70` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:85` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:85` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:132` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:187` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:187` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:187` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:202` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:202` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:202` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:246` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:246` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:262` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:276` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:276` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:276` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:308` | `_bottom` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:308` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:308` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:365` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:374` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:385` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:394` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:71` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:71` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:86` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:86` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:133` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:188` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:188` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:188` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:203` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:203` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:203` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:247` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:247` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:263` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:277` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:277` | `_doc2` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:277` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:309` | `_bottom` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:309` | `_doc1` | local | store has structural or side-effect meaning |
| `tests/test_panes.py:309` | `_session` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:201` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:228` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:261` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:273` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:316` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:358` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:388` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:409` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:442` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:505` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:204` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:233` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:264` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:278` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:321` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:361` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:393` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:414` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:447` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_pty_proc.py:510` | `_impl` | local | store has structural or side-effect meaning |
| `tests/test_set_options.py:45` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:103` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:103` | `_prompt` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:103` | `_spawn` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:128` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:128` | `_mounted` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:128` | `_overlay` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:128` | `_prompt` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:128` | `_spawn` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:139` | `_messages` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:139` | `_mounted` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:139` | `_overlay` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:151` | `_mounted` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:151` | `_overlay` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:151` | `_prompt` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:162` | `_mounted` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:162` | `_overlay` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:162` | `_prompt` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:187` | `_mounted` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:187` | `_overlay` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:187` | `_prompt` | local | store has structural or side-effect meaning |
| `tests/test_shell_flows.py:187` | `_spawn` | local | store has structural or side-effect meaning |
| `tests/test_support_mouse.py:85` | `_text` | local | store has structural or side-effect meaning |
| `tests/test_support_mouse.py:86` | `_text` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1504` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1874` | `_ctx` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1874` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1880` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1891` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1908` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1916` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1924` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1943` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1953` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1965` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1975` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_vim_keymap.py:1997` | `_editor` | local | store has structural or side-effect meaning |
| `tests/test_welcome.py:66` | `_color` | local | store has structural or side-effect meaning |

### test-stub-signature（399 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tests/lua_game_harness.py:69` | `palette` | param | monkeypatch stub / callback fixed by caller |
| `tests/lua_game_harness.py:164` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/lua_game_harness.py:168` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_find_replace.py:1000` | `limit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_idle.py:50` | `_interval` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:564` | `method` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:564` | `params` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:568` | `method` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:568` | `params` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:574` | `request_id` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:578` | `request_id` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:246` | `method` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:246` | `params` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:250` | `method` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:250` | `params` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:257` | `request_id` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_lsp.py:261` | `request_id` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_manual.py:725` | `kind` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_manual.py:725` | `lang` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_manual.py:770` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_manual.py:770` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_palette.py:355` | `limit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_palette.py:120` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_palette.py:123` | `ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_render.py:588` | `a` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_render.py:599` | `a` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_textual.py:1389` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_textual.py:1410` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_textual.py:460` | `doc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_app_textual.py:460` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_architecture.py:1093` | `sender` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_canvas_screen.py:70` | `_result` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_canvas_screen.py:233` | `_key` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:356` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:363` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:404` | `request` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:404` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:704` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:704` | `include_merges` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:704` | `limit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:709` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:712` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:715` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:718` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:816` | `_a` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:816` | `_k` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:934` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:934` | `prefix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:937` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:937` | `sha` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1014` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1014` | `include_merges` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1036` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1036` | `include_merges` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1144` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1149` | `remote` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1149` | `shas` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1163` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1168` | `remote` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_tool.py:1168` | `shas` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_view.py:111` | `_parts` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_view.py:98` | `encoding` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_changelog_view.py:106` | `_parts` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_chrome.py:187` | `layout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_cmd_cd.py:77` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_cmd_cd.py:77` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_cmd_cd.py:304` | `prefix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_cmd_cd.py:304` | `workspace` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_cmdline_completions.py:45` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_completion_popup.py:498` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_completion_popup.py:498` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_completion_popup.py:504` | `_doc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_completion_popup.py:507` | `_doc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_completion_popup.py:510` | `_doc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:78` | `with_self` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:216` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:231` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:243` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:316` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_conftest_wait_diagnosis.py:284` | `with_self` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_data_store.py:75` | `target` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_document_chunked.py:52` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_document_chunked.py:271` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_document_chunked.py:336` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_document_flows_saveas.py:191` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_editor_core.py:824` | `half` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_editor_core.py:843` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_editor_core.py:843` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_editor_sprites.py:180` | `order` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_events.py:89` | `_payload` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_events.py:105` | `_text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_events.py:117` | `_payload` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_events.py:73` | `_payload` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_events.py:112` | `_payload` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_explorer.py:53` | `placeholder` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_explorer.py:53` | `initial` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_explorer.py:53` | `on_submit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_explorer.py:53` | `refocus` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:97` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:111` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:129` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:149` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:158` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:182` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:222` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:235` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:259` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:275` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:278` | `_prefix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_api.py:294` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_bridges.py:339` | `_text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_bridges.py:468` | `_key` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_bridges.py:525` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_bridges.py:525` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_flows.py:27` | `_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_flows.py:32` | `_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extension_flows.py:44` | `exclude` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:307` | `_api` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:466` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:491` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:548` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:565` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_extensions.py:580` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:40` | `exc_info` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:69` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:87` | `reserved` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:87` | `kind` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:316` | `_name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:488` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:703` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_fonts.py:703` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:463` | `screen` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:463` | `callback` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:842` | `write_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:842` | `write_edits` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:842` | `write_mtime` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:842` | `write_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:875` | `write_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:875` | `write_edits` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:875` | `write_mtime` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:875` | `write_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:895` | `write_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:895` | `write_edits` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:146` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_hex_view.py:146` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_input_assist.py:115` | `_text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_key_notation.py:381` | `_name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lsp.py:1331` | `name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lsp.py:1402` | `name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lsp.py:1435` | `method` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lsp.py:1435` | `params` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_engine.py:66` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_extensions.py:630` | `name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_extensions.py:691` | `_ctx` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_extensions.py:884` | `_text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_extensions.py:1027` | `index` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_lua_extensions.py:1077` | `_prefix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_manual.py:44` | `_screen` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint.py:105` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint.py:129` | `argv` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint.py:203` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint.py:220` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:100` | `items` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:100` | `fix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:117` | `items` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:117` | `fix` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:141` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:144` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:169` | `max_workers` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:169` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:172` | `fn` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:205` | `max_workers` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:205` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:208` | `fn` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:215` | `wait` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_mdlint_parallel.py:215` | `cancel_futures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:393` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:393` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:52` | `callback` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:121` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:121` | `mode` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:145` | `offset` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_overlay_flows_hex.py:145` | `length` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:136` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:136` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:158` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:188` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:212` | `lang` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:217` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:217` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:226` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:226` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:235` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:263` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:263` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:285` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:285` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:310` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:310` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:326` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:326` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:377` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:377` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:394` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:414` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:430` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:445` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:470` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:470` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:478` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:478` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:494` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:506` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:512` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:615` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:615` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:639` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:639` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:658` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:658` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:702` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:702` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:759` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:759` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:778` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:834` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:834` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:847` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki.py:847` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:61` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:296` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:326` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:326` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:343` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:343` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:498` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:498` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:591` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:591` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:704` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:766` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:766` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:942` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:942` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_errors.py:959` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:73` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:73` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:170` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:248` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:248` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:287` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_lint.py:320` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:184` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:221` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:225` | `cores` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:254` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:266` | `cores` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:284` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:312` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:346` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:346` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:382` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:399` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:436` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:475` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:483` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:517` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:577` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:577` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:622` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:670` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:670` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:703` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:737` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:746` | `timeout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:766` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:766` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:824` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:882` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:922` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:957` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:957` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:996` | `text` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pack_wiki_parallel.py:996` | `translate_cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_palette_preview.py:403` | `_kw` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_palette_preview.py:456` | `lines` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_palette_preview.py:456` | `filetype` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_palette_preview.py:495` | `_screen` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_palette_preview.py:495` | `_kw` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:435` | `callback` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:435` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:790` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:985` | `_h` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:985` | `_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:985` | `_ov` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:997` | `_h` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:1016` | `_attrs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:1016` | `_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:462` | `_code` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:700` | `buf` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:700` | `n` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:700` | `written` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:700` | `_ov` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:706` | `hpc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:749` | `buf` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:749` | `n` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:749` | `written` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:749` | `_ov` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:758` | `hpc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:830` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:925` | `_exc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:934` | `_read` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:934` | `_write` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:934` | `_attrs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:934` | `_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:939` | `_size` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:939` | `_in_read` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:939` | `_out_write` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:939` | `_flags` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:939` | `_hpc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_pty_proc.py:950` | `_handle` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_python_lsp_ext.py:63` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_registries.py:175` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:87` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:122` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:122` | `files` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:125` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:128` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:131` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:134` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:134` | `dry_run` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:161` | `dry_run` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:161` | `no_push` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:318` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:321` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:390` | `repo` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_release_tool.py:390` | `dry_run` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:27` | `svg_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:27` | `fixtures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:131` | `fixtures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:134` | `svg_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:134` | `fixtures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:187` | `fixtures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_screenshots_tool.py:208` | `fixtures` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:138` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:184` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:184` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:187` | `_proc` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:250` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:250` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:396` | `_pgid` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:396` | `_sig` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shell.py:399` | `_pid` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_shells.py:28` | `_name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_smoke_tool.py:133` | `tmp` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_smoke_tool.py:138` | `tmp` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_smoke_tool.py:31` | `tmp` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_syntax_engine.py:41` | `filetype` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_syntax_engine.py:209` | `_pointer` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_syntax_engine.py:214` | `_language` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_syntax_engine.py:214` | `_source` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_syntax_engine.py:223` | `_pointer` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:428` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:428` | `cols` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:428` | `rows` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:431` | `on_output` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:431` | `on_exit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:443` | `cwd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:443` | `cols` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:443` | `rows` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:446` | `on_output` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_terminal.py:446` | `on_exit` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_translate.py:66` | `cmd` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_translate.py:228` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_translate.py:228` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_translate.py:265` | `args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_translate.py:265` | `kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_yxp.py:120` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tools_yxp.py:318` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_tracing.py:368` | `_handle` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_trust.py:117` | `target` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_trust.py:117` | `mode` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_ts_backend.py:875` | `_path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_ts_backend.py:398` | `_name` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_whichkey_panel.py:259` | `layout` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:27` | `_args` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:27` | `_kwargs` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:793` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:796` | `_self` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:796` | `_directory` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_workspace_filter.py:851` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:363` | `records` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:363` | `package` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:382` | `records` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:382` | `package` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:409` | `path` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:436` | `src` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:436` | `dst` | param | monkeypatch stub / callback fixed by caller |
| `tests/test_yxp.py:670` | `mode` | param | monkeypatch stub / callback fixed by caller |

### test-stub-signature:monkeypatch（2 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `tools/smoke_test/scenarios/view.py:219` | `args` | param | *args/**kwargs stub must accept any positional and keyword call |
| `tools/smoke_test/scenarios/view.py:219` | `kwargs` | param | *args/**kwargs stub must accept any positional and keyword call |

### unpack-placeholder（215 条）

| 文件:行号 | 名称 | 种类 | 保留理由 |
| --- | --- | --- | --- |
| `yate/cmdline_completions.py:37` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/commands.py:198` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/commands.py:260` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/commands.py:201` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/commands.py:411` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_components/file_manager/model.py:158` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_components/preview.py:81` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/buffer.py:927` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/buffer.py:955` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/buffer.py:1302` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/buffer.py:1318` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/buffer.py:1337` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/chunked.py:137` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/document.py:103` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_core/textobjects.py:196` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_sprites/characters.py:200` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/regex_backend.py:440` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/ts_backend/backend.py:65` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/ts_backend/backend.py:73` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/ts_backend/backend.py:318` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/ts_backend/backend.py:438` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_syntax/ts_backend/backend.py:492` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:145` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:148` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:162` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:430` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:442` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:572` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:612` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:632` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:640` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:656` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:666` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:676` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:681` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/editor_term/emulator.py:757` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/flows/completion_flows.py:307` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/keymaps/vim.py:504` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/keymaps/vim.py:732` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/keymaps/vim.py:745` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/keymaps/vim.py:1322` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/services/extensions/api.py:71` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/services/fonts.py:85` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/services/fonts.py:199` | `_` | local | `_` consumes a tuple/iterator slot |
| `yate/services/fonts.py:424` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/changelog/gitdata.py:119` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/mdlint/batch.py:192` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/mdlint/cli.py:210` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/probes/pb6_real_input_harness.py:157` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/probes/pb6_real_input_harness.py:207` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/probes/pb6_real_input_harness.py:246` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/cli.py:166` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/explorer.py:21` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/explorer.py:87` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/file_manager.py:51` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/regression.py:139` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/stress.py:39` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/stress.py:68` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/stress.py:94` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/stress.py:210` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/smoke_test/scenarios/workspace_nav.py:219` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/yxp/cli.py:211` | `_` | local | `_` consumes a tuple/iterator slot |
| `tools/yxp/cli.py:336` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/lua_game_harness.py:207` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/lua_game_harness.py:291` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:283` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:463` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:529` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:591` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:287` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:464` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:534` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_explorer.py:595` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_file_manager.py:160` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_file_manager.py:168` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find.py:758` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find.py:1134` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find.py:759` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find.py:1139` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find_replace.py:921` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_find_replace.py:929` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_manual.py:584` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_manual.py:588` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_mouse.py:92` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_mouse.py:101` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_panes.py:332` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_terminal.py:361` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_terminal.py:120` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_terminal.py:367` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_textual.py:999` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_textual.py:1281` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_app_textual.py:1002` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_chrome.py:60` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:573` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:583` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:599` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:616` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:628` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_cli.py:639` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_crash.py:182` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_core.py:689` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_core.py:1349` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_sprites.py:114` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_sprites.py:143` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_sprites.py:150` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_editor_sprites.py:188` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_extension_examples.py:200` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_file_manager.py:125` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_fonts.py:646` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_fonts.py:716` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_fonts.py:733` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_hex_view.py:528` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_hex_view.py:753` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_hex_view.py:913` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_hex_view.py:756` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_hex_view.py:922` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_highlight.py:242` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_highlight.py:597` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_input_assist.py:969` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_keyproto.py:153` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_keyproto.py:174` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_keyproto.py:194` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_keyproto.py:225` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:294` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:483` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:775` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1149` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1268` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1491` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1544` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1620` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1901` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1953` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2009` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2168` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2213` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2255` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2287` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2425` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:298` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:487` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:778` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1156` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1274` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1497` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1550` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1623` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1916` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:1961` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2017` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2173` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2218` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2260` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2293` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp.py:2430` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp_diff.py:106` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp_diff.py:114` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lsp_diff.py:132` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_game_nethack.py:45` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_game_nethack.py:201` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_game_nethack.py:252` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_game_pacman.py:52` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_tetris.py:320` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_lua_tetris.py:373` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_mdlint.py:48` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_pack_spec.py:551` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_panes.py:276` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_panes.py:277` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_project_search.py:286` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:139` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:251` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:270` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:314` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:373` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:150` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:254` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:281` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:327` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_screensaver.py:383` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_set_options.py:143` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_set_options.py:177` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:136` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:163` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:175` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:194` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:201` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:209` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_smoke_harness.py:391` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_syntax_engine.py:330` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_syntax_engine.py:398` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_syntax_engine.py:428` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_syntax_engine.py:453` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_terminal.py:134` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_terminal_emulator.py:851` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_tools_yxp.py:28` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_tools_yxp.py:41` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_ts_backend.py:1130` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_ts_backend.py:1134` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_ts_backend.py:1173` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_vim_keymap.py:1143` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_vim_keymap.py:1153` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_vim_keymap.py:1163` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_vim_keymap.py:1172` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_flows.py:113` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_flows.py:197` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_flows.py:237` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_flows.py:248` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_flows.py:266` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_panel.py:188` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_panel.py:306` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_panel.py:191` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_whichkey_panel.py:315` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_workspace_filter.py:182` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_workspace_filter.py:867` | `_` | local | `_` consumes a tuple/iterator slot |
| `tests/test_yxp.py:907` | `_` | local | `_` consumes a tuple/iterator slot |

