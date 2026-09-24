# 代码审查修复计划（原子保存 / undo 上限 / 脏标记 / 期望列 / 工作区信任）

> **实施状态（2026-09-23 核对）：✅ 全部已实现（Issue 1–7 + 回归修复，4 个提交）。**
>
> | 提交 | 内容 |
> |---|---|
> | `05106d5` `fix(editor-core)` | Issue 1/2/3/6/7：原子保存、undo 上限、O(1) 脏标记、吞异常补日志、软链环防护 |
> | `5190225` `fix(editor-core)` | Issue 3 初版引入的 `undo_redo` 冒烟回归修复（undo weight 对齐编辑计数） |
> | `b0d154d` `feat(editor-core)` | Issue 4：垂直移动期望列（desired column） |
> | `a89a720` `feat(extensions)` | Issue 5：项目扩展的工作区信任门控（`:trust`） |
>
> 最终验证：pyright strict 零诊断 · pytest 628 passed / 15 skipped ·
> 冒烟 651/651 checks（62/62 scenarios）。

> 来源：2026-09-23 全项目代码审查（安全 → 架构 → 业务逻辑 → 文档），
> 按严重级别排序修复。原则：最小改动、不破坏分层边界
> （`architecture-boundaries.md` R1–R11）、每项带回归测试。

---

## Issue 1 — `Document.save()` 非原子写入（High，数据完整性）

### 现状与根因

[document.py](../../yate/editor_core/document.py) 的 `save()` 用
`self.path.write_bytes(data)` 直写：先 truncate 原文件再写新内容。
进程崩溃、断电、磁盘满发生在写入中途 → **原文件被毁、新内容只写了一半**。
作者已防了编码错误中途抛异常（先 `encode` 再写盘），但没有防 I/O 中断。
vim / VS Code 均为 temp + rename。

### 修复策略（temp + `os.replace` 原子替换）

```python
# Before:
self.path.write_bytes(data)

# After:
tmp = self.path.with_name(self.path.name + ".yate-tmp")
try:
    tmp.write_bytes(data)
    os.replace(tmp, self.path)
except BaseException:
    tmp.unlink(missing_ok=True)   # 失败时清理临时文件
    raise
```

- `os.replace` 在同一卷上是原子操作，崩溃时原文件要么完好要么是新内容；
- 编码错误仍在触碰磁盘前抛出（`data = text.encode(self.encoding)` 先行）；
- 临时文件与目标同目录，保证同卷（`os.replace` 不会跨卷退化）。

### 测试

- `test_save_is_atomic_and_leaves_no_temp_file`：保存语义 + 无 `.yate-tmp` 残留；
- `test_failed_save_keeps_previous_contents`：编码失败不毁原文件。

---

## Issue 2 — undo 栈无深度上限（Medium，内存无界增长）

### 现状与根因

[buffer.py](../../yate/editor_core/buffer.py) 每次编辑
`_Snapshot(tuple(self.lines))` 全量入栈且永不淘汰。10 万行文件长会话：
每键一次数百 KB 常驻，内存无界增长。

### 修复策略

新增公开常量 `MAX_UNDO_STEPS = 1000`；`_commit` 超限淘汰最旧步骤：

```python
self._undo.append(_Edit(before, after, kind, weight))
if len(self._undo) > MAX_UNDO_STEPS:
    del self._undo[0]
```

### 测试

- `test_undo_stack_is_capped`：精确保留 1000 步。

---

## Issue 3 — `doc.modified` 每次按键 O(全文) 对比（Medium，性能）

### 现状与根因

[document.py](../../yate/editor_core/document.py) 的 `modified` 用
`get_text() != self._saved_text`：每次 `refresh_ui → refresh_status` 及
tab 栏逐 doc 执行，大文件每键多次全文 join。

### 修复策略（编辑计数 + 精确回退，两层判定）

1. `TextBuffer.content_edits`：内容变更 +1、undo −1、redo +1；
   `Document` 记录保存时的计数值，`modified` 先比计数（O(1)）；
2. **计数不匹配时回退行元组精确对比** —— 覆盖「保存在合并步中间」
   「undo 栈截断」等计数原理上无法表达的边界，恒为真值，且无全文 join 分配。

```python
@property
def modified(self) -> bool:
    if self.buffer.content_edits == self._saved_edits:
        return False
    return tuple(self.buffer.lines) != self._saved_lines
```

