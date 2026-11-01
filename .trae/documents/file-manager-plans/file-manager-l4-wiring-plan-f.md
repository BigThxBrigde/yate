# plan-f：L4 全量接线 + 架构登记（wave-5）

## 输入
总纲 §三/§四/§六；plan-e 的 FileManagerFlows 公共接口
（`open_overlay()` / `open_fullscreen(initial_dir)` / `bind_exit(exit_app)`）。
事实基线：
- actions 表：`reg(name, fn, description)`，fn 形如
  `lambda ctx: editor.<flows>.<method>()`（actions.py:26-236；quick_open 先例
  214-215 走 `editor.overlays.open_file_palette()`）；
- commands 表：`reg(name, fn, description, arg_completer=...)`（commands.py:234 起；
  连字符命令先例 `project-replace` 355、`install-extension` 554）；
- vsc 键位：`_k("<alt-shift-p>", "command_palette", ..., ...)`（vsc.py:104）；
  `alt+shift+f` 全仓空闲（调研 #8）；
- vim 键位：`KeyBinding(parse_key("<alt-shift-s"), "toggle_screensaver", ...)`；
  vim.py:224；
- cli：argparse 定义区 43-236；`--hex` 旗标先例 230-235；互斥校验先例 323-324；
  YateApp 构造 481-493；`target = Path(args.path) if args.path else None`（400）；
- app：`__init__` 参数 85-97（`diff_files`/`hex_file` Optional 形态先例）；
  on_mount `--diff`/`--hex` 经 `call_after_refresh` push 模态屏（212-224）——
  **全屏形态唯一既定先例，逐行对齐**；
- 架构：`UI_FROZEN_FILES`（tests/test_architecture.py:193-250，dict[str, set[str]]）。

## 目标
三处入口全部接通（Alt+Shift+F / `:file-manager` / `--file-manager`）；
R11 白名单登记；app 级 pilot 验收。

## 独占文件清单
- `yate/actions.py`、`yate/commands.py`
- `yate/keymaps/vsc.py`、`yate/keymaps/vim.py`
- `yate/cli.py`、`yate/app.py`
- `tests/test_architecture.py`（仅 UI_FROZEN_FILES 一处登记）
- `tests/test_app_filemgr.py`（新建）

## 具体修改

### 1. actions.py（populate 表内，与 overlay 组相邻）
```python
reg("file_manager", lambda ctx: editor.filemanager_flows.open_overlay(),
    "open the file manager overlay (lf-style)")
```
（action 名蛇形 `file_manager`，命令名连字符 `file-manager`——两表命名域独立，
对齐 quick_open/command_palette 先例。）

### 2. commands.py（register_commands 内，overlay 组相邻）
```python
reg("file-manager", _file_manager,
    "open the lf-style file manager (Alt+Shift+F)")
```
`_file_manager = lambda/局部 fn: editor.filemanager_flows.open_overlay()`——
对齐同文件既有 `_files`/`_palette` 局部函数先例（353-354）。

### 3. keymaps（两套都加，同一 action 名）
- vsc.py：`_k("<alt-shift-f>", "file_manager", "Open file manager", <类别>)`
  ——类别取该文件 `command_palette` 同组常量（executor 就近）；
- vim.py：`KeyBinding(parse_key("<alt-shift-f>"), "file_manager",
  "Open file manager", EDT)`——对齐 toggle_screensaver 条目（224）分组。

### 4. cli.py
1. argparse（`--hex` 230-235 旁）：
   `parser.add_argument("--file-manager", nargs="?", const=".", metavar="PATH",
   help="open the lf-style file manager ([PATH], default cwd)")`；
2. 互斥校验（323-324 先例段）：`args.file_manager is not None and args.path`
   → `parser.error("--file-manager and positional PATH are mutually exclusive")`；
3. 解析（400 旁）：`fm_dir = Path(args.file_manager).resolve() if
   args.file_manager is not None else None`（`"."` → cwd）；
4. 构造传参（481-493）：`YateApp(..., filemanager_dir=fm_dir)`。

### 5. app.py
1. `__init__`（85-97）加关键字参数 `filemanager_dir: Path | None = None` 并存
   `self._filemanager_dir`（对齐 diff_files/hex_file 形态）；
