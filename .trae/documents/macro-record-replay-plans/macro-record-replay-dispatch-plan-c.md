# 子计划 c：派发接线与组装（wave-1，主代理亲改）

> 【历史产物 · 方案已排除】本组文档记录 2026-11-11 第一轮宏录制回放方案
> （`<f6>` 单前缀 chord：`r` 录制 / `p` 回放 / `@` 重复），其实现**未并入**现行代码。
> 现行实现是 2026-11-12 第二轮方案（`<f10>` / `<f11>` / `<f12>` 三单键，
> 见 `../macro-record-replay-unified-progress.md`），键位、API 与命令契约以产品源码为准。
> 本文出现的 `MACRO_PREFIX_KEY`、`pre_dispatch`、`macro_awaiting`、`<f6>` 等符号
> 在现行代码中不存在，**不得**作为开发或施工依据。
> 2026-11-12 合并 `replay` 分支时仅为保留历史轨迹收录本组文档，代码未采纳。

> 唯一规范来源：本文件 + `../overview.md` §2.5/§2.6。

## 1. 输入

- `editor.py:282-293`（make_view 注入 handle_key）、`:435-460`
  （refresh_ui / refresh_ui_soon）、`:480-485`（_refresh_chrome）、
  `:495-501`（handle_key/handle_raw_key 薄委托）。
- `editor_compose.py:74-78`（session 构造注入）、`:363-374`（flows 工厂
  与 late-bound 通知先例）。
- `editor_dispatch.py:140-181`（`_handle_key` / `_handle_raw_key`）。

## 2. 独占文件

`yate/editor.py`、`yate/editor_compose.py`、`yate/editor_dispatch.py`。

## 3. 具体修改（接入清单 §三.8 全项）

1. `editor.py`：类属性注解 `macro: MacroFlows | None = None`（与既有
   flows 属性同区块）+ `__init__` 组装顺序注释补 `macro`。
2. `editor_compose.py`：对应 `_build_*` 工厂内构造
   `MacroFlows(session, editor.handle_raw_key, editor.message)` 并赋回
   （绑定方法注入 = 语义能力注入先例，不持 App 句柄）。
3. `editor_dispatch.py` `_handle_raw_key`：按总纲 §2.5 在 `event_to_raw`
   之后加 4 行接线（`pre_dispatch` True → `refresh_ui()` + `return True`）。
   `_handle_key`（event 路径）不改（raw 统一在 `_handle_raw_key` 处理）。

## 4. 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_editor_core.py tests/test_app_panes.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

## 5. 风险与回滚

- `pre_dispatch` 恒 False 时派发行为零变化（回归面 = 全量 pytest + 冒烟）。
- R10：接线在 `_handle_raw_key` 单点，返回 True 即被 view 层 stop
  （view.py:248-250 既有保证），不产生二次派发。
- 回滚：3 文件独立 revert，不影响 a/b。
