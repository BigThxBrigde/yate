# 输入闪烁修复：语法高亮防抖与陈旧缓存复用 实施计划

## 问题

issues.md 第 1 条：输入时屏幕闪烁，影响输入体验，需要加入防抖动机制。

## Repository Research（调研结论）

### 按键后的刷新链路

1. [editor.py](file:///d:/Programming/yate/yate/editor_view/editor.py#L169-L225) `EditorView.on_key` → [app.py](file:///d:/Programming/yate/yate/app.py#L684-L689) `YateApp.handle_raw_key`：keymap 修改 buffer（`content_version += 1`）后调用 `ui_refresh()`。
2. [app.py](file:///d:/Programming/yate/yate/app.py#L691-L711) `ui_refresh()` 对所有 pane 视图调用 `content_changed()` → `_update_virtual_size()` + `reveal_cursor()` + `refresh()`。
3. 渲染时 `render_line` → `_syntax_kinds` → [`_tokens_for`](file:///d:/Programming/yate/yate/editor_view/editor.py#L263-L289)。

### 闪烁根因（已确认）

[`_tokens_for`](file:///d:/Programming/yate/yate/editor_view/editor.py#L263-L289) 一旦发现 `content_version` 变化（任何一次编辑），立即丢弃**整个文档**的 token 缓存并返回 `[]`（editor.py:288）：

- 编辑后第一帧：所有可见行以**无语法颜色**的默认前景色绘制；
- 随后后台线程对**整个文档**重新分词（[`_highlight_later`](file:///d:/Programming/yate/yate/editor_view/editor.py#L291-L314)），完成后再 `refresh()` 重绘为彩色。

每次击键 = 「彩色 → 整屏无色 → 彩色」两帧；快速连打时 worker 不断取消/重启，颜色持续来回翻转，终端要重写大量单元格，表现为整屏闪烁（大文件/慢终端/Windows conhost 上尤其明显）。

### 已排除的因素

- Textual 对同一帧内的多次 `refresh()` 做合并（[widget.py:4334](file:///d:/Programming/yate/.venv/Lib/site-packages/textual/widget.py#L4324-L4376)），compositor 对 Strip 做 diff，仅输出变化单元格——`refresh()` 调用次数本身不是主因，**帧间内容真实变化（颜色丢失）才是**。
- 补全弹窗（[completion.py](file:///d:/Programming/yate/yate/app_features/completion.py#L64-L73)，0.12s debounce）、LSP `notify_edit`（[manager.py:316](file:///d:/Programming/yate/yate/editor_lsp/manager.py#L301-L316)，`call_later`）已有防抖，与本次闪烁无关。
- 光标移动不 bump `content_version`，缓存已能存活（现有测试 `test_highlight_cache_survives_cursor_movement` 覆盖），无闪烁。

### 安全性依据

- 陈旧 tokens 按字符区间着色，[_syntax_kinds](file:///d:/Programming/yate/yate/editor_view/editor.py#L316-L325) 已对 cell 数做 clamp；[char_to_cell](file:///d:/Programming/yate/yate/editor_view/theme.py#L512-L522) 对超出行长的索引天然安全（循环结束返回总宽），行级访问已有 `row < len(tokens)` 越界保护（editor.py:289）。
- Textual `set_timer` 挂在 widget 的 MessagePump 上，widget 卸载时自动停止（message_pump.py:533-535），适合做视图级防抖。

## Files and Modules

- [yate/editor_view/editor.py](file:///d:/Programming/yate/yate/editor_view/editor.py)：改造 `EditorView` 高亮缓存调度逻辑（唯一的生产代码改动文件）。
- [tests/test_app_textual.py](file:///d:/Programming/yate/tests/test_app_textual.py)：新增防抖/陈旧缓存复用测试。

## Implementation Steps

1. **在 `EditorView.__init__` 中调整高亮调度状态**
   - 删除 `self._hl_scheduled: bool`；
   - 新增 `self._hl_timer: Optional[Timer]`（Textual `message_pump.Timer`）与 `self._hl_scheduled_key: Optional[tuple[object, str, int]]`（`(doc, filetype, content_version)`，表示待发/在跑的着色任务目标）；
   - 新增类常量 `_HIGHLIGHT_DEBOUNCE_S = 0.08`（连打合并窗口，与补全防抖 0.12s 同量级）。
   - 保留 `_hl_tokens / _hl_doc / _hl_version / _hl_filetype` 属性名（现有测试直接依赖）。

2. **重写 `_tokens_for` 的缓存失效分支（核心）**
   - 缓存完全有效（doc / filetype / version 均匹配）：照旧返回该行 tokens；
   - **同 doc 且同 filetype、仅 version 落后（编辑场景）：返回上一版 tokens 继续着色（行越界返回 `[]`），不再返回整屏 `[]`**；
   - 无缓存 / doc 切换 / filetype 切换：缓存不可复用，返回 `[]`；
   - 上述两种失效情况都调用新的调度入口，但以 `(doc, filetype, version)` 为键：同一帧内对多行的重复调用、以及针对同一版本的重复渲染不重建 timer；版本变化（新的一次编辑）才取消旧 timer 重新计时——实现 trailing debounce。

3. **新增 `_schedule_highlight(delay: float)` 与 `_launch_highlight()`**
   - `_schedule_highlight`：`timer.stop()` 旧 timer 后用 `self.set_timer(delay, self._launch_highlight, name="highlight-debounce")` 重建；
   - 编辑复用路径 delay = `_HIGHLIGHT_DEBOUNCE_S`（0.08s）；
   - 无缓存/首帧/切文档/切 filetype 路径 delay = `0.0`，保持当前「打开文件后尽快首次上色」的体验；
   - `_launch_highlight`：清 `_hl_timer`，`is_mounted` 守卫后用现有 `run_worker(self._highlight_later(), group="highlight", exclusive=True, exit_on_error=False)` 启动（沿用每 widget 独立 group，避免多 pane 互相取消）。

4. **调整 `_highlight_later`**
   - 删除 `self._hl_scheduled = False`；
   - 版本/doc 匹配时：落缓存、清 `_hl_scheduled_key`、`refresh()`（维持现状）；
   - 过期时：保留 `is_mounted` 检查与 `self.refresh()`——重绘经 `_tokens_for` 按调度键决定是否需要再排（更新的编辑已挂新 timer 时不重复排），最终总有一个 worker 收敛到最新版本。

5. **新增测试（tests/test_app_textual.py，沿用 pilot + wait_until 风格）**
   - 无色帧消除：高亮就绪后按一个编辑字符，**不等待 debounce**，断言 `_tokens_for(0)` 立即返回旧版非空 tokens，且 `render_line(0)` 段颜色中关键字色仍在（无「整屏脱色帧」）；
   - 防抖合并：同一帧/连续多次渲染只存在一个待发 timer（`_hl_timer` 单例、`_hl_scheduled_key` 为最新版本）；
   - 最终一致：`wait_until` 等待后 `_hl_version == app.buffer.content_version` 且 tokens 换为新对象（现有 `test_highlight_cache_survives_cursor_movement` 已部分覆盖，需确认在新增 0.08s 延迟后仍通过，其 timeout=5.0 充足）；
   - 隔离性：filetype 切换（`set filetype=`）与切换到另一文档时不复用陈旧 tokens（立即返回 `[]`，随后正常着色）。

## Dependencies and Considerations

- 唯一运行时依赖是已安装的 textual>=8.0；`set_timer` / `Timer.stop()` 均为其稳定 API。
- 陈旧缓存代价：编辑行本身可能在约 80ms 内显示略陈旧的颜色，停顿后自动纠正——这是 VS Code/vim 语法插件的通用做法，远优于整屏脱色闪烁。
- 跨多 pane：调度状态与 worker group 都是每 widget 一份，同文档的多个视图各自着色，互不取消（沿用现状）。
- 扩展直接改 `buffer.lines` 后调用 `mark_content_changed()`（[extensions.py:19](file:///d:/Programming/yate/yate/services/extensions.py#L19)）同样 bump version，自动走新防抖路径，无需改动。
- Python 3.10 兼容（项目要求 >=3.10），类型标注用 `Optional`/`tuple`。

## Validation

- `python -m unittest discover -s tests` 全量通过（重点 test_app_textual.py 中高亮相关用例）。
- pyright strict 零诊断（`[tool.pyright] typeCheckingMode = "strict"` 门禁）。
- 手动验证：`python -m yate <一个较大的 .py 文件>`，插入模式长按/快速连打字符，确认不再出现整屏颜色闪白；停顿约 0.1s 后颜色正确；切换主题、`:set filetype=`、多 pane、撤销/重做后高亮最终一致。
- 可选：用 `.trae/skills/textual-pilot-smoke` 做 headless 截图（SVG）对比编辑前后帧，确认无全帧脱色。

## Risks

- **风险：防抖期间着色短暂陈旧** → 仅影响编辑行局部颜色，~0.08s 后纠正；首帧/切文档不防抖（delay=0），不影响打开文件的上色速度。
- **风险：timer/worker 竞态导致永远不着色** → 调度键设计保证：worker 过期后 refresh 会按最新版本重排；最终一致性由新测试与现有 `test_highlight_cache_survives_cursor_movement` 双重守护；timer 随 widget 卸载自动停止，worker 完成有 `is_mounted` 与 doc/version 双重检查。
- **风险：快速连打时 worker 频繁取消（exclusive group）** → 与现状一致且只减不增：防抖窗口内根本不启动 worker，连打期间线程分词次数大幅下降，属于额外收益。