2. `on_mount`（212-224 段，diff/hex push 之后）：
   ```python
   if self._filemanager_dir is not None:
       self.editor.filemanager_flows.bind_exit(self.exit)
       self.call_after_refresh(
           self.editor.filemanager_flows.open_fullscreen, self._filemanager_dir
       )
   ```
   （`call_after_refresh` 先例同段；bind_exit 在 push 前完成；`self.exit` 是
   App 动词绑定方法注入——L4 持有句柄合法，flows 不持。）
3. 浮层形态零 app.py 改动（flows.open_overlay 已接 actions）。

### 6. tests/test_architecture.py（R11 登记，单行）
`UI_FROZEN_FILES`（193-250）新增：
`"flows/filemanager_flows.py": {"filemgr"}`——只允许 import
`yate.editor_view.filemgr`（filemgr_model/preview 由 filemgr 间接持有，
flows 不直引）。

### 7. tests/test_app_filemgr.py（pilot 全链路，对齐 test_app_palette.py:23-33 模式）
前置：tmp_path 目录树；`app = YateApp(target=tmp_path)`；
`async with app.run_test(size=(120, 36)) as pilot`。

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_alt_shift_f_opens_overlay_and_esc_restores` | press("alt+shift+f") → Esc | `app.screen` 变为 FileManagerScreen 后还原（screen_stack 深度回 1）；焦点回编辑器（editor focused） |
| `test_command_file_manager_opens_overlay` | `:file-manager`（命令行走查或直接 registry 调用+palette 命令路径） | 同上浮层打开 |
| `test_action_file_manager_registered_in_both_keymaps` | 实例化 vsc/vim keymap | `<alt-shift-f>` 绑定 `file_manager`（双 keymap 各断言） |
| `test_fullscreen_startup_pushes_filemgr_screen` | `YateApp(target=tmp_path, filemanager_dir=tmp_path)` | run_test 后 `isinstance(app.screen, FileManagerScreen)`（wait_until 轮询 call_after_refresh 落地） |
| `test_fullscreen_open_file_switches_workspace` | j/l 选中文件 Enter（wait_until open 完成） | `app.screen_stack` 回主界面；`session.current.path == 该文件`；`workspace.root == 父目录` |
| `test_fullscreen_open_dir_sets_root` | 目录 Enter | `workspace.root == 目录` 且 explorer 树刷新（root 节点 path 相符） |
| `test_fullscreen_q_exits_app` | press("q") | app 退出（pilot 上下文结束，`app._exit` 或 return code 断言——executor 以 Textual 8.x 可观测面定） |
| `test_dirty_blocks_switch_and_reports` | 打开文件改一字节 → alt+shift+f → Enter 同文件 | report 消息含 `unsaved`；workspace root 未变 |
| `test_cli_flag_mutually_exclusive_with_path` | 直接调 `build_parser().parse_args` 两种组合 | 双方都给 → SystemExit(2)；单给 → 解析成功 |
| `test_cli_file_manager_defaults_to_cwd` | `parse_args(["--file-manager"])` | `args.file_manager == "."` |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/actions.py yate/commands.py yate/keymaps/vsc.py yate/keymaps/vim.py yate/cli.py yate/app.py tests/test_app_filemgr.py tests/test_architecture.py
.venv\Scripts\python.exe -m pytest tests/test_app_filemgr.py tests/test_app_palette.py tests/test_architecture.py tests/test_keymaps.py -q
```

## 风险与回滚
- argparse `nargs="?"` 与位置参数的贪婪匹配：`yate --file-manager D:\dir` 时
  PATH 进旗标（互斥校验兜底；`yate D:\dir --file-manager` 位置参数在前也合法）；
- `test_fullscreen_q_exits_app` 的退出可观测面依 Textual 版本而异，以
  `pilot.press("q")` 后 `app.return_code` / `app._exit_set` 实际属性为准
  （executor 查证，报告记录）；Ctrl+C 路径由 BINDINGS `ctrl+c` 同 action 覆盖；
- 回滚：各文件改动均为追加注册/单参数，独立成笔可逐文件还原。