### 回归与二次修复（`5190225`）

初版纯计数方案被冒烟场景 `undo_redo` 拦截（`clean_after_undo` 期望 False
实得 True）：连续打字被**合并**成一个 undo 步（输入 5 字符 = 计数 +5），
一步 undo 只 −1，计数永远回不到保存点。

**修复：** `_Edit` 增加 `weight` 字段（该步折叠的行变更次数，合并打字累加），
undo/redo 按 `edit.weight` 增减计数，与实际撤销的变更数对齐；
`Document.modified` 的两层判定（计数快路径 + 精确回退）保持不变。

### 测试

- `test_modified_tracks_undo_back_to_saved_state`：非合并编辑精确回归保存点
  （含越过保存点变 dirty、redo 回到干净）；
- `test_modified_with_coalesced_typing_since_creation`：冒烟路径镜像
  （type → undo → redo）；
- `test_modified_when_save_lands_inside_coalesced_step`：保存在合并步中间
  的回退路径；
- `test_cursor_only_edits_do_not_mark_document_modified`：纯光标移动不计脏。

---

## Issue 4 — 垂直移动丢失期望列（Medium，编辑器语义）

### 现状与根因

[buffer.py](../../yate/editor_core/buffer.py) 的 `move_up`/`move_down`
直接 `set_cursor((r, c))`：col 被短行截断后**永久丢失**——从第 80 列下移
穿过一个 10 字符行再下移，光标停在 10 而非回到 80。vim / VS Code 均有
desired column 语义。

### 修复策略（`_goal_col` 追踪 + 全路径清除）

- `TextBuffer` 新增私有状态 `_goal_col`：垂直移动以记忆列为目标
  （连续移动中的第一次回退到当前列），`set_cursor` 截断后恢复；
- **清除时机**（防止过期目标列复活）：`set_cursor`（覆盖水平移动、home/end、
  鼠标点击、keymap 显式定位）、`_commit`（内容编辑）、`_restore`（undo/redo）、
  `set_text`、`mark_content_changed`（扩展直改行）、`select_all`。

```python
def move_down(self, select: bool = False) -> None:
    r, c = self.cursor
    goal = self._goal_col if self._goal_col is not None else c
    if r < len(self.lines) - 1:
        r += 1
    self.set_cursor((r, goal), select)
    self._goal_col = goal   # set_cursor 会清除；此处恢复以维持连续追踪
```

### 测试

- 目标列穿越短行存活；
- 水平移动重置；编辑重置；
- `select=True`（shift+方向键）选区扩展下同样正确。

---

## Issue 5 — 扩展从 CWD 静默自动加载（Medium，供应链 / 任意代码执行）

### 现状与根因

[extensions.py](../../yate/services/extensions.py) 的
`load_startup_extensions` 无条件加载 `Path.cwd() / "extensions"` 下所有
`.py`：用户在任何含恶意 `extensions/` 目录的仓库中启动 `yate` 即执行任意
代码——正是 VS Code 引入 Workspace Trust 的原因。yaterc 同理（项目 rc
自动发现），但那是文档明示的 vimrc 式设计；`./extensions` 静默加载没有
同等提示。

### 修复策略（信任清单 + `:trust` 显式确认）

**产品决策**：不采用首启确认对话框（打断 TUI 启动流），采用
「启动跳过 + 消息栏提示 + `:trust` 显式加载」。

1. 新增 [trust.py](../../yate/services/trust.py)（L0 叶子服务）：
   信任清单存 `~/.yate/trusted_workspaces`，每行一个 resolved 绝对路径，
   `#` 注释允许；删除对应行即撤销信任；
2. 启动时项目 `./extensions` **仅在受信任工作区加载**；未信任则跳过并提示
   `extensions: skipped untrusted <路径> (run :trust to load them)`；
3. 新增 `:trust` 命令（`Editor.trust_cwd_extensions`）：记录信任并立即加载；
   幂等（loader 按 resolved 路径去重，重复运行只报新加载数）；
4. **边界**：rc 声明路径、`--ext` / `--ext-dir`、`~/.yate/extensions` 属
   用户主动行为，不受门控——被门控的只有「打开仓库」这一被动动作带入的代码。

### 文档

- `yate/docs/extensions.en/zh.md`：新增「Workspace trust（:trust）」章节，
  加载顺序第 3 步标注门控；
