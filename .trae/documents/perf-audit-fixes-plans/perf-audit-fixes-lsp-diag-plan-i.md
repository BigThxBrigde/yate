# perf-audit-fixes-lsp-diag-plan-i（成员 C3：P11）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Minor P11。

## 一、目标

**P11（minor→诊断多时 major）**：诊断查询每调用全表拷贝 + 全表线性过滤——
`diagnostics_on_line`（manager.py:605-637 的 `diagnostics_for`/`diagnostics_on_line`）
每次 `list(self._diagnostics.get(...))` 拷贝 + 全表过滤；渲染循环每可见行调用一次
（editor_view/editor.py:415），单帧成本 = 行数 × 诊断数；pyright 对出错文件可发
布数百条诊断。同文件搜索匹配已有 `_matches_for_row`（editor_view/editor.py:603-621）
按行桶缓存先例，诊断没有。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_lsp/manager.py`（Wave a 的 plan-a 已改过本文件，波间串行无冲突，
  基于其最新状态修改）
- `yate/editor_view/editor.py`（仅当渲染调用处需要适配时才动；预期 O(1) 化后
  调用处不变）

关联测试（可改/可新增用例）：
- `tests/test_lsp.py`、`tests/test_app_lsp.py`、`tests/test_highlight.py`、
  `tests/test_app_render.py`

## 三、实施要点

1. manager 侧在诊断发布点（publish/写入 `self._diagnostics` 的位置）同时重建
   该 uri 的按行索引：`dict[str, dict[int, list[Diagnostic]]]`——多行诊断
   （start_row ≠ end_row）登记到其覆盖的每一行（或登记区间起点 + 渲染行查询
   按范围命中——以简单正确优先：逐行登记实现最简，诊断表变更时整索引重建，
   发布频率低（服务器 push 驱动），成本可接受）；
2. `diagnostics_on_line(doc, row)`：索引 O(1) 取该行列表；**对外拷贝语义保持**
   （返回新 list，防调用方修改污染索引）；
3. `diagnostics_for` 保持现状（外发调用方需要全表拷贝）；
4. 文档关闭/诊断清除时同步移除对应索引（对齐 `_diagnostics` 的现有清理点
   manager.py:379-381、169-181）；
5. `editor_view/editor.py` 渲染调用处（415）预期零改动——若需适配（如方法
   更名）保持最小改动并在报告登记。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_app_lsp.py tests/test_highlight.py tests/test_app_render.py -q
```

补用例：多行诊断按行命中正确（覆盖区间每行都能查到）；发布后索引重建与
旧查询结果一致；关闭文档后索引随之清除。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

索引与全表不同步会漏诊断——索引重建绑定在 `_diagnostics` 写入点（单一来源），
测试护栏覆盖发布/清除路径。回滚：本成员产物单独提交，可独立 revert。
