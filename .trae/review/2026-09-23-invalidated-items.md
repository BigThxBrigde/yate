# yate Code Review — 已失效条目（复核基准 2026-09-23）

## 已失效条目

> 审查条目经核实后不再成立的记录，仅存档。复核基准：2026-09-23 当前代码
> （分层重构 L4→L0 完成后）。

| 原条目 | 原位置 | 失效原因 |
|---|---|---|
| `is_relative_to()` 需要 Python 3.9+ | 原 `app_features/explorer.py:104` | 项目已要求 Python 3.10+（`pyproject.toml`），兼容性顾虑不复存在；代码现位于 `yate/editor_view/explorer.py` |
| 中文 docstring 与英文代码库不一致 | 原 `app.py:1690` | 分层重构随文档英文化一并清除；当前 `yate/app.py` 已检索不到中文 docstring |
| 未使用的导入 `replace`（from dataclasses） | 原 `editor_view/panes.py:11` | 该导入已不存在；panes.py 现从 `pane_types` 导入的 `replace_node` 在 [panes.py:235](../../yate/editor_view/panes.py) 有实际调用（被误判） |
