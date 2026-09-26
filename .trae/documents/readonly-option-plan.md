# 计划：只读选项与命令（issue IKHAD5）

## 一、背景

Gitee issue [IKHAD5](https://gitee.com/jermaine/yate/issues/IKHAD5) 要求为 yate 增加只读能力：

1. CLI 选项 `--readonly`：`yate path/to/file --readonly` 打开的文件为只读；**仅对文件参数有效，目录参数无效**。
2. ex 命令 `:set readonly=true` / `:set readonly=false` 切换当前文档只读态。

已与用户确认语义：**禁止编辑 + 禁止保存**（VS Code 式只读：输入/删除/粘贴/undo 等一切编辑被拦截并给出状态栏提示，`:w`/`:saveas` 拒绝写盘）。

分支：`issues/readonly-opt-impl`（已存在，本地=origin，是 master 的祖先：领先 0 / 落后 130 提交）。

## 二、架构设计

### 状态与拦截面

只读标志的唯一事实源：`TextBuffer.read_only: bool`（L0，`yate/editor_core/buffer.py`）。所有写路径最终汇聚到 `TextBuffer` 的公共变更方法，在 L0 统一拦截并抛 `BufferReadOnlyError`；用户可见的反馈在 L3 的三个分发/入口点统一给出。

```mermaid
flowchart TD
    subgraph 只读态的设置
        CLI["cli.py --readonly"] --> APP["YateApp(readonly=...)"] --> ED["Editor.startup_readonly"]
        ED --> OT["_open_target(): 参数是文件?"]
        OT -->|file| S1["doc.buffer.read_only = True"]
        OT -->|dir| SKIP["忽略（issue 规定）"]
        CMD[":set readonly=true/false"] --> SR["Editor.set_readonly()"] --> S2["session.doc.buffer.read_only = True/False"]
    end
    subgraph 拦截点（L0 护栏）
        S1 --> BUF["TextBuffer 公共变更方法<br/>_ensure_writable() → raise BufferReadOnlyError"]
        S2 --> BUF
    end
    subgraph 用户反馈（L3 捕获）
        KEY["按键（输入/vim 操作/action/补全接受）"] --> HK["Editor.handle_key() try/except"]
        PAL["命令面板 / 扩展触发 action"] --> EA["Editor.execute_action() try/except"]
        HK --> BUF
        EA --> BUF
        SAVE[":w / :saveas"] --> PS["前置检查 read_only → 拒绝"]
        REP["查找替换提交"] --> PR["前置检查 read_only → 拒绝"]
    end
    BUF -->|raise| MSG["message('buffer is read-only ...', warn)"]
    PS --> MSG
    PR --> MSG
```

### 拦截覆盖矩阵

| 写入路径 | 入口 | 拦截方式 |
|---|---|---|
| 按键输入（vsc 打字 `keymaps/base.py:277`、vim `keymaps/vim.py:183`）、动作表编辑、补全接受 | `Editor.handle_key` | try/except + message，返回 True（键已消费，遵守 R10） |
| 命令面板 / 扩展桥直接触发 action | `Editor.execute_action`（editor.py:643） | try/except + message |
| 保存 `:w` / 未命名另存 | `Editor.save_document`（:510）/ `_submit_save_as`（:538） | 前置检查 + message |
| 查找替换单处/全部（`SearchEngine.replace_one/replace_all`，editor.py:916 一带） | 替换提示条提交处理器 | 处理器前置检查 + message；search.py 两个方法顶部再防御性抛错（防止"先改行后 commit"造成半途损坏） |
| 扩展 API（`insert_text`/`replace_range`/`set_text`） | 扩展调用 L0 方法 | L0 抛错，经扩展既有错误通道呈现；extensions 文档补注记 |
| 越带直改 `buffer.lines` + `mark_content_changed()` | 扩展契约 | **不拦截**（属性赋值无法拦截，属既有契约），文档注明 |

### 架构合规对照

- 标志放 L0 `TextBuffer`：纯数据 + 行为自持，无 UI 依赖；`Document`/`EditorSession`/`EditorView` 结构零改动（状态栏只读 `buf.read_only`）。
- 不新增 Protocol / TYPE_CHECKING / Any；依赖方向全部向下（editor.py → editor_core 既有导入，仅补异常类导入）。
- R10：`handle_key` 捕获后 `return True`，不产生二次派发。
- `:set readonly` 粒度 = 当前活动文档（与 `:set filetype` 同粒度，复用 `set_filetype`（editor.py:1073）的 setter+message+refresh_ui 模式）；split 窗格共享同一 `Document`，自动同步。

## 三、实施步骤

### Phase 0 — worktree 准备与合并

1. `git worktree add D:\Programming\yate-readonly-opt-impl issues/readonly-opt-impl`
2. `git -C D:\Programming\yate-readonly-opt-impl merge master` → 预期 fast-forward 到 `a0a416c`（分支是 master 祖先，零冲突）。
3. 在 worktree 内准备解释器（对齐 yate-refine-arch 的既有做法）：若 `D:\Programming\yate-readonly-opt-impl\.venv` 不存在则创建并 `pip install -e .`。**不得**把主仓 `.venv` 重装指向 worktree（editable 安装会把 `yate` 解析回主仓代码，测试将测错对象）。
4. 将本计划文档移入 worktree 的 `.trae/documents/`（随分支提交，遵守仓库 docs(plans) 惯例）。

验收：`git -C <worktree> log --oneline -1` = a0a416c；`git status` 干净；`.venv\Scripts\python.exe -m pytest tests/ -q` 全绿（合并后基线）。

### Phase 1 — L0 只读护栏（editor_core）

文件：`yate/editor_core/buffer.py`、`yate/editor_core/search.py`、`yate/editor_core/__init__.py`

1. `buffer.py` 顶部定义 `class BufferReadOnlyError(Exception)`（含 docstring：只读缓冲区拒绝变更时抛出）。
2. `TextBuffer.__init__` 增加关键字参数 `read_only: bool = False`，存为 `self.read_only`。
3. 新增私有方法 `_ensure_writable(self) -> None`：`read_only` 为真时 `raise BufferReadOnlyError("buffer is read-only")`。
4. 在以下**公共变更方法**入口显式调用 `_ensure_writable()`（内部助手 `_delete_range`/`_apply_text` 不加，它们只被已护栏方法调用）：
   `set_text`、`undo`、`redo`、`insert_text`、`replace_range`、`delete_selection`、`delete_backward`、`delete_forward`、`indent_selection`、`outdent_selection`、`delete_lines`、`duplicate_line`、`move_line`、`join_lines`、`delete_to_line_start`、`paste`（`insert_newline`/`insert_tab`/`paste` 经 `insert_text` 间接覆盖，公共入口同样加一行防御）。
   `mark_content_changed` **不加**（见拦截矩阵）。
5. `search.py`：`replace_one`（:110 一带）与 `replace_all`（:115）开头加 `buffer._ensure_writable()` 同等检查（复用异常，防止 snapshot→直改 lines→commit 中途才失败）。
6. `editor_core/__init__.py` 导出 `BufferReadOnlyError`。

验收：`pyright yate/` 零诊断；`pytest tests/test_editor_core.py tests/test_session.py -q` 全绿。

### Phase 2 — L3/L4 语义接线

文件：`yate/editor.py`、`yate/app.py`、`yate/cli.py`、`yate/commands.py`、`yate/prompt_completion.py`

1. `Editor.__init__`（:87）加 `readonly: bool = False` 关键字参数，存 `self.startup_readonly`（docstring 注明：仅作用于启动文件参数）。
2. `_open_target`（:348）：两个文件分支（含"不存在即新建"分支）取 `_open_document` 返回的 doc，非 None 且 `startup_readonly` 时 `doc.buffer.read_only = True` 并 `log.info("opened read-only: %s", path)`；目录分支不动。
3. `Editor.handle_key`（:641 结尾处的方法体）整体包 `try/except BufferReadOnlyError` → `self.message("buffer is read-only (toggle with :set readonly=false)", kind="warn")` + `return True`。
4. `Editor.execute_action`（:643）同样包 try/except → message + `return True`。
5. `save_document`（:510）开头：`if doc.buffer.read_only: self.message("cannot save: buffer is read-only", kind="warn"); return`；`_submit_save_as`（:538）同样前置检查。
6. 查找替换提交处理器（定位 editor.py:916 `replace_all` 调用所在方法及单处替换分支）：开头前置检查 `read_only` → message + return。
7. 新增 `Editor.set_readonly(self, value: bool) -> None`（仿 `set_filetype` :1073：设 `session.doc.buffer.read_only`、`message(f"readonly: {'on' if value else 'off'}", kind="ok")`、`self.refresh_ui()`）。
8. `YateApp.__init__`（app.py:79）加 `readonly: bool = False`，透传给 `Editor(...)`。
9. `cli.py`：`build_parser` 增加 `--readonly`（store_true，help 注明仅对文件参数有效）；`main` 的两处 `YateApp(...)`（diag :308 与正常运行 :320）都传 `readonly=args.readonly`。
10. `commands.py` `_set`（:125）：新增 `elif key == "readonly":` 分支——值严格校验（true/on/1/yes → True；false/off/0/no → False；其余 warn），调 `editor.set_readonly(val)`；同步更新 usage 提示文案与 `reg("set", ...)`（:198）描述。
11. `prompt_completion.py`：`_SET_OPTIONS`（:21）加 `"readonly"`；值补全分支加 `elif key == "readonly": vals = ("true", "false")`（仿 show_hidden :76）。

验收：`pyright yate/ tests/` 零诊断；`pytest tests/test_cli.py tests/test_prompt_completion.py tests/test_app_textual.py -q` 全绿。

### Phase 3 — L2 状态栏指示

文件：`yate/editor_view/icons.py`、`yate/editor_view/statusbar.py`

1. `icons.py` 增加 `LOCK = "\uf023"`（Nerd Font 锁形，与既有图标同族）。
2. `statusbar.py` `refresh_status`：`buf.read_only` 时在文档名/修改点（DOT :125-126）旁追加 `LOCK` 标记（醒目色，如 `t.yellow`/`t.red`），并把其宽度计入 :107-110 的预算计算（与 `dot_cells` 同法）。

验收：pyright 零诊断；用 textual-pilot 冒烟断言只读时状态栏出现锁标记。

### Phase 4 — 测试与文档

测试（新增/扩展）：

| 文件 | 内容 |
|---|---|
| `tests/test_editor_core.py` | read_only 默认 False；ctor 传参生效；护栏方法逐一断言抛 `BufferReadOnlyError` 且内容/`content_edits`/undo 栈不变；解除后可编辑；`replace_one`/`replace_all` 抛错且缓冲区未被部分修改 |
| `tests/test_cli.py` | `build_parser` 解析 `--readonly`（默认 False / 置 True） |
| `tests/test_prompt_completion.py` | `:set ` 键补全含 readonly；`:set readonly=` 值补全 true/false |
| `tests/test_app_textual.py`（或新 pilot 用例） | pilot：`:set readonly=true` 后输入字符无效且状态栏有锁；`:set readonly=false` 恢复；`--readonly` 启动文件后打字无效、`:w` 提示拒绝 |
| `tools/smoke_test/scenarios/view.py`（:101 一带 :set 矩阵） | 增加 readonly=true/false 两行的消息断言 |

文档（实施时以 `yate/editor_view/manual.py` 实际加载路径定位 manual/changelog 双语文件）：

- 用户手册 en/zh：CLI 选项表加 `--readonly`；`:set` 选项节加 `readonly=true|false`。
- changelog en/zh：按既有条目格式追加本特性。
- `yate/docs/extensions.en.md` / `extensions.zh.md`：buffer API 表注记"只读缓冲区的变更方法会抛 `BufferReadOnlyError`；`mark_content_changed` 不受限制"。
- `yaterc.en/zh.md` **不改**（readonly 不进 yaterc，纯运行时开关）。

验收：`.venv\Scripts\python.exe -m pyright yate/ tests/` 零诊断；`.venv\Scripts\python.exe -m pytest tests/ -q` 全绿（在 worktree 根目录、用 worktree 自己的 .venv 执行）。

### Phase 5 — 提交（英文 conventional，见 git-commit-message 规则）

建议切分（可按实际调整，不 push）：

1. `feat(editor-core): guard buffer mutations behind a read-only flag`
2. `feat(editor): add --readonly startup flag and :set readonly option`（editor/app/cli/commands/completion/statusbar）
3. `test(editor): cover the read-only buffer, command and startup flows`
4. `docs: document the readonly option in manual, changelog and extension notes`

## 四、边界情况

- `--readonly` + 目录参数 → 忽略，不报错（issue 规定"无效"）。
- `--readonly` + 不存在的文件路径 → 新建缓冲区即只读；用户可 `:set readonly=false` 解锁（行为一致、可预期）。
- 只读拦截不破坏 undo 栈与 coalescing（拦截发生在任何 snapshot 之前）。
- welcome 页与普通新建缓冲区永不受 `--readonly` 影响。
- split 窗格共享同一 Document → 只读态跨窗格同步，符合预期。
- 扩展直改 `lines` 的越带通道保持既有契约（无法拦截），文档注明。
