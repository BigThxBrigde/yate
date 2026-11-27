# 波次 1 子计划 A：`keyproto/legacy.py` -> `key_codec.py`

索引：[overview.md](overview.md) | 主计划：[../iktbxc-plan.md](../iktbxc-plan.md)
事实：[../iktbxc-reference-inventory.md](../iktbxc-reference-inventory.md) §B。

以下所有路径均相对仓库根（命令基准）。每次编辑前必须先 `read_file` 精确区域；**不做盲目全局替换**。

## 1. 输入 / 输出

输入：`yate/keyproto/legacy.py`（唯一活跃的 Textual 按键名 -> 原始字节编解码器）、9 处活跃引用、1 行规则、3 行架构 wiki。
输出：重命名后的模块 `yate/keyproto/key_codec.py`，其 docstring 说明 "legacy" 指的是终端按键命名体系，而非弃用层；所有活跃引用已更新；零运行时行为变更。
独立提交：`refactor(keyproto): rename legacy key codec to key_codec`。

## 2. 独占文件清单

- `yate/keyproto/legacy.py` -> `yate/keyproto/key_codec.py`（`git mv`）
- `yate/app.py`、`yate/editor_dispatch.py`、`yate/editor_term/keys.py`、`yate/keyproto/__init__.py`
- `tests/test_app_textual.py`、`tests/test_term_keys.py`、`tests/test_keyproto.py`
- `.trae/rules/architecture-boundaries.md`
- `.trae/wikis/yate-architecture.md`

明确未触碰：`.trae/documents/**` 历史计划、`.trae/reviews/**`、`CHANGELOG*`、`tools/changelog/zh_overrides.json`、`tests/test_architecture.py`（由 wave 2 和 3 负责）、P2 文件。

## 3. 步骤

### 步骤 A1 —— 基线（只读）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py tests/test_term_keys.py tests/test_app_textual.py -q
```

预期：退出码 0（编辑前 37 个架构用例全绿）。

### 步骤 A2 —— 重命名

```powershell
git mv yate/keyproto/legacy.py yate/keyproto/key_codec.py
```

绝不删除+创建。核实 `git status --short` 显示重命名（`R`）。

### 步骤 A3 —— 重写模块 docstring（新文件前 7 行）

把旧的首行 "Legacy key codec: ..." 与 "Formerly ..." 段落替换为：

```python
"""Current key codec for legacy terminal key names.

Translates Textual key names into the raw byte sequences yate keymaps use
(control codes / ANSI escape sequences).  "Legacy" here describes the
terminal key-name system those bytes come from, not a deprecated module:
this is the only active codec, shared by the keymaps, the driver layer and
the app from the L0 leaf package.

Formerly ``yate.editor_components.keys``; moved into the L0 leaf package so
keymaps, the driver layer and the app can share one codec without touching
the component package.
"""
```

纯 ASCII 英文（misc-rules.md §四）。docstring 以下的代码不变。

### 步骤 A4 —— 精确字符串编辑（先读每个区域）

| 文件:行 | 旧字符串 | 新字符串 |
|---|---|---|
| `yate/app.py:30` | `from yate.keyproto.legacy import textual_key_to_raw` | `from yate.keyproto.key_codec import textual_key_to_raw` |
| `yate/editor_dispatch.py:23` | `from yate.keyproto.legacy import event_to_raw` | `from yate.keyproto.key_codec import event_to_raw` |
| `yate/editor_dispatch.py:123`（注释） | `keyproto.legacy maps only single-modifier alt chords` | `keyproto.key_codec maps only single-modifier alt chords` |
| `yate/editor_term/keys.py:4`（docstring） | `:func:\`yate.keyproto.legacy.modified_key_sequence\`` | `:func:\`yate.keyproto.key_codec.modified_key_sequence\`` |
| `yate/editor_term/keys.py:12` | `from yate.keyproto.legacy import modified_key_sequence` | `from yate.keyproto.key_codec import modified_key_sequence` |
| `yate/keyproto/__init__.py:13` | `- :mod:\`yate.keyproto.legacy\` -- Textual key name -> raw byte` | `- :mod:\`yate.keyproto.key_codec\` -- Textual key name -> raw byte` |
| `tests/test_app_textual.py:23` | `from yate.keyproto.legacy import event_to_raw` | `from yate.keyproto.key_codec import event_to_raw` |
| `tests/test_term_keys.py:12` | `from yate.keyproto.legacy import modified_key_sequence` | `from yate.keyproto.key_codec import modified_key_sequence` |
| `tests/test_keyproto.py:30` | `from yate.keyproto.legacy import textual_key_to_raw` | `from yate.keyproto.key_codec import textual_key_to_raw` |
| `.trae/rules/architecture-boundaries.md:47` | `keyproto/legacy.py` | `keyproto/key_codec.py` |
| `.trae/wikis/yate-architecture.md:156` | `` `legacy.py::event_to_raw` `` | `` `key_codec.py::event_to_raw` `` |
| `.trae/wikis/yate-architecture.md:184` | `yate/keyproto/legacy.py` | `yate/keyproto/key_codec.py` |
| `.trae/wikis/yate-architecture.md:194`（Mermaid） | `participant KP as keyproto/legacy<br/>event_to_raw` | `participant KP as keyproto/key_codec<br/>event_to_raw` |

import 顺序在其组内保持字母序（`python-coding-style.md` §1.3）；仅当组内含有 keyproto 其他模块时 key_codec 排在其后，因此逐个 import 块复核。

### 步骤 A5 —— 负向演练（命名守卫）

1. 向 `yate/keyproto/key_codec.py` 临时追加类 `RenameProbeController`（任意简单体，如 `pass`），保存并核对磁盘。
2. 运行 `.venv\Scripts\python.exe -m pytest tests/test_architecture.py::test_no_banned_identifier_names -q`。它必须失败（退出码 != 0），断言中点名新路径——这证明重命名后的文件仍在命名守卫的扫描根内。
3. 移除该类、核对磁盘、清理 `yate/keyproto/__pycache__` 与 `tests/__pycache__`，重跑同一测试 -> 退出码 0。`git status --short` 除预期的重命名/docstring 外，不得显示该编解码器模块的多余 diff。

### 步骤 A6 —— 验收

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py tests/test_term_keys.py tests/test_app_textual.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
git grep -n -E "keyproto\.legacy|keyproto/legacy" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

所有命令退出码 0；最后一条 `git grep` 必须不打印任何内容（"no match" 的退出码 1 是预期信号——需显式记录）。

### 步骤 A7 —— 提交与重命名检查

```powershell
git add -A
git commit -m "refactor(keyproto): rename legacy key codec to key_codec"
git --no-pager log --follow --oneline -- yate/keyproto/key_codec.py
```

`git log --follow` 必须显示该编解码器在重命名前的历史。

## 4. 风险 / 回滚

- 遗漏 docstring 路径：残余 grep + pyright + 全量 pytest 可捕获。
- `git mv` 跟踪：`git status` 重命名行 + `git log --follow` 检查。
- 回滚：`git revert <wave-1 commit>`；其他波次尚未开始。

## 5. 回填（执行期间填写）

真实命令结果、退出码、负向演练证据与偏离记录。
