# perf-audit-fixes-mouse-completion-plan-g（成员 C1：P4 + P7）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Major P4/P7。

## 一、目标

1. **P4（major）**：鼠标拖选每个 MouseMove 触发全应用 `refresh_ui`
   （mouse_flows.py:92-100；`_on_down`:88、`_on_click`:127 同模式但低频）——
   MouseMove 每秒可达上百次，每次执行全部窗格重绘 + 全部 chrome 重建 + LSP 同步；
2. **P7（major）**：无 LSP 补全词缓存以 `content_version` 为键（completion.py:295-307），
   打字每键推进 version → 每次查询必然全量重算
   `[set(_WORD_RE.findall(line)) for line in buf.lines]`，且 worker 跑在事件循环上。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/flows/mouse_flows.py`
- `yate/editor.py`（仅新增 `refresh_ui_soon()`；Wave b 的 plan-f 已改过本文件，
  波间串行无冲突，注意基于其最新状态修改）
- `yate/editor_view/completion.py`
- `yate/flows/completion_flows.py`（仅当 P7 实现需要时才动；预期主要在 completion.py）

关联测试（可改/可新增用例）：
- `tests/test_app_mouse.py`、`tests/test_completion_popup.py`、
  `tests/test_prompt_completion.py`、`tests/test_app_render.py`、
  `tests/test_app_panes.py`

## 三、实施要点

### P4
1. `Editor` 新增 `refresh_ui_soon()`：`call_after_refresh` 合并去重——实例级
   pending 标记（或持有返回的 timer 句柄），pending 时直接 return；
   回调执行时清标记并调 `refresh_ui()`；
2. `mouse_flows._on_move`（92-100）改调 `refresh_ui_soon()`（`self._refresh`
   是注入的 `editor.refresh_ui`——注入点在 editor.py:260 一带，改为注入
   `refresh_ui_soon` 或注入对偶方法；保持注入模式，不走 `self.app`）；
3. `_on_down` / `_on_click` / `_on_up` 保持同步刷（低频、交互终点需即时反馈）；
4. 拖拽期间被拖视图的 `content_changed()` 仍同步调（标脏便宜，刷新才贵）；
   由 `refresh_ui_soon` 统一出帧。

### P7
1. `_row_word_cache` 改行级结构：`WeakKeyDictionary[TextBuffer, _RowWords]`，
   `_RowWords` 持 `content_version`、`rows: dict[int, frozenset[str]]`（或
   list + 惰性 None 槽）；
2. 查询时：version 相同直接返回；不同则只对"内容可能变化的行"重算——
   消费 plan-d 落地的 `buf.take_dirty_range()`（若 Wave b 已合入则用之；
   若未合入，退化为"与旧 version 差异行不可知 → 全量重算一次"的保守路径
   并在报告登记，等 Wave b 后由主代理复核）；
   注意：`take_dirty_range` 是一次性取走语义——补全查询消费后，plan-j 的
   高亮同步将取不到区间。**协调裁决（主代理已定）**：P7 不消费 dirty range，
   改为在 buffer 上提供**非消费型**只读访问 `last_dirty_range` 属性（plan-d
   契约扩展：`take_dirty_range()` 保留消费语义供 plan-j，另暴露
   `dirty_range` 只读属性或 `peek_dirty_range()`）；C1 按此实现并在报告登记，
   主代理在 Wave b 回收后核对 plan-d 是否已按扩展契约落地，未落地则由
   主代理补丁（buffer.py 归 plan-d 名下）。
3. 并集逻辑（`_words_from_buffer`:272-285 一带）不变；worker 线程模型不变。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_app_mouse.py tests/test_completion_popup.py tests/test_prompt_completion.py tests/test_app_render.py tests/test_app_panes.py -q
```

补用例：拖选期间 refresh 合帧（计数断言 N 次 move ≤ 帧数次 refresh_ui）；
行级词缓存只重算变更行（计数断言）。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离（尤其 dirty-range 契约扩展的落地情况）与未解决项。

## 六、风险与回滚

P4 合帧可能让拖选高亮延迟一帧（可感知性低，交互终点同步刷兜底）；
P7 依赖 plan-d 契约——按上述协调裁决执行，未落地部分由主代理补。
回滚：本成员产物单独提交，可独立 revert。
