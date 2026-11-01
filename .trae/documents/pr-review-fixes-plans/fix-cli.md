# 子计划 fix-cli — m1 字面量 + m2 空转用例 + m6 CLI 校验缺口 + m7 手册补行

**Worktree 根**：`D:\Programming\yate-file-manager`（分支 `feat/file-manager`）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 m1 / m2 / m6 / m7
（先读对应小节全文）。

## 独占文件

- `yate/commands.py`
- `tests/test_cmd_cd.py`
- `yate/flows/filemanager_flows.py`
- `yate/cli.py`
- m6 的 CLI 校验用例文件：先 `grep -rn "_validate_file_manager_args" tests/` 定位（可能在
  `tests/test_app_filemgr.py` 或 `tests/test_cli.py`），该文件归本批独占。
- `yate/resources/manual.en.md`
- `yate/resources/manual.zh.md`

## 修改点

### m1（minor）— 目录过滤字面量错误

`yate/commands.py:245-248`：`c.endswith(("/", "\""))` 中第二个元素实为双引号字符，且为死
分支（`path_matches` 目录候选恒以 `/` 结尾，盘符候选由后续循环单独追加）。改为：

```python
# ``path_matches`` marks every directory candidate with a trailing "/"
# on every platform; files never carry it.
dirs = [c for c in matches if c.endswith("/")]
```

### m2（minor）— 空转用例矫正（先红后绿的证据链）

`tests/test_cmd_cd.py:264-274`：`completer("")` / `completer("d")` 在文件创建**之前**求值，
`"afile.txt" not in empty` 恒真。修法：

1. **先改测试**：把 `write_text` 提到求值之前，并补断言 `"afile.txt" not in completer("a")`；
   此时跑该用例应**红**（m1 的字面量缺陷 + 文件候选漏过滤被抓出）——记录红证据。
2. **再修实现**（m1）转绿。

### m6（minor）— `--file-manager` 校验缺口

- `yate/flows/filemanager_flows.py:99-103`：`open_fullscreen` 现只判
  `initial_dir.exists()`；改为目录判定（`initial_dir.is_dir()`，可复用
  `yate/flows/document_flows.py` 模块级 `_probe_is_dir` 语义，经 flows 层允许的导入方式；
  若跨模块导入不便则就地 `try: initial_dir.is_dir()` 实现同等判定）。非目录时经 flows
  既有消息通路报 `not a directory: <path>`（error 级）并直接返回，不再把文件路径当 cwd
  入屏。注意 flows 不持 App 句柄的边界不变。
- `yate/cli.py:283-291`（`_validate_file_manager_args`）：补互斥矩阵——
  `if args.diff_files: parser.error(...)`、`if args.hex_file: parser.error(...)`，
  文案与既有 `_validate_diff_args` / `_validate_hex_args` 口径一致（argparse exit 2）。
- 用例：非目录路径启动被拒（错误消息含路径）；`--file-manager --diff a b` 与
  `--file-manager --hex x` 各自 `SystemExit(2)`。

### m7（minor）— 应用内手册补两行（双语）

- `yate/resources/manual.en.md`：命令表补
  `` | `:file-manager` | — | open the lf-style file manager overlay (Alt+Shift+F) | ``；
  键位表补 `Alt+Shift+F` 行。以表内现有行格式/列宽为准（先读邻近行）。
- `yate/resources/manual.zh.md`：`:701` 附近命令表、`:432` 附近键位表，同步中文行
  （描述措辞对照 zh 表内既有风格）。

## 自测

`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（0 诊断）+
`.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py <m6用例文件> -q`（全绿，按退出码判定；
m6 用例文件以 grep 定位为准）。

## 执行纪律

- 禁触碰其他文件（`filemgr.py` / `workspace.py` 等由并行批次负责）。
- m2 红证据写进汇报；完成后**不提交**，汇报：改动文件、diff 要点、红证据、自测退出码。