- `yate/docs/yaterc.en/zh.md`：默认目录扫描处标注信任要求。

### 测试

- `tests/test_trust.py`：store 读写、roundtrip（`.` 拼写解析同目录）、
  幂等追加、注释/空行跳过；
- `tests/test_extensions.py`：未信任跳过（含提示消息）/ 信任后加载；
- `tests/test_app_textual.py::test_disabled_extensions_skip_bundled_not_project_dir`
  扩展为双路径：未信任跳过 + `:trust` 后加载 + store 文件落盘。

---

## Issue 6 — 6 处 `except Exception: pass` 静默吞异常（Low）

### 现状与根因

隔离失败是正确的，但 shutdown 路径的日志是诊断「LSP 为何没退干净」等
问题的唯一手段，违反项目规则 §4.5（禁止静默吞异常）。

### 修复策略（保留隔离，补日志）

| 文件 | 位置 | 处理 |
|---|---|---|
| [editor.py](../../yate/editor.py) | extension teardown | `log.exception`（已有模块 logger） |
| [manager.py](../../yate/editor_lsp/manager.py) | LSP server stop | `log.exception("server %s failed to stop", name)` |
| [extensions.py](../../yate/services/extensions.py) | load failure | `log.exception` |
| [pty_proc.py](../../yate/editor_term/pty_proc.py) | PTY shutdown | 新增模块 logger（接 `yate.logs.tracing`，默认静默） |
| [fonts.py](../../yate/services/fonts.py) | 备份/回写 | 新增模块 logger |

所有 logger 均走 `tracing.get_logger(__name__)`：默认零输出，不改变
正常会话行为；`yate_trace` 开启后可诊断。

---

## Issue 7 — `walk_files` 不防符号链接环（Low）

### 现状与根因

[workspace.py](../../yate/services/workspace.py) 的 `walk_files` 用
`is_dir()` 判断（跟随符号链接），`ln -s . loop` 这类环导致无限递归
（5000 文件上限挡不住纯目录环）。

### 修复策略

`walk_files` 不进入符号链接目录：

```python
if child.is_dir() and not child.is_symlink():
    stack.append(child)
```

### 测试

- `test_walk_files_does_not_follow_symlinked_directories`：
  Windows 无特权（Symlink 需管理员/开发者模式）时自动 skip。

---

## 变更清单汇总（4 个提交，11 + 3 + 2 + 10 = 文件级累计 20 个）

| 提交 | 生产代码 | 测试 | 文档 |
|---|---|---|---|
| `05106d5` | document.py / buffer.py / editor.py / manager.py / extensions.py / pty_proc.py / fonts.py / workspace.py | test_editor_core.py / test_workspace_filter.py | — |
| `5190225` | buffer.py / document.py | test_editor_core.py | — |
| `b0d154d` | buffer.py | test_editor_core.py | — |
| `a89a720` | trust.py（新增）/ extensions.py / editor.py / commands.py | test_trust.py（新增）/ test_extensions.py / test_app_textual.py | extensions.en/zh.md / yaterc.en/zh.md |

## 验证策略（已执行）

1. `python -m pyright yate/ tests/ tools/` → 零诊断（硬门槛）；
2. `python -m pytest tests/ -q` → 628 passed, 15 skipped（平台相关）；
3. `python -m tools.smoke_test run` → 651/651 checks、62/62 scenarios；
4. 冒烟回归 `undo_redo` 由 Issue 3 初版引入、由 `5190225` 修复——
   印证冒烟套件对脏标记语义的守护价值。

## 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `.yate-tmp` 临时文件在崩溃时残留 | 低 | 低 | 命名固定、同目录可见，下次保存覆盖；文档无需提及 |
| undo 截断到 1000 步后老步骤不可撤销 | 极低 | 低 | vim 默认 1000，行业惯例 |
| `modified` 精确回退在大文件上的开销 | 低 | 低 | 仅计数不匹配时触发（脏状态翻转瞬间），远低于旧方案每键全文 join |
| `_goal_col` 在扩展直改行后过期 | 极低 | 低 | `mark_content_changed` 已清除 |
| 信任门控改变既有用户工作流（项目扩展不再静默加载） | 中 | 低 | 启动消息明确指引 `:trust`；一次确认永久生效；CHANGELOG 记录行为变更 |
---
