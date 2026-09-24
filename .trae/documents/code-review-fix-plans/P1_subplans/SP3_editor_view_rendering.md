# SP3 — editor_view 渲染与交互（S4 S12 S13 S14 S15 S17 S28 S37 S40 S42）

> 来源：[P1 批次三](../P1_suggestions_plan.md)、[批次四（S28/S42）](../P1_suggestions_plan.md)、
> [批次六（S37）](../P1_suggestions_plan.md)、[批次七（S40）](../P1_suggestions_plan.md)。
> 全部落在渲染热路径 / editor_view 域，波次一优先执行。统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S12 | [editor.py:424、:576](../../../../yate/editor_view/editor.py) | `diagnostics_on_line` 每渲染行查两次 | M |
| S13 | [editor.py:495-510](../../../../yate/editor_view/editor.py) | `_welcome_lines()` 每帧重建 | S |
| S14 | [editor.py:289-311、:345-349](../../../../yate/editor_view/editor.py) | 丢弃过期高亮结果后仍多付一个防抖窗口 | M |
| S15 | [editor.py:151-158](../../../../yate/editor_view/editor.py) | `_cursor_anchor()` 每渲染 3+ 次遍历窗格树 | M |
| S17 | [panes.py:461-467](../../../../yate/editor_view/panes.py) | reconcile 与 apply_doc 重复恢复活动叶子滚动 | M |
| S4 | [explorer.py:385-387](../../../../yate/editor_view/explorer.py) | 新建文件同步 `open_path`（树回调内做 LSP open） | S |
| S37 | [explorer.py:107、:119-123](../../../../yate/editor_view/explorer.py) | 删除最后选中项后 `_last_selected` 悬挂 | S |
| S40 | [manual.py:341-379](../../../../yate/editor_view/manual.py) | 手册搜索每按键全量重建块 widget、无防抖 | M |
| S28 | [test_app_textual.py:204-314](../../../../tests/test_app_textual.py) | 测试深访 `_hl_tokens` 等私有属性 | M |
| S42 | [test_app_textual.py:3781-3786](../../../../tests/test_app_textual.py) | 注释与已落地的原子写行为矛盾 | S |

## 独占文件清单（只许改这些）

- `yate/editor_view/editor.py`
- `yate/editor_view/explorer.py`
- `yate/editor_view/panes.py`
- `yate/editor_view/manual.py`
- `tests/test_app_textual.py`（S28 探针迁移 + S42 注释；不动无关用例断言）

## 实施步骤（建议顺序）

1. **第 0 步 复核**：十条锚点逐一确认；重点 S14——现行实现已是 Timer +
   `_hl_scheduled_key` 防重（P1 已按新代码改写策略），确认 discard 分支仍在
   editor.py:345-349。
2. **S12 + S15（同模式合并做）**：渲染帧入口对可见行范围算一次诊断
   `dict[int, list[Diagnostic]]`、算一次 `_cursor_anchor()`，以帧局部变量下传
   gutter 与行渲染。验收：monkeypatch 计数，单帧调用次数 = 1（两项各自断言）。
3. **S13**：以 `keymaps.active_name`（或 keymap 对象 id）为键缓存
   `tuple[str, ...]`。验收：两次渲染返回同一对象；切 keymap 后重建。
4. **S14（按 P1 修订策略）**：discard 分支加 `self._schedule_highlight(0.0)` 立即重排，
   跳过多余防抖窗口。**注意**：保留「discard 后旧 `_hl_tokens` 继续上色」的防闪白设计
   （editor.py:113-115 注释），不得清缓存。验收：制造 doc 切换，断言新 pass 立即启动
   （`_hl_scheduled_key` 更新、无 0.08s 等待）。
5. **S17**：**动手前先在报告中写清 reconcile（全量恢复）与 apply_doc（活动叶子恢复）
   的语义差异**，然后按 P1 策略让 reconcile 的恢复循环跳过即将获焦的活动叶子。
   验收：分屏 → 切分 → 关闭一半，剩余叶子滚动位置保留。
6. **S4 + S37**（explorer.py 同文件小改）：`open_path_later(target)`；
   `_restore_cursor` 未命中时 `_last_selected = None`。
7. **S40**：仿 `EditorView._HIGHLIGHT_DEBOUNCE_S` 用
   `asyncio.get_running_loop().call_later` 防抖，窗口期合并查询后再重建。
   验收：连续输入多字符，重建函数调用次数 < 按键数且最终内容正确。
8. **S28 + S42**：`editor.py` 新增公开只读探针（frozen dataclass 返回高亮状态快照，
   **不引入 Protocol**，符合 R2）；test_app_textual.py 的私有属性断言改走探针；
   S42 更新过时注释并补磁盘字节完好断言。
9. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright yate/editor_view tests/test_app_textual.py
   .venv\Scripts\python.exe -m pytest tests/test_app_textual.py tests/test_explorer.py tests/test_panes.py -q
   ```

## 注意

- `test_app_textual.py` 是公共 app 级测试文件：改动仅限 S28/S42 所需；遇到 timing 类
  偶发失败先重跑确认再下结论，不得顺手改断言（subagent-workflow §三.3）。
- S12/S15 改渲染签名时保持 editor_view 内部传递，不新增跨层导出（R3/R11）。
