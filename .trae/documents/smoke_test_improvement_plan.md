# 冒烟测试改进计划

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - 骨架已按任务 3 拆分：`tools/smoke_test/` 下
>   `cli.py` / `report.py` / `baselines.py` / `harness.py` / `testsuite.py`
>   + `scenarios/`（`core` / `edit` / `search` / `files` / `panes` / `explorer` /
>   `view` / `integration` / `regression` / `stress` / `aliases` / `_base`），
>   `scenarios/__init__.py` 聚合各模块的 `SCENARIOS` 并重导出。
> - `smoke_baselines/` 已入库（`*.json`）；CLI 已支持 `--tag` / `--scenario` /
>   `--coverage` / `--json` / `--no-invariant` / `--repeat` / `--seed` /
>   `--svg*` / `--skip-slow` / `--no-color` / `--width` / `--quiet` /
>   `--fail-only` / `--report` 等选项。
> - 任务 1 的产品缺陷已修复：vim 键位支持 `ctrl+/` 切回 vsc；场景入口改用
>   F5（vsc 模式 `:` 非绑定键）。
> - 场景总数约 59（含 R 组回归与 S 组压力），全局不变量钩子已接入。

## 与当前实现的差异（回写，2026-09-22）

- **§现状盘点已过时**：`theme_switch` / `help_modal` 已改用 F5 入口、
  `keymap_toggle` 已修复；`tools/smoke_baselines/` **已存在**（62 个 `.json`），
  `compare` 不再必然输出 `no baselines`。
- **报告渲染**：不再集中在 `testsuite.py::_print_table`（232–249 行），
  已拆到 `tools/smoke_test/report.py`；`testsuite.py` 只保留 main 与对外重导出。
- **文件组织**（与任务 3 的建议一致）：`cli.py` / `report.py` / `baselines.py` /
  `harness.py` / `testsuite.py` + `scenarios/`（13 个模块），`SCENARIOS` 由
  `scenarios/__init__.py` 按 core→功能组→regression/stress 顺序聚合。
- **CLI 选项**已提供：`--tag` / `--scenario` / `--coverage` / `--json` /
  `--report` / `--no-invariant` / `--repeat` / `--seed` / `--svg` /
  `--svg-rows` / `--skip-slow` / `--no-color` / `--width` / `--quiet` /
  `--verbose` / `--fail-only`。
- **场景数量**：`Scenario(` 定义约 59–62 个（含 R 组回归与 S 组压力）。

> 目标：`python -m tools.smoke_test` 从「3 个失败」变成全绿基线，补充覆盖高频用户路径的场景，并把 PASS/FAIL 报告改造成一眼可读的彩色报告。

---

## 现状盘点

`python -m tools.smoke_test run` 当前输出（已实测）：

```
type_save_find  PASS
file_palette    PASS
keymap_toggle   FAIL (1)
  [XX] back_to_vsc: expected='vsc' actual='vim'
theme_switch    FAIL (1)
  [XX] latte_theme: expected='latte' actual='mocha'
help_modal      FAIL (1)
  [XX] modal_open: expected=2 actual=1

Total: 16 ok, 3 fail     (exit 1)
```

- 共 5 个场景 / 19 项检查，3 项失败。
- `tools/smoke_baselines/` **不存在**，`compare` 子命令目前必然输出 `no baselines` 并 exit 2。
- 报告渲染集中在 `tools/smoke_test/testsuite.py::_print_table`（第 232–249 行），纯 `print` 无颜色、无汇总、无耗时。

---

## 任务 1：修复 3 个失败的冒烟测试

### 1.1 `theme_switch` / `help_modal` —— vsc 模式下 `:` 不是绑定键

**根因（已定位，非猜测）：**

`yate/keymaps/vsc.py:88-91` 有明确注释：

```python
# NOTE: ":" is intentionally not bound in vsc mode - it is typed
# literally. Reach the ex command line with F5 (or the command
# palette via alt+shift+p).
_k("<f5>", "command_prompt", "Ex command line (:w :q :e :! ...)", VIEW),
```

冒烟脚本第 157、176 行用 `await pilot.press("colon")` 试图进入命令行；在 vsc 模式下 `:` 只会被当作普通字符插入缓冲区，随后的 `theme latte` / `help` 也一并进入缓冲区，`enter` 只是换行——命令从未执行，所以主题仍是 `mocha`、弹层从未打开。

手册 `yate/resources/manual.en.md:328` 同样写明 "`:` is not a vsc-mode binding"。

