# perf-audit-fixes-ui-refresh-plan-f（成员 B3：P3 + P21 + P10b）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P3、§Minor P10/P21。

## 一、目标

1. **P3（major）**：`refresh_ui`（editor.py:713-741）每按键/鼠标事件无条件执行
   全应用刷新链；`handle_raw_key`（editor.py:856-869）867 行不看 `handled` 无条件
   `self.refresh_ui()`——任何未绑定键也付全款。chrome 重建（状态栏整条 Rich Text、
   标签栏重排、面包屑）无"未变短路"；
2. **P21（minor）**：`whichkey.clear()`（whichkey.py:148-154）隐藏态每键仍
   `update("")` 标脏；
3. **P10b（minor）**：面包屑 `chrome.py:191` 对 `doc.path` 每次 `resolve()`
   （Windows syscall），随每键 `refresh_crumbs` 执行。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor.py`
- `yate/editor_view/chrome.py`
- `yate/editor_view/statusbar.py`
- `yate/editor_view/tabbar.py`（仅当短路需要时才动）
- `yate/editor_view/whichkey.py`

关联测试（可改/可新增用例）：
- `tests/test_chrome.py`、`tests/test_whichkey_panel.py`、
  `tests/test_whichkey_flows.py`、`tests/test_mode_chip.py`、
  `tests/test_app_render.py`、`tests/test_app_panes.py`

## 三、实施要点

### P3
1. `handle_raw_key`：`self.refresh_ui()` 改为 `if handled: self.refresh_ui()`；
   `BufferReadOnlyError` 分支保持现状（已单独刷新并消费键）；注意
   `completion.after_editor_key(raw)` 保持在 refresh 之后、不受 handled 门控
   （补全面板需要每个键都喂入——确认现状后保持）；
2. chrome 短路（先例 `terminal.py:562-576`：文本未变则跳过）：
   - `statusbar.refresh_status`（statusbar.py:118-204）：构建 Rich Text 前先由
     输入要素生成"内容指纹"（mode/文档名/dirty/LSP 段等按现状要素组 key），
     与上次相同则直接 return（实例字段存上次指纹）；
   - `tabbar.refresh_tabs`（chrome.py:53-127）：同法（标签序列指纹）；
   - `breadcrumbs.refresh_crumbs`（chrome.py:191 一带）：同法；
3. **不改** `_refresh_views` 的全量 `content_changed()`（总纲非目标 3）；
4. `_refresh_lsp` 保持无条件（有内部防抖与短路）。

### P21（whichkey.py）
- `clear()` 开头加卫语句：面板未显示且无内容时直接 return，不 `update("")`
  不标脏。注意 flow 侧（whichkey_flows.py）不归本成员，改组件内部即可。

### P10b（chrome.py）
- 面包屑对 `doc.path` 的 resolved 结果按 Document 缓存（组件侧
  `dict`/WeakKeyDictionary 按 doc.path 或 doc 实例键控）；retarget/save-as 时
  失效——观察 Document 生命周期挂点，若无现成信号，用"路径变更才重算"的
  轻量键（缓存键 = str(doc.path)，path 不变即复用；保存不改 path 天然命中）。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_chrome.py tests/test_whichkey_panel.py tests/test_whichkey_flows.py tests/test_mode_chip.py tests/test_app_render.py tests/test_app_panes.py -q
```

补用例：未消费键不触发 refresh_ui（可 monkeypatch 计数）；chrome 指纹相同不重建、
要素变化才重建；which-key 隐藏态 clear 零标脏。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

指纹漏要素会导致状态栏/标签显示陈旧——指纹要素必须覆盖该组件的全部输出
决定因素，逐组件核对现状渲染输入。回滚：本成员产物单独提交，可独立 revert。
