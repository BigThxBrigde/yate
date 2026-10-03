# dap-support plan-b：F5→F7 迁移与文档同步（W1）

主计划依据：§5.0 事实 1 与决策 1。

## 目标

vsc 模式 ex 命令行从 F5 迁到 F7；vim 模式删除 F5 的 command_prompt 绑定
（`:` 保持唯一入口）；全部文档 F5=命令行 条目同步改写，为 plan-j 腾出 F5。

## 非目标

不新增调试键位（plan-j）；不改键位层解析（plan-a）；不动 welcome 页
（hints 不含 F5，editor_view/editor.py:766-779 已核对）。

## 独占文件清单（只改这些）

- `yate/keymaps/vsc.py` — F5 绑定 :95 改 `<f7>`，注释 :92-94 同步
  （说明 ":" 在 vsc 是普通字符，用 F7 或 alt+shift+p 进命令行）；
- `yate/keymaps/vim.py` — 删除 f5→command_prompt 绑定 :175-177；
- `yate/resources/manual.en.md` — F5 条目改 F7：行 191、341、359、561、585、1382；
- `yate/resources/manual.zh.md` — 行 182、324、341、526、545、1244；
- `README.md` — 键位表 :98（F5→F7）；
- `README.zh.md` — 键位表 :123；
- `tests/test_vsc_keymap.py`、`tests/test_vim_keymap.py` — 断言 vsc F7→
  command_prompt、vsc/vim 无 F5 绑定、vim `:` 不变。

## 实施要点

1. 帮助覆盖层由键位表自动生成，无需单独改；DBG 分类归 plan-j。
2. 手册两版行号不同，逐条改并全文 `grep "F5"` 复核无残留命令行语义
   （plan-j 阶段 F5 将重新出现在调试语境，本步验收以当前 grep 为准）。
3. README 键位表所在区块：en "Common keys (vsc keymap)" :92 起、
   zh "常用键位（vsc 键位）" :117 起。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_vsc_keymap.py tests/test_vim_keymap.py tests/test_keymap_set.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- 用户肌肉记忆冲突：手册/README 全量同步 + 命令面板双入口；评审否决则回退
  主计划 §5.0 备选 A（F5 保留给 ex 行，调试命令驱动）。
- 回滚：单 commit revert。