**实测证据**（临时探针脚本，已删除）：

```
prompt mode: command                 # F5 后 prompt_bar.active_mode
theme after :theme latte: latte      # F5 → "theme latte" → enter 生效
stack after :help: 2                 # F5 → "help" → enter → HelpScreen
```

**修复方案：** 把这两个场景的入口从 `colon` 换成 `f5`（命令文本保持不带前导 `:`——`PromptBar` 自己显示 `:` 前缀，输入内容是命令名本身）。

```python
# theme_switch
await pilot.press("f5")          # 原: await pilot.press("colon")
await pilot.pause()
for ch in "theme latte":
    await pilot.press(ch)
```

`help_modal` 同理。`_type_save_find` 用的是 `ctrl+f`（`find` 已绑定）不受影响；若后续新增 vim 场景，vim 模式下 `:` 才是合法入口（`yate/keymaps/vim.py:392`）。

**验证：** `python -m tools.smoke_test run --scenario theme_switch --scenario help_modal` → 两项全 PASS。

---

### 1.2 `keymap_toggle` —— vim 键位缺少 `ctrl+/` 绑定，切换是单向的

**根因（已定位）：**

- `yate/keymaps/vsc.py:99`：`_raw("\x1f", "toggle_keymap", "Toggle vsc/vim keymap (ctrl+/)", VIEW)` —— vsc 侧有绑定。
- `yate/keymaps/vim.py`：全文件无 `\x1f`、无 `toggle_keymap`（grep 仅命中 vsc.py）。
- vim 的 `handle_key`（`vim.py:107`）只对 `_FUNCTION_KEYS`（F1–F12）查绑定表，其余键走 normal 模式分发；`\x1f` 不是可打印字符，最终被静默忽略。

**实测证据：** 第一次 `ctrl+/` → `vim`；第二次 `ctrl+/` → 仍是 `vim`；用 `:vsc` 可以切回。

这与手册 `manual.zh.md:242` / `manual.en.md:256`「`Ctrl+/` 在两套键位间切换」矛盾——**这是产品缺陷，不是测试写错**，因此推荐修产品而非改测试。

**修复方案（推荐 A）：** 在 `yate/keymaps/vim.py::VimKeymap.handle_key` 开头加入 raw 键分支，并在 `build_bindings()` 补帮助条目（F1 面板与 `lookup` 共用该表；`\x1f` 非单字符，不会与 normal 模式单键命令冲突）。

```python
def handle_key(self, ctx: ActionContext, key: str) -> bool:
    if key == "\x1f":                     # ctrl+/ : back to vsc
        self.pending = ""
        self.count_str = ""
        ctx.app.toggle_keymap()
        return True
    if key in _FUNCTION_KEYS:
        ...
```

```python
# build_bindings() 末尾（HLP 分类）
KeyBinding("\x1f", "toggle_keymap", "Toggle vim/vsc keymap (ctrl+/)", HLP),
```

`toggle_keymap` 动作已在 `yate/actions.py:168` 注册，`YateApp.toggle_keymap()` 在 `app.py:584`，可直接调用。

**备选 B（不推荐）：** 把场景第二个断言改成用 `:vsc` 命令切回（实测可行）。这样测试会变绿，但掩盖了「手册承诺的双向切换实际单向」这一缺陷。

**验证：**

1. `python -m tools.smoke_test run --scenario keymap_toggle` → 3/3 PASS。
2. 补一条 `tests/` 用例：构造 vim 键位 → 派发 `\x1f` → 断言 `app.keymap_name == "vsc"`（放在 `tests/test_app_textual.py`，与既有 headless 测试同风格）。
3. `pytest -q` 无回归。

---

## 任务 2：大规模扩充冒烟场景（5 → 约 59）

现有 5 个场景只覆盖了「输入/保存/查找」「快速打开」「键位切换」「主题」「帮助弹层」，编辑语义、选择、替换、分屏、文件树、命令面板、退出守卫等主路径全部空白。按功能面补齐 **54 个新场景**（P0 27 / P1 21 / P2 6），其中专门划出两组用于「护住稳定性」：

- **R 组（回归防护）**：把 `.trae/documents/` 里记录过的历史修复逐条钉上冒烟，防回退。
- **S 组（稳定性与不变量）**：压力 / 边界 / 随机按键，外加一套**每个场景自动执行的全局不变量体检**。

### 2.1 标签化

