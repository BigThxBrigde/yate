# review-vscode-keymap-plan

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
① review vscode keymap 是否全部正常；② 检测与 vim keymap 不冲突、不互相覆盖；有问题则 fix。

分支/worktree：`enh/review-vscode-keymap` @ `../../yate-review-vscode-keymap`（基于 master 24fed04）。

## 一、目标与非目标

**目标**

1. 对 `yate/keymaps/vsc.py` 全表取证：每个绑定的 action 是否已注册、raw key 是否可达。
2. 排查 vsc 与 vim 之间的冲突/覆盖面，结论落盘（只读取证）。
3. 修复查实的缺陷 + 加防回归测试。

**非目标**

- **不改任何 vim keymap 相关模块**（`keymaps/vim.py`、`window_flows.py` 等一律不动；
  防回归测试也只针对 VscKeymap，不引入对 VimKeymap 的断言）——用户硬约束；
- 不改 parse_key/驱动层（不给 ctrl+shift+字母引入区分编码）；
- 不动双语手册（无用户可见行为变化）。

## 二、调研事实（文件:行号）

### 派发链

```
Textual Key
  → App.on_event：priority 绑定先查（ctrl+q → App.action_quit → registry，app.py:321）
  → Editor.handle_key（editor.py:521）按名拦截：
      ctrl+space/ctrl+@ 补全 (556) → TOGGLE_KEYS 终端 (560) → ctrl+w vim 窗格 chord
      （仅 vim NORMAL，window_flows.py:172）→ alt+shift+p (591) → alt+shift+s (602)
      → ctrl+shift+e (607) → ctrl+1 (610) → ctrl+p (613)
  → event_to_raw（keyproto/legacy.py:52）→ handle_raw_key → keymaps.active.handle_key（editor.py:630）
```

- Textual 内建 ctrl+p 命令面板已被 `ENABLE_COMMAND_PALETTE = False`（app.py:82-83）禁用，无抢占。
- 单一活动 keymap（`KeymapSet.active`），vim/vsc 不会同时派发。

### ① vsc 全表核对结论

