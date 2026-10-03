# dap-support plan-k：--diag dap 诊断节（W6）

主计划依据：§7 可发现性表末行；§8.2 test_diagnostics 必改项。

## 目标

`yate --diag` 报告在 `[lsp]` 后输出 `[dap]` 节；节清单 12→13 与测试同步。

## 非目标

不改 `format_report` 骨架与既有 12 节行为；不改 cli.py 参数。

## 独占文件清单（只改这些）

- `yate/diagnostics.py` — `format_report` 局部节列表（:75-88）在 lsp 注册
  （:85）后插 `("dap", lambda: _section_dap(editor))`；新增 `_section_dap`
  （放 `_section_lsp` :380-403 后）：debugger 名单、filetypes、发现 command
  （或 `(none)`）、opt-out 状态、launch 模板键名、当前会话状态；两列缩进
  风格沿用 lsp 节；敏感值（env）掩码对齐 lsp 节做法
  （test_lsp_env_keys_are_shown_but_values_are_masked，
  [test_diagnostics.py:99-135](../../tests/test_diagnostics.py#L99-L135)）；
- `tests/test_diagnostics.py` — `_ALL_SECTIONS`（:24-27）插 `"dap"`；
  `test_report_contains_all_twelve_sections`（:45）改名/改 13；按 lsp 节
  用例样式（:96-135、:280-286）补 dap 节用例（无注册时的空态、注册后的
  名单/command/掩码）；
- `tests/test_cli.py` — `--diag` 报告含 `[dap]`（走查范式 :291-310；
  `test_diag_flag_is_store_true` :134-136 不动）。

## 实施要点

1. `--diag` 入口（[cli.py:357-375](../../yate/cli.py#L357-L375)）已加载扩展
   （:373 `register_configured_servers`），python_dap 经 setup(api) 注册后
   dap 节自然有数据，cli.py 零改动。
2. 无 editor.dap 属性的旧对象路径（diag 用假 editor）：`_section_dap` 需
   容忍缺失（getattr 卫语句），与 lsp 节同手法。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py tests/test_cli.py -q
.venv\Scripts\python.exe -m pyright yate/diagnostics.py
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- 节数硬编码测试漂移：本计划一次性把 `_ALL_SECTIONS` 改为单一事实来源，
  后续加节只改常量。
- 回滚：单 commit revert。