给 `Scenario` 增加 `tags: tuple[str, ...]` 字段，配合任务 3 新增的 `--tag` 过滤，便于只跑某个功能面（如 `run --tag explorer`）或只跑回归（`run --tag regression`）。标签集合：`edit` / `select` / `search` / `files` / `panes` / `explorer` / `command` / `view` / `integration` / `regression` / `stress`。

### 2.2 场景清单

**A. 编辑与历史 `edit`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| A1 | `undo_redo` | P0 | 输入 → `ctrl+z` → `ctrl+y` | `buffer.lines` 回到原文 / 再恢复；`doc.modified` |
| A2 | `duplicate_delete_line` | P0 | `ctrl+d` 复制行、`ctrl+shift+k` 删行 | 行数、首行内容 |
| A3 | `move_line_block` | P0 | `alt+↑` / `alt+↓` 移动行 | 两行顺序互换 |
| A4 | `indent_outdent` | P0 | `ctrl+]` 缩进、`shift+tab` 反缩进 | 行首空格数 |
| A5 | `join_lines` | P0 | `ctrl+j` 合并行 | 行数 -1、合并后文本 |
| A6 | `clipboard_roundtrip` | P0 | 选区 `ctrl+c` → 移动 → `ctrl+v`；整行 `ctrl+x` | `buffer.selected_text()`、`has_selection()`、粘贴后文本 |
| A7 | `word_motion_bounds` | P1 | `ctrl+←/→` 词跳转、`home/end`、`ctrl+home/end` | `buffer.cursor` 行列 |
| A8 | `autoindent_newline` | P1 | 缩进行回车保持缩进、`tab` 插入 | 新行前缀空格 |
| A9 | `vim_modal_editing` | P0 | `:vim` → `i` 插入 → `esc` → `dd` → `:w` | 缓冲内容、vim 模式枚举、落盘文件 |

**B. 选择 `select`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| B1 | `selection_extend_clear` | P1 | `shift+←` 扩展 → `esc` 清除 | `has_selection()` True→False、`selected_text()` |
| B2 | `select_all_indent` | P1 | `ctrl+a` 全选 + 缩进 | 所有行缩进、`anchor` 清除 |

**C. 搜索 / 替换 / 跳转 `search`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| C1 | `find_next_prev_wrap` | P0 | `ctrl+f` 查找、`f3` 下一处、回环 | `search.query`、`search.index` 回绕 |
| C2 | `replace_single_all` | P0 | `f4` 两段输入（查找串 / 替换串），单次 + 全部 | 替换后 `buffer.lines` |
| C3 | `goto_line_two_ways` | P0 | `ctrl+g` 跳行 与 `:42` | `buffer.cursor[0]` |
| C4 | `find_backward` | P1 | `?` 反向查找（`find_back` 模式） | `search.matches` 命中方向、`index` |

**D. 文件 / 标签 / 退出 `files`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| D1 | `open_path_prompt` | P0 | `ctrl+o` 输入路径打开 | `doc.name`、`doc.path` |
| D2 | `save_as_flow` | P0 | `:w other.txt` 另存 | 新文件存在、`doc.path`/标签名更新、`modified=False` |
| D3 | `new_buffer_close_tab` | P0 | `ctrl+n` 新建 → `ctrl+w` 关闭 | `len(app.docs)`、`doc_index` 收敛 |
| D4 | `tab_cycle` | P0 | 两文件间 `ctrl+pgdn/pgup`（或 `:bn/:bp`） | `doc_index`、`doc.name` 交替 |
| D5 | `welcome_screen` | P0 | 无 target 启动的欢迎页 | 缓冲为欢迎内容、无路径 |
| D6 | `quit_guard_wq` | P0 | 脏缓冲 `:q` 被拦 → `:wq` 保存退出 / `:q!` 强退 | 拦截时仍在运行 + warn 消息；`:wq` 后落盘并退出 |
| D7 | `filetype_override` | P0 | `.py` 自动识别 → `:set filetype=md` → `auto` 还原 | `doc.filetype`、`filetype_override`、`app.mode_label()` |

**E. 分屏 `panes`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| E1 | `split_vs_sp_only` | P0 | `:vs` / `:sp` / `:only` / `:close` | `app.panes.leaf_count` 1→3→1 |
| E2 | `split_with_file` | P1 | `:vs other.txt` 分屏并打开指定文件 | 叶子数、活动文档名 |
| E3 | `pane_focus_window_keys` | P1 | `ctrl+w` + 方向/`ctrl+w` 组合移动焦点 | 焦点所在叶子变化、单窗格时提示 |

