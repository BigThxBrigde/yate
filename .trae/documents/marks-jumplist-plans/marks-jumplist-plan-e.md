# plan-e — 双语手册与键位文档同步 + 双语守卫（wave-3）

父文档：[overview.md](overview.md)。输入：F12；issue"备注"（双语同时新增、
同时更新）。前置：wave-1/2 全部验收通过（文档必须描述已落地行为）。

## 目标与非目标

- 目标：`yate/resources/manual.en.md` 与 `manual.zh.md` 同步补入三个新键位
  （§5.1 vsc / §5.2 vim 两张表）与四个新 ex 命令（§8）；新增双语守卫测试
  （对齐 test_macro_docs.py 先例）。
- 非目标：其它专题文档（lsp/which-key 等 md）不动；帮助浮层（f1）与 which-key
  为数据驱动自动出现（F13），无需文档代码改动（AC7 由 plan-b 的 key_label
  用例 + 手工冒烟覆盖）。

## 独占文件清单

- `yate/resources/manual.en.md`
- `yate/resources/manual.zh.md`
- `tests/test_marks_docs.py`（新建）

## 具体修改

### 1. `manual.en.md`

- §5.1 vsc keymap 表（L389 起）与 §5.2 vim keymap 表（L535 起）：各追加三行
  `<alt-left>` / `<alt-right>` / `<alt-m>`（描述与 actions.py 文案一致：
  jump back / jump forward / marks overview）。
- §8 Command Line（L738 起）：命令清单补 `:marks`、`:mark <name>`（"jump if
  set in any open buffer, else set at cursor"）、`:delmark <name>`、`:jumps`，
  含边界提示说明（非法名/空历史 warn）。
- §5 表所在键位兼容小节（"Terminal compatibility" L506 附近）核对 alt 修饰
  序列说明是否需要补 `\x1b[1;3D/C`（若已述 alt+arrow 通用机制则不重复）。

### 2. `manual.zh.md`

- 与英文逐节对应的中文新增（两语言**同时**新增，行数/结构对齐是守卫前提）。

### 3. `tests/test_marks_docs.py`（对齐 test_macro_docs.py 形态）

- 常量 `_MANUALS = (resources/manual.en.md, manual.zh.md)` 用
  `importlib.resources`/`yate.paths` 定位（不写死盘符路径，F12）。

| 用例 | 操作/断言 |
|---|---|
| `test_manual_both_languages_list_all_three_keys` | 两份手册各含 `<alt-left>`、`<alt-right>`、`<alt-m>` 至少一次且各出现在 §5 的两套表区段 |
| `test_manual_both_languages_document_marks_commands` | 两份手册各含 `:marks`、`:mark`、`:delmark`、`:jumps` |
| `test_manual_en_zh_table_rows_stay_paired` | 两语言中三键位行数相同（对齐 macro 手册的 en/zh 行配对断言） |
| `test_manual_new_lines_have_no_machine_local_paths` | 新增行（含三键与四命令的行）匹配 `[A-Za-z]:[\\/]` 为零（可移植措辞纪律） |
| `test_manual_keys_match_action_names` | 手册中 alt-left/alt-right 的动作描述与 keymap 表动作名 `jump_back`/`jump_forward` 出现同一术语（防键位与动作漂移的文档面） |

## 验证方案与验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_marks_docs.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

- 通过判定：全部退出码 0——此为整任务收尾门禁（overview"全量收尾门禁"）。
- 手工核验（文档可读性）：打开两份手册抽查新增段落双语语义一致、无占位符。

## 风险与回滚

- 风险1：双语行配对断言过脆（后续无关改动也会碰行数）→ 断言只锚定新增
  区段附近的小窗（读取 §5.1/§5.2/§8 定位符之间的文本），不做全文件行数
  相等断言。
- 风险2：手册路径若从 resources 迁移 → 用 `yate.paths`/`importlib.resources`
  解析，测试不写死目录。
- 回滚：`git checkout -- yate/resources/manual.en.md
  yate/resources/manual.zh.md` + 删除 `tests/test_marks_docs.py`；纯文档 +
  文档测试回滚，无代码牵连。
