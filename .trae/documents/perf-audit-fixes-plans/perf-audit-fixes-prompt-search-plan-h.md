# perf-audit-fixes-prompt-search-plan-h（成员 C2：P8）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P8。

## 一、目标

**P8（major）**：实时搜索每键全文档重扫且缺防抖——`_live_search`
（prompt_flows.py:57-61）在搜索提示词 `on_input_changed` 每键同步调
`Search.update()`（search.py:50-64，全 buffer 逐行 `finditer` 重建全部匹配）。
本仓库其他长任务路径均有防抖先例（补全 0.12s、高亮 0.08s、find&replace 0.3s、
LSP 0.25s），此处独缺。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/flows/prompt_flows.py`

关联测试（可改/可新增用例）：
- `tests/test_app_find.py`、`tests/test_modals.py`、`tests/test_app_render.py`

## 三、实施要点

1. `_live_search` 套防抖：模块级常量窗口（取 0.12s，对齐补全先例），
   `asyncio.get_running_loop().call_later` 重排——每次输入取消旧 timer、排新
   timer（先例：manager.py `notify_edit` 的 timer 模式；prompt_flows 内已有
   类似防抖先例可参照则优先对齐）；
2. 空查询立即清除分支保持同步（清高亮不贵，且用户清空时期望即时反馈）；
3. 防抖回调执行时以**最新** query 为准（timer 携带 doc/prompt 引用，回调内读
   当前输入值——按现有 `_live_search` 的取参方式保持一致，避免陈旧 query）；
4. prompt 关闭/取消时取消 pending timer（防回调触达已关闭的 prompt——按
   flow 生命周期挂点处理，参考本文件既有清理模式）；
5. `Search` 本体（editor_core/search.py）零改动（归 plan-e 名下）。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_app_find.py tests/test_modals.py tests/test_app_render.py -q
```

补用例：连续输入只触发一次全扫（防抖后）；清空查询即时清除高亮；
prompt 关闭后 timer 不触达。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

防抖 0.12s 引入高亮延迟（不可感量级，与补全先例一致）。
回滚：本成员产物单独提交，可独立 revert。