**F. 文件树 `explorer`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| F1 | `explorer_visibility_focus` | P0 | `ctrl+b` 显隐、`ctrl+e` 聚焦、`ctrl+1` 回编辑器 | `explorer_tree` 可见性、焦点 widget |
| F2 | `explorer_crud` | P0 | prompt 三段：新建文件 / 重命名 / 删除 | 磁盘文件存在性、`app.docs` 路径同步、树刷新 |
| F3 | `explorer_delete_open_folder` | P0 | 删除含已打开标签的文件夹 | 标签被关闭、`app.docs` 收敛（**覆盖刚修复的 LSP `didClose` 路径**） |
| F4 | `explorer_hidden_toggle` | P1 | `:set show_hidden=on` | `workspace.show_hidden` 与树节点数变化 |

**G. 命令 / 弹层 / 外观 `command` `view`**

| # | 场景 | P | 用户路径 | 关键断言 |
|---|---|---|---|---|
| G1 | `command_palette_run` | P0 | `alt+shift+p` 模糊选命令执行 | 面板开关、命令生效（如主题名变化） |
| G2 | `theme_switch_invalid` | P0 | `:theme` 无参列表、`:theme nope` 非法名 | 非法时不切换且有报错消息 |
| G3 | `command_history_recall` | P1 | 命令行上下键取回历史 | `prompt_bar` 输入值 |
| G4 | `manual_changelog_modals` | P1 | `F8` 手册、`:changelog` | `screen_stack` 2 → 1（返回后恢复） |
| G5 | `set_options_matrix` | P1 | `:set keymap/theme/show_hidden/terminal_height`，含非法值 | 各选项生效、非法值仅告警不生效 |
| G6 | `status_mode_label` | P1 | vim 模式切换时状态栏标签 | `app.mode_label()` 文本随模式变化 |

**H. 集成 / 边界 `integration`（P2，先验证确定性再纳入）**

