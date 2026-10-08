# big-module-split 子计划总纲

主计划：[`../big-module-split-plan.md`](../big-module-split-plan.md)（issue IKK5F7）。

每波次一份子计划；波次间触碰文件互不重叠。每波收尾验收 =
该波验收命令 + `python -m pyright yate/ tests/ tools/` 零诊断；
全部波次结束后统一跑全量门禁（pytest + 覆盖率 --cov-fail-under=75）。

| 波次 | 子计划 | 新增模块 | 移出对象 |
|---|---|---|---|
| a | [big-module-split-regex-langdefs-plan-a.md](big-module-split-regex-langdefs-plan-a.md) | `editor_syntax/regex_langdefs.py` | regex_backend 语言定义段 |
| b | [big-module-split-diff-pane-plan-b.md](big-module-split-diff-pane-plan-b.md) | `editor_view/diff_pane.py` | diffview 的 Pane 侧 |
| c | [big-module-split-view-highlight-plan-c.md](big-module-split-view-highlight-plan-c.md) | `editor_view/highlighting.py`、`editor_view/welcome.py` | editor_view/editor 的高亮与欢迎页 |
| d | [big-module-split-theme-registry-plan-d.md](big-module-split-theme-registry-plan-d.md) | `editor_view/themes.py`、`cells.py`、`theme_files.py` | theme.py 数据/桥接/文件加载/几何 |
| e | [big-module-split-leaf-extracts-plan-e.md](big-module-split-leaf-extracts-plan-e.md) | `editor_core/words.py`、`editor_term/palette.py`、`editor_term/keys.py` | buffer 词运动；emulator 调色板/按键表 |
| f | [big-module-split-lsp-yaterc-plan-f.md](big-module-split-lsp-yaterc-plan-f.md) | `editor_lsp/parsing.py`、`yaterc_options.py` | manager 线格式解析；yaterc 选项校验 |

维持豁免（不拆，理由见主计划 §二）：`keymaps/vim.py`、`yate/editor.py`。