- 62 个绑定的 action 名逐一对照 `actions.py::populate` 注册表：**全部已注册，0 未知 action**。
- raw key 可达性：除 `<ctrl-1>`（\x1b[49;5u，legacy 终端不可产，由 editor.py:610 按名拦截，keymap 行仅作 help 展示）外全部可由 `event_to_raw` 产出。
- **缺陷 D1（唯一实质缺陷）**：vsc.py:104-105 `<ctrl-e>` 与 `<ctrl-shift-e>` 经 `parse_key` 解析后同为
  `\x05`（ctrl+shift+字母在 legacy 终端就是同一字节，parse_key 无区分）。`Keymap.__init__` 的
  `_index`（base.py:224，dict 推导后者胜）**静默覆盖**前者；help overlay 遍历 `bindings` 列表
  （overlays.py:85 `HelpScreen`）显示两行同标签 `<ctrl-e>`、描述不同——正是 issue 要求消灭的
  "同键互相覆盖"形态。功能无损（两行同为 focus_explorer），但帮助误导。
- 无害别名（保留）：`\x1b[H`/`\x1b[1~` 同为 <home>、`\x1b[F`/`\x1b[4~` 同为 <end>，是真实终端编码差异，help 各占一行。

### ② vim/vsc 冲突排查结论（全部无冲突）

| 面 | 结论 | 证据 |
|---|---|---|
| ctrl+w | 仅 vim NORMAL 武装窗格 chord；vsc ctrl+w → close_tab；vim INSERT → delete_word_back | window_flows.py:172-174 |
| ctrl+/（\x1f） | 两 keymap 均可切换：vsc 走 `_index`；vim 在 handle_key 顶部处理（全模式） | vsc.py:103；vim.py:172-175 |
| shell 按名拦截的 5 个 chord | ctrl+p/ctrl+1/ctrl+shift+e/alt+shift+p/alt+shift+s 在 vim 无绑定，无覆盖 | editor.py:591-614 |
| 扩展 bind_key | 目标显式 keymap（vsc/vim/both），未知名告警，不会隐式覆盖另一份 | services/extensions.py:294-311 |
| vim 伪 action 行（"move left" 等） | 仅 help 标签，不会被 dispatch；可派发行（F 键、\x1f）action 名全部已注册 | vim.py:176-185 |

vim 侧 `<alt-shift-s>` 行（vim.py:158-161）为 help-only 行，实际派发由 editor.py:602 按名拦截、两种 keymap 下都生效——非缺陷，保留。

## 三、备选方案与否决理由

- **A. 保留两行、改 help overlay 去重** — 否决：治标；`_index` 静默覆盖语义仍在，且 `add_binding`
  （base.py:231）依赖"同 key 替换"语义，动展示层引入特例。
- **B. parse_key/驱动层区分 ctrl+shift+字母（kitty CSI-u）** — 否决：协议层大改，legacy 终端物理上
  同字节，超出本 issue 范围。
- **C. 删除 vim 的 alt-shift-s 行** — 否决：该行是 vim F1 帮助里该快捷键的唯一展示来源，shell 拦截照常工作。

## 四、实施步骤

### 步骤 1：vsc 去重（修复 D1）

- 改动文件：`yate/keymaps/vsc.py`
- 删除 `<ctrl-shift-e>` 重复行（105），`<ctrl-e>` 描述并入 vscode 别名：
  `"Focus file explorer (ctrl+e / vscode ctrl+shift+e)"`。
  两 chord 行为不变：legacy 驱动同字节走 raw 路径；chord 驱动由 shell 按名拦截（editor.py:607）。
- 输出：vsc 绑定 62 → 61 行，无 raw key 重复。
- 验收：步骤 2 的新测试 + `python -m pytest tests/test_vsc_keymap.py -q` 全绿。

### 步骤 2：防回归测试（新增 `tests/test_vsc_keymap.py`）

用例（纯 vsc 侧，不 import / 不断言 VimKeymap，遵守用户硬约束）：

1. `test_vsc_has_no_duplicate_raw_keys`：VscKeymap 的 `bindings` key 无重复
   （拦截 `_index` 静默覆盖类缺陷的回归）。
2. `test_vsc_bindings_use_registered_actions`：`populate(ActionRegistry(), cast("Editor", None))`
   （populate 注册期不触碰 editor 属性，lambda 惰性引用）后，vsc 每个 str action ∈ `registry.names()`。
3. `test_ctrl_w_in_vsc_closes_tab`：`vsc.lookup("\x17").action == "close_tab"`——
   钉死 vsc 侧 ctrl+w 语义（键表层契约；vim 侧 chord 条件在 window_flows，不在本任务改动面）。

- 改动文件：`tests/test_vsc_keymap.py`（新增，仅此一个测试文件）
- 验收：`python -m pytest tests/test_vsc_keymap.py tests/test_keymap_set.py -q`

### 步骤 3：全量门禁 + 收尾

- `python -m pytest tests/ -q` 全绿；`python -m pyright yate/ tests/ tools/` 零诊断
  （环境注意：主仓 `.venv` 损坏——缺 pyvenv.cfg 与 Lib；执行时先探测系统 python 3.13 的
  pytest/pyright 可用性，必要时如实记录环境偏离，不在本任务内修 venv）。
- 架构测试 `tests/test_architecture.py` 随全量跑。
- 本文档回填真实结果；按 `git-commit-message.md` 提交（`fix(keymaps): ...`，只提交不推送）。

## 五、风险与回滚

- 风险极低：唯一产品改动是删除一行冗余绑定 + 描述文本，无行为变化。
- 回滚：单 commit revert 即可。

## 六、执行记录（2026-09-29 回填）

- [x] 步骤 1：`yate/keymaps/vsc.py` 删除 `<ctrl-shift-e>` 冗余行（62 → 61 个绑定），
  `<ctrl-e>` 描述并入 vscode 别名并附原因注释；行为不变（legacy 驱动同字节、chord 驱动由外壳按名拦截）。
- [x] 步骤 2：新增 `tests/test_vsc_keymap.py`（3 用例：无重复 raw key / action 全注册 /
  ctrl+w=close_tab）。定向键表测试全绿：`pytest tests/test_vsc_keymap.py tests/test_keymap_set.py
  tests/test_vim_keymap.py -q` → 127 passed。
- [x] 步骤 3 全量门禁（最终以项目 venv 解释器复跑，junitxml 实测）：
  - `pytest tests/`（`.venv`，Python 3.13.2 + textual 8.2.8）：
    **1458 项 = 1451 passed + 7 skipped + 0 failed + 0 errors**，退出码 0，无需 deselect。
  - `pyright yate/ tests/ tools/`（strict）：**0 errors / 0 warnings / 0 informations**。
  - 架构测试 `tests/test_architecture.py` 随全量通过。
- 偏离记录：
  - **更正（2026-09-29 晚）**：本会话早前"项目 `.venv` 损坏（缺 pyvenv.cfg / Lib）"的诊断有误
    （当轮工具输出失真所致）；实测 venv 健康（Python 3.13.2、textual 8.2.8、pytest 9.1.1、
    yate editable 安装齐全）。中间曾用系统 Python 3.13 跑过门禁（数字：deselect 1 例后
    1457 项 0 失败），最终以上方 venv 复跑数字为准。
  - `tests/test_app_textual.py::test_syntax_highlight_and_theme_switch` 为**负载敏感 flaky 用例**
    （Textual pilot 时序：高负载下 `pilot.pause()` 后高亮段未就绪）：全量/混跑偶发失败、
    独立复跑稳定通过（多轮实测含 master 与本分支、venv 与系统解释器各组合），与本次改动无关；
    修复该 flake 属独立任务，未纳入本计划。
  - worktree 不共享未跟踪目录（无 `.venv`，pyright 报 "venv .venv subdirectory not found"）：
    以**目录联接** `.venv → .venv` 补齐（`.gitignore:101` 已覆盖，无 git 污染；
    实测 `import yate` 仍解析到 worktree 源码），pyright 的 `venvPath/venv` 配置由此直接生效。