| # | 场景 | 用户路径 | 注意事项 |
|---|---|---|---|
| H1 | `shell_command_output` | `F2` 执行 `python -c "print(...)"` 输出浮层 | Windows 无 `echo` 可执行文件，统一用 `sys.executable` |
| H2 | `terminal_panel_toggle` | `` ctrl+` `` 开关集成终端 | spawn 子进程，慢且平台相关，可标记 `slow` |
| H3 | `diagnostics_empty_state` | LSP 关闭时 `:diagnostics` 行为 | 断言空状态文案，不依赖真实 server |
| H4 | `large_file_scroll` | 2000 行文件 `page_down` 翻页 | 断言视口 top 前移，避免断言具体渲染 |

### 2.3 覆盖矩阵（场景组 → 被测模块）

| 场景组 | 主要覆盖 |
|---|---|
| A / B | `editor_core/buffer.py`、`keymaps/vsc.py`、`keymaps/vim.py` |
| C | `editor_core/search.py`、`app.py` 查找替换流程 |
| D | `app.py`（save/quit/docs/tabs）、`editor_core/document.py`、`editor_syntax/` |
| E | `editor_view/panes.py`、`app.py` 窗格命令 |
| F | `app_features/explorer.py`（含刚修复的 LSP `didClose`）、`editor_view/explorer.py` |
| G | `app_features/commands.py`、`editor_view/commandline.py`、`palette.py`、`manual.py`、`editor_view/theme.py` |
| H | `app_features/terminal.py`、`diagnostics.py`、`editor_view/editor.py` |

### 2.4 编写规约

- 全部在 `pilot.run_test()` 下 headless 跑，不碰真实终端。
- 禁用副作用：`YATE_PYTHON_LSP=off`（testsuite 顶部已 `setdefault`）、不触发字体安装、不联网；shell/终端场景限定在 P2 且用 `sys.executable -c`。
- 只用 `pilot.pause()` 推进，禁止 `sleep` 赌时序；确需等待异步完成的用轮询 helper（可复用 `tests/test_app_textual.py:32` 的 `wait_until`）。
- 断言一律读 app 状态（`app.doc` / `app.buffer` / `app.docs` / `app.panes` / `app.search` / `app.prompt_bar` / `app.screen_stack` / `theme.active()`），截图仅用于 svg 基线。
- 单场景目标 < 3s，全套 < 60s；每步按键后 `pause()`。
- 每个场景独占 `tmp` 子目录，文件名与内容固定（避免路径排序/时间影响基线）。
- **全局单例状态必须还原**：主题、键位、`show_hidden` 等在场景结束显式复位（现有 `theme_switch` 已这么做），否则结果会依赖执行顺序。

### 2.5 实施要点

1. 每个场景写成 `async def _xxx(tmp: Path) -> ScenarioResult`，沿用 `Check(label, expected, actual)` + `_snapshot(app, tmp)` 结构。
2. `Scenario` 增 `tags` 字段并追加进 `SCENARIOS`（`testsuite.py:189`）；场景数量上去后建议按标签拆到 `scenarios/` 子模块（见任务 3 的文件拆分）。
3. 全部加完后统一跑 `python -m tools.smoke_test snapshot` 生成 `tools/smoke_baselines/*.json`（该目录当前不存在，需创建；若不想入库则在 `.gitignore` 声明）。
4. 命令名以 `yate/app_features/commands.py:67-278` 注册表为准（`w/write`、`q/quit`、`q!`、`wq`、`e/edit`、`sp/split`、`vs/vsplit`、`only`、`close`、`bn/bp`、`bd`、`set`、`theme`、`filetype`、`help`、`manual`、`changelog`、`explorer`、`diagnostics`…），动作名以 `yate/actions.py:64-168` 为准，避免臆造。

### 2.6 R 组：回归防护 `regression`（防止历史修复回退）

`.trae/documents/` 里积累的修复都是真实踩过的坑，但**没有任何一条被冒烟覆盖**——改坏了也没人发现。逐条钉上：

| # | 场景 | P | 守护的修复 | 用户路径与断言 |
|---|---|---|---|---|
| R1 | `regress_wq_multi_tab` | P0 | `wq_safety_plan`（多 tab dirty 被静默丢弃） | 两个 tab，只保存当前 tab 后 `:wq` → **不应退出**；断言仍在运行、`len(app.docs)` 未丢、有 warn 提示 |
| R2 | `regress_unicode_save` | P0 | `wq_safety_plan`（`UnicodeEncodeError` 未被捕获 → 进程终止） | 保存含当前编码无法表示字符的缓冲 → 断言 app 未崩溃、`doc.modified` 仍为 True、有 error 消息 |
| R3 | `regress_typing_flicker` | P0 | `typing_flicker_debounce_plan` + `highlight_comment_flicker_plan` | 连续输入 20 字符 → 断言高亮 token 缓存不在击键后整屏脱色（`_tokens_for` 非空、`content_version` 单调） |
| R4 | `regress_split_panes` | P0 | `split_panes_plan` | `:vs`/`:sp`/`:only` 后叶子数与焦点稳定（与 E1 视角不同：此处断言**焦点与文档绑定**不串台） |
| R5 | `regress_tab_click` | P1 | `scrollbar_tab_click_plan` | 点击 `#tabbar` 上的非活动标签切换文档（需先确认 `pilot.click()` 在该 Textual 版本可用） |
| R6 | `regress_overlay_theme` | P1 | `overlay_theme_consistency_plan` | 切到 latte 后打开 F1/F8/输出浮层，断言弹层 token 与主主题同源 |
| R7 | `regress_completion_staleness` | P1 | `completion_staleness_check_plan` | 触发补全后继续输入 → 不弹出/不接受陈旧项（LSP off 时走 buffer words 路径） |
| R8 | `regress_diagnostics_cmd` | P1 | `diag_command_plan` | LSP 关闭时 `:diagnostics` 不崩且给出空态提示 |
| R9 | `regress_theme_expansion` | P1 | `themes_expansion_plan` | 遍历 `theme.available()` 逐个切换再还原，断言无异常且终态为 mocha |

> R 组的价值不在「多测几条路径」，而在**把事故变成断言**：每新增一个历史修复，就往这张表补一行。建议在 `tests/` 之外单列一个 `HISTORY_FIXES` 注释，标明每行对应的 plan 文档，方便回溯。

### 2.7 S 组：稳定性与不变量 `stress`

| # | 场景 | P | 用户路径 | 断言 |
|---|---|---|---|---|
| S1 | `stress_key_fuzz` | P1 | 固定种子伪随机 200 次按键（可打印字符 + 少量编辑键） | app 仍在运行、缓冲可保存、光标合法、无未捕获异常 |
| S2 | `stress_many_tabs` | P1 | 连续打开 20 个文件再逐个关闭 | `app.docs` 收敛到 1、`doc_index` 合法、无残留 |
| S3 | `stress_rapid_toggles` | P1 | 快速连续切换主题 / 键位 / 文件树各 10 次 | 终态一致（主题 mocha、键位 vsc、树可见性还原），中途无异常 |
| S4 | `stress_reopen_same_file` | P1 | 打开 → 修改不保存 → 关闭 → 再打开 | 读到的是磁盘内容，不是内存残留 |
| S5 | `stress_large_file` | P2 | 5000 行文件：打开 → 末尾插入 → 保存 | 行数与磁盘一致、耗时可接受 |
| S6 | `stress_long_line` | P2 | 单行 10000 字符：渲染 + 光标移动 | 不崩、光标不越界 |

**全局不变量钩子（贯穿所有场景，含既有的 5 个）** —— 这是「加 case 保稳定」性价比最高的一步：

runner 在每个场景结束后自动追加一组隐藏检查 `assert_invariants(app)`，任何一条不过即该场景 FAIL：

1. 光标合法：`0 <= row < len(buffer.lines)` 且 `0 <= col <= len(buffer.lines[row])`；
2. 栈干净：非弹层场景下 `len(app.screen_stack) == 1`；
3. 无未捕获异常：场景全程未进入 crash 态（`app.return_code is None` 且未抛到 pilot）；
4. 全局单例还原：主题 / 键位 / `show_hidden` 回到场景开始前的值（runner 自动快照 → 还原 → 比对）；
5. 保存一致性：凡断言过 `saved` 的场景，再读一次磁盘与 `buffer.lines` 比对；
6. 编辑可逆：编辑类场景结束前 `undo` 到栈底，断言能回到初始文本。

### 2.8 覆盖率度量（把「测了多少」变成可量化指标）

仅有场景数量不足以说明稳定性。给 runner 加两个计数钩子：

- 包装 `app.run_command`：记录被冒烟执行过的命令名；
- 包装 `app.execute_action`：记录被触发过的动作名。

报告新增 `--coverage`：输出 `commands 28/33 (85%)`、`actions 24/48 (50%)` 与**未覆盖清单**（对照 `CommandRegistry.names()` / `ActionRegistry.names()`）。目标：先做到命令覆盖 ≥ 60%、动作覆盖 ≥ 50%，再按缺口补场景。这样新增场景不再是凭感觉，而是对着缺口补。

---

## 任务 3：输出报告更美观直观

### 现存的观感问题

`_print_table`（`testsuite.py:232-249`）目前：纯文本无颜色；失败项与成功项混排无层级；`expected=.. actual=..` 全部平铺；svg 行用 `[:100]!r` 打印 repr 噪声；无耗时、无汇总、无进度；`compare` 的 `MATCH/DRIFT` 与 diff 同样无高亮。

### 改造设计（Rich —— 已随 textual 引入，无需新依赖）

1. **头部概览 Panel**：yate 版本、`python` / `textual` 版本、终端宽度、起始时间、场景总数。
2. **运行期进度**：`rich.progress.Progress` 或 `console.status(...)` 显示「正在运行 3/15 split_panes」，避免长时间无输出。
3. **结果 Table**（列：场景 / 状态 / 检查数 / 耗时）：
   - 状态列 `✔ PASS`（绿）/ `✘ FAIL(1)`（红）；
   - 检查数列渲染 `7/8`，失败时该单元格标红；
   - 表格 `box=rich.box.SIMPLE_HEAVY`，`overflow="fold"`，窄终端不炸版。
4. **失败详情默认展开、成功默认折叠**：只把失败 `Check` 渲染成两行（`expected` / `actual`），并对首处差异字符做红底高亮（`rich.text.Text` 分段）；成功项仅在 `--verbose` 下逐条列出，否则只显示计数。
5. **SVG 行可视化**：放进 `Panel`，按 y 排序、按终端宽度裁剪、去掉 `!r`；`--svg` 默认 6 行，新增 `--svg-rows N` 可调。
6. **尾部汇总**：总检查数通过率 + 进度条（`█░` 或 `BarColumn`）、总耗时、退出码提示（`exit 1` 用红字说明）。
7. **`compare` 着色**：`MATCH` 绿 / `DRIFT` 红；diff 行沿用 `+`（新增，绿）、`-`（缺失，红）、`~`（漂移，黄），`~` 行渲染 baseline / current 双行对照。
8. **分组小计**：场景数从 5 涨到约 42 后，单张表太长——按 `tag` 分组渲染多个 Table，每组带小计行（`edit 9/9`、`explorer 4/4`），失败组排在最前。
9. **覆盖率区块**：`--coverage` 时把命令/动作覆盖率与未覆盖清单单独渲染成一节（见 2.8），缺口项高亮，方便对着补场景。
10. **新增 CLI 选项**：`--tag`（按功能面过滤，可重复）/ `--no-color` / `--json PATH`（CI 机器消费）/ `--quiet` / `--fail-only` / `--svg-rows N` / `--width N` / `--skip-slow`（跳过 P2）/ `--repeat N`（重复跑 N 次查抖动）/ `--seed N`（fuzz 场景种子）。保持退出码语义（0 全通过、1 有失败、2 无基线）。
10. **可选**：`--report out.html` 用 `console.save_html()` 导出可归档的彩色报告。

### 代码组织（建议，场景变多后近乎必需）

`testsuite.py` 已 324 行，再加 37 个场景会膨胀到 1200+ 行。拆成：

```
tools/smoke_test/
  scenarios/           # 按标签分文件：edit.py / files.py / panes.py / explorer.py / ...
  report.py            # Rich 渲染（header / 分组表 / 失败详情 / 汇总）
  baselines.py         # snapshot + compare + diff
  cli.py               # argparse 子命令
  testsuite.py         # 只保留 main 与对外重导出（兼容既有导入路径）
```

`python -m tools.smoke_test` 与 `from .testsuite import main` 保持不变。

---

## 实施顺序（每步完成即本地提交）

**提交约定**：沿用 `.trae/rules/git-commit-message.md`（`type(scope): subject`，主题与正文英文）；每一步是一个**原子提交**——只含该步的改动，提交前跑完该步对应的验证项；只 `commit` 不 `push`。这样任何一步出问题都能精确定位、单独回退。

| 步 | 内容 | 提交前的验证 | 提交信息 |
|---|---|---|---|
| 1 | **修失败**：1.1 两个场景改 `f5`；1.2 `vim.py` 补 `\x1f` 分支 + `tests/` 补用例 | `run --scenario keymap_toggle` 3/3；`pytest -q` 全通过 | `fix(smoke): reach the command line with f5 and bind ctrl+/ in vim keymap` |
| 2 | **搭骨架**：`Scenario` 加 `tags`；`testsuite.py` 拆成 `scenarios/ + report.py + baselines.py + cli.py`，原 5 个场景搬迁 | `python -m tools.smoke_test run` 输出与拆分前一致；`--help` 不变 | `refactor(smoke): split harness into scenarios/report/baselines/cli and tag scenarios` |
| 3 | **报告美化**：Rich 头部/分组表/失败详情/汇总，含 `compare` 着色 | 全量 `run` 结果不变；80 列窄终端不炸版 | `feat(smoke): render results with rich (grouped tables, failure diffs, summary)` |
| 4 | **钩子**：全局不变量体检 + 命令/动作覆盖率计数 | 既有 5 场景不变量全绿；故意破坏一处能判 FAIL | `feat(smoke): add per-scenario invariant checks and command/action coverage` |
| 5 | **R 组回归场景**（9 个，优先于 A–H） | `run --tag regression` 全 PASS | `test(smoke): add regression scenarios pinned to past fixes` |
| 6 | **A–H 的 P0 场景**（约 23 个） | `run --tag edit --tag files --tag explorer` 等分组全 PASS | `test(smoke): add P0 functional scenarios (edit, files, panes, explorer)` |
| 7 | **A–H 的 P1 场景**（约 17 个） | 对应 `--tag` 全 PASS；`--repeat 3` 无抖动 | `test(smoke): add P1 navigation, selection, option and modal scenarios` |
| 8 | **P2 集成与压力**（6 个） | `--skip-slow` 可跳过；全量 `--repeat 3` 一致 | `test(smoke): add P2 integration and stress scenarios` |
| 9 | **收尾**：`snapshot` 生成基线 + `compare` 复核，更新 docstring 与手册 | `compare` 全 MATCH（exit 0） | `chore(smoke): regenerate baselines and refresh harness docs` |

补充说明：

- 第 1 步同时改动产品代码（`keymaps/vim.py`）与测试，仍在**一个提交**内，正文里分两段说明「产品行为变更」与「测试入口修正」。
- 第 5–8 步若某批次太大（例如 P0 一次 23 个），按标签再拆成多个提交（如 `test(smoke): add file and buffer scenarios` / `… explorer scenarios`），保持单提交可审阅。
- 每步提交后若发现该步引入回退，用 `git revert <该步 commit>` 精确撤销，而不是在这之上叠加修复提交。

## 验证清单

- [ ] `python -m tools.smoke_test run` → `Total: N ok, 0 fail`，exit 0
- [ ] `python -m tools.smoke_test run --scenario keymap_toggle` → 3/3
- [ ] `run --tag explorer` / `--tag files` 等分组过滤可用，输出含分组小计
- [ ] P2 集成场景在 `--skip-slow` 下被跳过，全量跑时也不 flake（`--repeat 3` 结果一致）
- [ ] 不变量钩子对既有 5 个场景全部通过（说明钩子本身无误报）
- [ ] 故意破坏一处状态（如场景内不还原主题）→ 不变量钩子能把它判成 FAIL（证明钩子有效，不是摆设）
- [ ] `--coverage` 输出命令覆盖 ≥ 60%、动作覆盖 ≥ 50%，未覆盖清单可导出
- [ ] `pytest -q` 全通过（含新增的 vim `ctrl+/` 用例）
- [ ] pyright strict 零诊断（`tools` 在 `pyproject.toml:46` 的 `include` 内）
- [ ] `snapshot` → 写入基线；再 `compare` → 全 `MATCH`，exit 0
- [ ] 全套耗时 < 60s（单场景 < 3s）
- [ ] 在 PowerShell 与窄终端（80 列）各看一次彩色输出，确认不断行、不溢出

## 风险分析

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| vim 新增 `\x1f` 分支与 `pending`/`count` 状态残留冲突 | 低 | 中 | 分支置于 `handle_key` 最前并显式清空 `pending`、`count_str` |
| 新增绑定进入 F1 帮助表，导致帮助面板 SVG 基线漂移 | 中 | 低 | 改动后重跑 `snapshot` 刷新基线 |
| 新场景时序 flake（截图/worker 未完成） | 中 | 中 | 统一 `pilot.pause()` 推进、断言只读 app 状态；必要时用 `wait_until` 轮询（可复用 `tests/test_app_textual.py:32` 的 helper） |
| 场景数量增加后总耗时变长（42 个 × 平均 1s） | 中 | 中 | 报告加 per-scenario 耗时 + `--tag` / `--scenario` / `--skip-slow` 过滤 + 进度条；必要时分文件并行跑（每个子进程独立 `run_test`，需先验证 Textual pilot 可并发） |
| 新场景互相污染全局单例（主题/键位/选项） | 中 | 高 | 场景结束显式复位；`run` 结束统一 `theme.set_theme("mocha")` 兜底；基线中记录主题相关断言 |
| 断言写错（臆造命令名/动作名/API）导致场景永远失败 | 中 | 低 | 命令名以 `commands.py:67-278`、动作名以 `actions.py:64-168` 为准；先跑单场景再入基线 |
| 不变量钩子误报（合法场景被判 FAIL） | 中 | 中 | 先在既有 5 个场景上验证钩子全绿；钩子检查项逐个灰度开关，可 `--no-invariant` 临时绕过 |
| fuzz 场景（S1）不稳定、偶发失败 | 中 | 高 | 固定 `--seed`，默认只跑 200 次轻量按键；失败时打印完整按键序列便于复现；单独打 `stress` 标签，默认全量跑但可过滤 |
| 覆盖率钩子（`run_command` / `execute_action` 包装）改变行为或漏计 | 低 | 中 | 只在冒烟 runner 内包装，不进产品代码；用计数而非替换，保持原语义 |
| R 组断言与产品行为不符（历史修复已演进） | 中 | 低 | 每条 R 场景在注释里标注对应 plan 文档与预期行为；落地时先跑一次确认当前行为再定断言 |
| Rich 在部分 Windows 控制台不上色/宽度异常 | 中 | 低 | `Console(soft_wrap=True)`、表格 `overflow="fold"`、提供 `--no-color` / `--width` |
| `snapshot` 基线入库导致频繁冲突 | 低 | 中 | 基线仅存 checks（不含 svg）或明确 `.gitignore`；`compare` 缺失基线时保持 exit 2 提示 |

---

## 后续建议

1. 把 `python -m tools.smoke_test compare` 接进 CI（退出码已可直接用），配合 `--json` 出机器可读结果。
2. 场景与 `tests/test_app_textual.py` 存在重叠，长期可考虑把稳定的冒烟场景反向复用为 pytest 用例，避免两套断言漂移。
3. 报告稳定后可加 `--since`/`--history`，把每次 `run` 的 JSON 追加成趋势文件，观察耗时与通过率变化。
