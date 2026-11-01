# 子计划 fix-fm — M1 POSIX 根层死胡同 + m3 死分支 + m4 指南纠偏 + 剪切回归用例

**Worktree 根**：`D:\Programming\yate-file-manager`（分支 `feat/file-manager`）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 M1 / m3 / m4 与 §B1
修法第 2 条用例（先读对应小节全文）。

## 独占文件

- `yate/editor_view/filemgr.py`
- `yate/editor_view/filemgr_model.py`
- `tests/test_filemgr.py`
- `tests/test_filemgr_model.py`
- `yate/docs/file-manager.en.md`
- `yate/docs/file-manager.zh.md`

## 修改点

### M1（major）— 空盘符层不应存在（两处入口判据）

- `filemgr.py:163-167`（`__init__` 起始态）：起始目录为文件系统根且 `list_drives()` 为空
  时**不得**落 `_cwd = None`。评审修法：
  ```python
  start = (initial_dir or root or Path.cwd()).resolve()
  at_root = start.parent == start
  self._cwd: Path | None = None if at_root and workspace.list_drives() else start
  ```
- `filemgr.py:713-730`（`action_up`）：根层尝试进盘符层前加判据——
  ```python
  if self._cwd.parent == self._cwd:
      if not self.workspace.list_drives():
          return  # POSIX: no drive level, stay at the file-system root
      self._cwd = None
      self._reload()
      return
  ```
  与现状融合；`action_up` docstring 说明「盘符层仅当 `list_drives()` 非空时存在（Windows）」。
- **新增 POSIX 回归用例**（`tests/test_filemgr.py`，平台无关——monkeypatch 掉 list_drives）：
  `monkeypatch.setattr(Workspace, "list_drives", lambda self: [])`，屏幕起始目录取文件系统根
  语义（用 monkeypatch 的假根，或直接构造 `_cwd` 等价根状态），按 `h` 断言 `_cwd` 不变、
  中栏仍列出原内容；以及 `list_drives()` 非空（现状 Windows 路径）时根层按 `h` 才进盘符层。
  注意：不要在真实 `/` 上做破坏操作；用 tmp_path 构造 + monkeypatch `Path.parent` 不可行，
  可参考现有 Windows-only 用例（`tests/test_filemgr.py:818-849`）的构造方式，把「根」
  判据通过被测状态直接驱动。先按现状跑一次证明红（M1 行为：进入空盘符层死胡同），
  再修转绿。

### m3（minor）— `parent_and_siblings` 删除不可达根分支

- `filemgr_model.py:233-248`：删掉 `if current.parent == current:` 分支（含 `list_drives()`
  调用与 `None` 返回），函数收敛为「返回 `(current.parent, list_dir(current.parent))`」；
  docstring 同步（唯一调用点 `filemgr.py:363-366` 的前置守卫保证 `_cwd` 非根）。
- `tests/test_filemgr_model.py:212-234`：删除断言死行为的用例（monkeypatch `sys.platform`
  后断言左栏盘符条目那几条）；若其中有可保留的正常路径断言则平移，不留死假设。

### m4（minor）— 双语指南纠偏

- `yate/docs/file-manager.zh.md:16-17`：§1「到达文件系统根后，父目录栏变为盘符虚拟层」
  改为「中栏列出盘符（左栏占位 `(no parent directory)`）」，并补「在文件系统根按 `h`
  进入盘符层（仅 Windows）」。
- §3 导航表 `h`/`Left`/`Backspace` 行补「在文件系统根进入盘符层（Windows）」。
- `yate/docs/file-manager.en.md:18-21` 同步英文。

### 剪切同场景回归用例（评审 §B1 修法第 2 条）

`tests/test_filemgr.py` 补一条：复制臂已有 B1 守卫（prfix-ws 批实现，**直接按契约写用例，
不改 workspace.py**）之外，**剪切**目录进自身子树应被 `shutil.move` 的 `Error("Cannot move
a directory ... into itself")` 挡住，屏幕输入行报 `paste failed:`——锁定既有行为防回归。
（跑这条用例时剪切臂无需新实现，属行为锁定用例；若 prfix-ws 尚未完成导致复制臂守卫
未在位，本条仍应绿，因为它只断言剪切路径。）

## 自测

`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/`（0 诊断）+
`.venv\Scripts\python.exe -m pytest tests/test_filemgr.py tests/test_filemgr_model.py -q`（全绿，
按退出码判定）。

## 执行纪律

- 禁触碰其他文件；`workspace.py` / `commands.py` 等由并行批次修改，**不要**为让本批用例
  通过去改它们。
- M1 用例先红证据写进汇报；完成后**不提交**，汇报：改动文件、diff 要点、红证据、自测退出码。
