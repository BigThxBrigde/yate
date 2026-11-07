# Issue source notes — `:enew` arguments and unnamed-buffer LSP attach

Source: <https://gitee.com/jermaine/yate/issues/IKSFS7> (read 2026-11-06).
Title: `fix: :enew 参数被静默忽略 + 无路径 buffer 永不启动 LSP（状态栏却显示已检测到 SERVER）`
Status: 待办的 / label: bug / milestone: AI在哪里Vol.2 / 0 comments / created 2026-11-02 23:02.
Branch for this task: `fix/enew-args-lsp-attach`, worktree: `../yate-enew-args-lsp-attach` (relative to the main repo).

This file is the step-1 "issue text reading and organization" artifact of
`task-orchestration.md` section 2.1: it only collects the source text, the
reproduction steps, the expected/actual behavior, the reporter's code
locations and the suggested directions. It contains no task analysis and no
design decision; those belong to the plan-architect-designer step.

## 1. Problem statement (verbatim organization)

`:enew` 新建 buffer 后存在三个连锁问题：

1. **参数被静默忽略**：`:enew test.py` 中的 `test.py` 被直接丢弃，不报错、不提示，用户会误以为 buffer 已绑定到 `test.py`。
2. **buffer tab 一直是 `[no name]`**：新建的 document `path=None`，tab 栏 / 状态栏名称恒为 `[no name]`（这部分本身符合"未命名 buffer"语义，但因上一条用户预期是 `test.py`）。
3. **无路径 buffer 永不启动 LSP，但状态栏已显示 server 被检测到**：`:set filetype=py` 后语法高亮正常激活，状态栏 LSP 指示也显示 server 已配置/检测到，但 server 进程从未启动，无补全、无诊断。

## 2. Reproduction steps

1. 启动 yate，执行 `:enew test.py`（或 `:enew` 后 `:set filetype=py`）。
2. 观察顶部 buffer tab：显示 `[no name]`，而非 `test.py`。
3. 观察状态栏：filetype 显示 `py`（高亮已激活），LSP 指示显示 py server 已检测到（CONFIGURED）。
4. 编辑内容触发补全 / `:diagnostics`：无任何 server 启动迹象，补全不可用。

## 3. Expected behavior

- `:enew` 带参数时要么报错提示（对齐 vim `:enew` 无参语义），要么支持以给定文件名创建 buffer 并绑定路径（至少 `:saveas` 之后 LSP 应能接管）。
- 状态栏 LSP 指示与实际行为一致：无路径 buffer 不应显示"已检测到可服务它的 server"，或应在路径补齐（`:saveas test.py`）后真正 attach。

## 4. Actual behavior

- `:enew test.py` 等价于裸 `:enew`，参数无提示丢弃。
- 无路径 buffer 上 `:set filetype=py`：高亮激活、状态栏显示 server 已检测到，但 LSP server 不启动、无 didOpen。

## 5. Reporter's preliminary code locations

- `:enew` 忽略参数：`../../yate/commands.py` 的 `_enew` 直接调用 `document_flows.new_buffer()`，未透传 args：

  ```python
  def _enew(args: str) -> None:
      editor.document_flows.new_buffer()
  ```

- buffer 命名来源（tab 栏/状态栏均渲染 `doc.name`）：`../../yate/editor_core/document.py` 的 `name` 在 path 为 None 时恒为 `[no name]`：

  ```python
  @property
  def name(self) -> str:
      """Return the file name, or ``[no name]`` for an unsaved document."""
      return self.path.name if self.path is not None else "[no name]"
  ```

- LSP 全链路以 `doc.path is not None` 为硬门控，无路径 buffer 直接 return：`../../yate/editor_lsp/manager.py` 的 `supports` 与 `ensure_client`：

  ```python
  def supports(self, doc: Document) -> bool:
      """True when some registered server claims this document's type."""
      return doc.path is not None and self.config_for(doc.filetype) is not None

  async def ensure_client(self, doc: Document) -> LspClient | None:
      """Start (once) and return the client for *doc*, or None on failure."""
      if doc.path is None:
          return None
      config = self.config_for(doc.filetype)
      if config is None:
          return None
  ```

- 不一致点：状态栏 `state_for_doc` 只看 `doc.filetype`、不看 path，所以无路径 buffer 也会显示"server 已检测到"，与 `ensure_client` 的门控矛盾（`../../yate/editor_lsp/manager.py`）：

  ```python
  def state_for_doc(self, doc: Document) -> ServerState | None:
      """Aggregated server state relevant to *doc*, for the status bar."""
      cfg = self.config_for(doc.filetype)
  ```

- 另注意 `:saveas` 路径只走 `notify_saved`（didSave），didOpen 从未发过，server 端没有该 uri，保存后 LSP 也不会自动接管。

## 6. Reporter's suggested directions (for discussion, not a decision)

1. `:enew` 带参数时报 usage 警告，或按参数创建绑定路径的新 buffer（并补 `new_buffer(path)` 通路 + didOpen）。
2. 统一 `state_for_doc` 与 `supports` / `ensure_client` 的判定口径（都考虑 path）。
3. `:saveas` 成功后，若该 uri 此前无 didOpen，补发 didOpen（即把"首次获得路径"视作 shown 事件）。

## 7. Constraints carried into planning (from repository rules, not from the issue)

- `task-orchestration.md` section 2: closed loop with plan first, per-step commit, no push.
- `plan-before-execute.md` section 2: plan must contain goals/non-goals, rejected alternatives,
  step-by-step inputs/file lists/outputs/acceptance commands, risks and rollback.
- `architecture-boundaries.md`: strict downward dependencies R1-R15, no new Protocol,
  no `TYPE_CHECKING`, no `Any`, tracing logs, 37 architecture guards.
- `python-coding-style.md`: pyright strict zero diagnostics, `from __future__ import annotations`,
  full annotations, docstrings, no relative imports, lazy `%` logging.
- `doc-conventions.md`: relative-path references in `.trae/` markdown, bilingual manual sync
  when `yate/docs/*.{en,zh}.md` are touched.
- Gate commands (main agent, final step): pyright / `pytest tests/ -q -n auto` /
  `pytest tests/test_architecture.py -q` / coverage `--cov-fail-under=75` / smoke `--jobs 4`.
