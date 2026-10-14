---
title: 扩展系统增强分支 Qwen Code 评审报告（2026-10-14）
date: 2026-10-14
scope: branch:enh/extension-system-enhance
status: reviewed
---

# 扩展系统增强分支 Qwen Code 评审报告（2026-10-14）

> 评审对象：分支 `enh/extension-system-enhance`（HEAD `96ebe80`），
> diff 基线 = merge-base(master)（`b3cd12a`）。
> 评审范围：61 文件，+6130/-417（8048 行 diff：4983 source / 2065 test / 1000 docs）。
> 评审方式：Qwen Code `/review` skill，medium effort，Step 3B 领地×维度扇出
> （27 代理：25 chunk 代理 + test-matrix + 1b 移除行为审计），
> 覆盖 25/25 chunk，27/27 代理有效工作。
> 门禁实测：`.venv` 下 pytest 全绿（162 tests across 7 key test files）。

---

## 一、门禁实测

| 门禁 | 结果 |
|---|---|
| `pytest tests/test_events.py test_extension_api.py test_extension_bridges.py test_lua_extensions.py test_lua_defs.py test_ui_contributions.py test_architecture.py -q` | **全绿**（162 passed） |
| 覆盖率 | 前轮实测 91.95%，本轮未重跑全量 |
| 冒烟 | 前轮 112/112，本轮未重跑 |

---

## 二、发现清单（按严重程度）

### 2.1 [Suggestion] `events.py` `report_failure` 回调未防御自身抛异常

**文件：** `yate/services/events.py:156–159`

**问题：** `emit` 的 `except Exception` 处理器内调用 `self._report_failure(...)`，
但该回调本身未套 try/except。若 `report_failure` 抛异常（如 shutdown 期间
message widget 已卸载），异常会逃逸出 `emit`，终止 `for` 循环，
后续健康监听器不再执行——违反文档承诺的"never prevents the remaining listeners"。

**触发场景：** 扩展监听器 A 抛异常 → `report_failure` 回调（如 `ed.message(text)`）
也抛异常 → 监听器 B/C 永远不执行。

**建议修复：**
```python
if self._report_failure is not None:
    try:
        self._report_failure(
            f"extension event {event.name}: listener failed "
            "(see trace log)"
        )
    except Exception:
        log.exception("event failure reporter itself failed: %s", event.name)
```

**Fix witness：** `tests/test_events.py` — 新增测试：两个健康监听器夹一个失败监听器，
`report_failure` 也抛异常，断言两个健康监听器仍然执行。

---

### 2.2 [Suggestion] Lua `yate.ui` 有 `add_segment` 但缺 `remove_segment`

**文件：** `yate/extensions/_yate.lua:225–228`

**问题：** `yate.ui.add_segment` 封装了 `api.ui.add_segment`，
但无对应的 `yate.ui.remove_segment`。Lua 扩展在 teardown 时无法通过
同一抽象层清理状态栏段。

**触发场景：** Lua 扩展在 setup 中调用 `yate.ui.add_segment("my-seg", provider)`。
扩展重载时，段 ID 仍在 Python 侧 `_segments` 字典中 → bridge 抛 `ValueError`
（重复 ID，`bridges.py:428`）→ 扩展重载失败。Python 示例
（`example_ext.py.example:162`）展示 `api.ui.remove_status_segment(...)`，
但 Lua 用户必须降级到原始 bridge 调用，破坏封装一致性。

**建议修复：**
```lua
---@param id string
---@return nil
function yate.ui.remove_segment(id)
  api.ui.remove_status_segment(id)
end
```

**Fix witness：** `tests/test_lua_extensions.py` — 新增测试：Lua 扩展在 teardown
中调用 `yate.ui.remove_segment(id)`，重载成功无 `ValueError`。

**Fix constraint：** Python bridge 方法名为 `remove_status_segment`（非 `remove_segment`），
位于 `yate/services/extensions/bridges.py:437`。

---

### 2.3 [Nice to have] 文档字符串 "13-name facade" 与实际 14 名不符

**文件：** `tests/test_architecture.py:1063`

**问题：** `test_extension_machinery_hides_behind_facade` 的文档字符串写
"the 13-name facade does not re-export"，但 `EXTENSION_FACADE_NAMES` 含 14 个名字
（R14 规则文档正确写为 14）。

**建议修复：** 将 "13-name" 改为 "14-name"。

---

## 三、六维度结论

- **功能与正确性**：事件发射点（saved/opened/closed/activated/diagnostics/
  keymap/theme）与生命周期约定一致；Lua 三种入口形式（module table > global
  setup > top-level）有文档、测试和回退路径；子包化移动忠实，所有调用点已更新。
- **安全**：无新增注入面；`./extensions` 仍在 `:trust` 工作区门控下加载；
  无硬编码凭据。
- **性能**：事件发射全在低频路径（保存/打开/诊断/主题）；状态栏 provider
  拉取模型文档明示 "keep provider cheap"；`UiExtensionBridge.segments`
  快照排序 O(n log n)，n 为段数（个位数量级）。
- **可维护性**：docstring 密度与全仓一致；惰性 `%` 日志；PEP 695 `type` 语句；
  闭包捕获使用默认参数模式（`km=km, raw=raw`），与既有 `bind_key` 一致。
- **架构边界**：R14 冻结 14 名 facade 有架构测试守护；`EXTENSION_SUBMODULE_FROZEN`
  白名单机制合理；子包内部不对外暴露。
- **测试覆盖**：test-matrix 代理逐行为变更映射测试，确认每个行为变更都有
  对应测试（mutation 下会变红）；漂移守卫（`test_lua_defs.py`）锁定
  Lua ↔ Python 表面对齐。

---

## 四、结论

**Approve** — 无阻塞问题。两个 Suggestion 为防御性改进，不影响当前正确性。

| 严重度 | 数量 |
|---|---|
| Critical | 0 |
| Suggestion | 2 |
| Nice to have | 1 |
