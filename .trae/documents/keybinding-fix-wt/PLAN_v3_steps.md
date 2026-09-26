# 方案 v3 — 分步执行计划（探针实证修订版）

> 状态：**Phase A 执行中 / Phase B 待启动**
> 取代：`PLAN_B_v2_key_reachability.md` §A1/A2 的根因假设（被 `_probe_vim.py` 探针证伪）；Phase B 保留并简化
> 探针结论（2026-09-26，当前分支代码）：
> - vim + 编辑器聚焦 + `ctrl+p` → 面板**打开**（分支先于 keymap，`editor.py:624`，接线 `handle_key=self.handle_key` editor.py:227）
> - vim 任意模式 + `\x1f` → **切换成功**（`vim.py:123` 是 handle_key 入口、模式无关检查）
> - `ctrl+e`(\x05) → vim 消化（scroll 语义），符合预期
> ** ⇒ 真机失败的最可能解释：被测的是安装版旧代码；次可能：WT win32 驱动对 `\x1f`/`\x10` 的 event.key 命名与 pilot 合成不同。**
> ** ⇒ PA1 的入口日志 + 真机 `YATE_TRACE=1` 复测一次性裁决。**

---

## Phase A — 派发层加固 + 证据链（4 步，每步验证后提交）

### PA1 — 入口级按键取证日志

- **改动**：`yate/editor.py` `Editor.handle_key` 开头（L566 `has_modal_screen` 之前）：
  ```python
  log.debug(
      "key event: key=%s character=%r focused=%s",
      event.key, event.character,
      type(self.app.focused).__name__ if self.app.focused else None,
  )
  ```
  tracing 默认关闭，零成本；`YATE_TRACE=1` 时真机一次运行即可拿到全部 `event.key` 实名。
- **验证**：pyright 0；pilot 全量不回归。
- **提交**：`feat(editor): log key events at entry for terminal diagnostics`

### PA2 — event.key 别名加固（防御驱动命名差异）

- **改动**：`yate/editor_view/keys.py` `_CTRL_PUNCT` 补 `"slash": 0x1F`（Textual 部分路径对 `/` 命名为 `ctrl+slash` 而非 `ctrl+slash`→已覆盖 `/`，此处防御 win32 驱动第三种形态）；核对 `\x10` 无别名风险（C0 0x10 全链路唯一命名 `ctrl+p`）。
- **测试**：`test_app_textual.py` `test_ctrl_and_alt` 追加 `textual_key_to_raw("ctrl+slash") == "\x1f"`。
- **验证**：定向 4 文件 pytest + pyright。
- **提交**：`fix(keymap): accept ctrl+slash alias for the 0x1f toggle byte`

### PA3 — vim 模式回归守卫（锁定探针证明的行为）

- **改动**：`tests/test_dispatch_guards.py` 重写：
  1. 保留 vsc 守卫；
  2. 新增 vim 用例：`handle_raw_key("\x1f")` 切 vim → 编辑器聚焦 → `press("ctrl+p")` 面板开；`press("ctrl+/")` 与 `handle_raw_key("\x1f")` 双路径切换回 vsc；explorer 聚焦后 `press("ctrl+1")` 回编辑器；
  3. 单元级：`VimKeymap.handle_key(ctx, "\x11")` 消费返回 True（不真退出，避免 pilot 关 app）；
  4. **反向演练**：注释 `editor.py` ctrl+p 分支 → vim 守卫必须变红 → 还原，演练结果写入提交信息。
- **验证**：该文件 pytest + 全量 + pyright。
- **提交**：`test(editor): pin vim-mode reachability for global chords`

### PA4 — 文档回填 + 真机复测指引

- **改动**：
  - 本文件勾选 PA 状态与实测数字；
  - `README.md` 状态表更新（v2 假设证伪 → v3）；
  - `SP5_gates_matrix.md` 复测指引加 **`YATE_TRACE=1` 环境变量步骤**：真机复测前 set，跑完把 trace 里 `key event:` 行贴回（裁决"驱动命名差异 vs 旧代码"）；
  - `wt_keybinding_fix_plan.md` 状态行指向本文件。
- **提交**：`docs(keybinding): record probe findings and v3 plan`

### Phase A 验收口径

- vsc/vim 双键位：ctrl+p / ctrl+/ 在 **pilot 层**全绿守卫锁定；
- 真机复测（PA4 指引）二选一结论：① 全通 → IKH1RA 除 ctrl+1 外关账（此前为旧代码误测）；② 仍失败 → trace 给出真实 event.key 名，按名补映射（PA2 模式扩展），仍不通才进 Phase B 驱动层。

### 真机复测指引（裁决性实验，按此执行）

```powershell
# 在被测终端（WT），worktree 目录下：
$env:YATE_TRACE='1'
d:\Programming\yate\.venv\Scripts\python.exe -m yate <测试目录>
# 复测 vim/vsc 双键位：ctrl+p、ctrl+/、ctrl+1；退出后查看 trace
# （tracing 落盘 ~/.yate/data/logs/yate-*.log，见 yate/logs.py）：
Get-Content ~\.yate\data\logs\yate-*.log | Select-String "key event:"
```

判读：
- 若 trace 显示 `key=ctrl+p` 且面板开 → 应用层全通，**此前真机测的是旧代码**（安装版），重装或用 worktree 入口即可；IKH1RA 剩 ctrl+1 → Phase B；
- 若 trace 显示 `key=ctrl+underscore` / 其它名字且跟随 `unmapped key event` → 把名字贴回，PA2 模式补映射；
- 若完全没有 `key event:` 行 → 事件没进 `Editor.handle_key`，驱动层问题实锤 → Phase B PB2.0 探测优先。

---

## Phase B — Windows 输入通道（物理层丢失/碰撞键的唯一解）

> **适用键清单（真机 trace 实证，2026-09-26）：**
> 1. **ctrl+1 等 ctrl+数字**：trace 无事件行 —— conhost 不编 C0、win32 驱动只读 `uChar` 不读 `dwControlKeyState`；
> 2. **ctrl+` vs ctrl+space**：两者在 WT 都坍缩为 NUL（`ctrl+@`）—— 现状取舍（`editor.py:587` 排除 +
>    `terminal.py:49` 全名集合）：编辑器聚焦 → 补全；终端聚焦 → 关终端。win32-input-mode 下
>    VK_OEM_3 ≠ VK_SPACE 可区分，两者才能各得其所；
> 3. **ctrl+e / ctrl+shift+e 区分**：legacy 终端同为 `\x05`。
> alt+digit 同类（Textual 映成 `¡` 等字符）。

> 简化洞察：Textual 的 `XTermParser` 可能**原生支持** win32-input-mode 帧（`\x1b[vk;mods;...u` 形态与 kitty CSI-u 同族）。
> 若支持，PB2 从"自建驱动"降级为"启动时启用协议 + 键名映射"，工作量减半。PB2.0 探测定方案。

### PB1 — `yate/keyproto/` L0 子包

- **模块**：`chords.py`（`KeyChord` frozen dataclass：`vk: int`、`ctrl/alt/shift: bool`、`char: str`）、
  `aliases.py`（chord → Textual 键名归一：`ctrl+1`、`ctrl+shift+e`…）、`legacy.py`（吸收 `editor_view/keys.py` 的 C0 表逻辑，keys.py 改为转发）。
- **约束**：L0，不 import yate 上层（R4）；PEP 695/3.12 风格；pyright strict 0。
- **验证**：新增 `tests/test_keyproto.py` 全覆盖 + 架构守护 13 用例 + pyright。
- **提交**：`feat(keyproto): add key chord model and legacy codec package`

### PB2 — 驱动层 chord 交付（先探测再实现）

- **PB2.0 探测**：脚本喂 `XTermParser` win32-input-mode 帧（`\x1b[49;5;1u` 形态，WT 启用后 conpty 输出）→ 若解析出含修饰的键名，走 **PB2-light**：`EditorSession`/启动序列在 WT 下发 `\x1b[>1u` 启用协议 + `event_to_raw`/chord 名映射补全；若不解析，走 **PB2-full**：`YateWindowsDriver(textual.drivers.win32.Win32Driver)` 子类，`KEY_EVENT_RECORD` 读 `dwControlKeyState`（`LEFT_CTRL_PRESSED|LEFT_ALT_PRESSED|SHIFT_PRESSED`），按 VK 合成 chord → `aliases.name(chord)`。
- **改动（PB2-full 时）**：新文件 `yate/keyproto/driver_windows.py`；注入 `YateApp` 类属性 `DRIVER_CLASS`（`app.py`，Textual `App.driver_class` 机制，条件：Windows 且未显式配置）。
- **验证**：单测（伪造 INPUT_RECORD 序列）+ pilot 全量回归 + 架构守护。
- **提交**：`feat(keyproto): deliver full chords on windows (vk + modifiers)`

### PB3 — 配置与降级

- **改动**：`yate/config.py` `_KNOWN_OPTIONS` 增 `key_protocol = auto|win32-input|legacy`（默认 auto：WT → win32-input，其余 legacy）；`auto` 探测失败自动降级 legacy 并 `log.info` 一次。
- **验证**：config 单测 + pilot 冒烟。
- **提交**：`feat(config): add key_protocol option with auto detection`

### PB4 — 文档 + `:keys` 排障面板

- **改动**：双语 manual「终端兼容性」节改写（ctrl+1 在 auto 模式下 WT 可用）；`yate/diagnostics.py` `:keys` 面板展示最近 20 条按键（复用 PA1 日志管道）；README 状态表。
- **提交**：`docs(manual): document key_protocol and ctrl+digit availability`

### PB5 — 真机矩阵复测 + 发布

- WT / conhost / VS Code 三终端跑 `verify_matrix.ps1`（升级版：含 ctrl+1 全部预期）；
- 全绿 → 关账 IKH1RA（引用 PA1 证据链）→ 发布 `v0.4.0`。

---

## 执行状态

| 步骤 | 状态 | commit | 实测 |
|---|---|---|---|
| v3 计划生成 | ✅ | （随 PA4 提交） | 探针证伪 v2 §A1/A2 根因假设 |
| PA1 入口日志 | ✅ | `5a73fc7` | 150 passed / pyright 0 |
| PA2 别名加固 | ✅ | `1d1f3d8` | 188 passed / pyright 0 |
| PA3 vim 守卫 | ✅ | `34ab059` | 2 passed；**反向演练成功**：注释 ctrl+p 分支 → vim 守卫红（assert 1==2）/ vsc 守卫仍绿（keymap `\x10` 绑定掩盖——SP2 盲区实锤并记录） |
| PA4 文档回填 | ✅ | `beea5e0` | — |
| **PA2b C0 兜底（真机 trace 裁决产物）** | ✅ | `1db6175` | trace 实锤：WT win32 驱动把 ctrl+] 命名为 `ctrl+right_square_bracket`（character 仍携 `\x1d`）、ctrl+6 → `ctrl+circumflex_accent`（`\x1e`）→ `event_to_raw` 增加兜底：ctrl-chord 表查找未命中且 `event.character` 为 C0（<0x20）→ 直接采用；一次覆盖全部未知标点命名，ctrl+p trace 显示 `key=ctrl+p`（规范名，无 unmapped）；191 passed / pyright 0 |
| **Phase A 真机验收** | ✅ | — | 2026-09-26 19:06 复测 trace：`ctrl+right_square_bracket`×4 / `ctrl+underscore`×8 / `ctrl+p` 全部**无 unmapped 行**（对照修复前 18:59 段）→ ctrl+]、ctrl+6、ctrl+/、ctrl+p 在 WT 真机全通；`escape` 关面板正常 |
| **PB1 keyproto L0 包** | ✅ | `5cd97d1` | chords/aliases/legacy 三模块；`editor_view/keys.py` 整体迁入 `keyproto/legacy.py`（3 处导入方同步改）；测试抓到真缺口：`ctrl+\``/`ctrl+grave`/`ctrl+grave_accent` 三种命名从未映射到 NUL → 补齐；4+21 passed / pyright 0 |
| **PB2.0 探测定案** | ✅ | （随 PB2 提交） | 本 Textual 版本**无 XTermParser 字节流入口**（Windows 走 record 直读）；且 `WindowsDriver.start_application_mode` 已启用 kitty `>1u` 而 WT/conpty 不响应（trace 实证 ctrl+1 无事件）→ 协议路线死路，**PB2-full record 读取定案** |
| **PB2 chord 驱动** | ✅ | `ce93090` | `keyproto/driver_windows.py`：`record_key_override`（纯函数，VK+dwControlKeyState→KeyChord，CapsLock/NumLock/修饰键/导航 VK 排除）+ `ChordEventMonitor`（stock 循环 + 唯一 chord 分支）+ `YateWindowsDriver`；`YateApp.get_driver_class` Windows 下选 chord 驱动（pilot/headless 显式请求 HeadlessDriver 不受影响）。**name-first 交付**：全部走既有派发表，派发层零改动；1235 passed / pyright 全仓 0 |
| **PB3 `key_protocol` 配置** | ✅ | `33f91e5` | `auto`（默认，Windows→chord 驱动）/`legacy`（stock 驱动逃生阀）/`win32-input`；yaterc 校验 + `YateApp.get_driver_class` 按配置选择（`self.config` 提前到 `super().__init__()` 之前赋值，因驱动解析发生在 App.__init__ 内）；94 passed / pyright 0 |
| **PB4 文档** | ✅ | （本提交） | 双语 manual「终端兼容性」改写（chord 驱动默认行为 + legacy 回退语义）+ README 双语 ctrl+1 行更新。**偏离计划：`:keys` 排障面板暂缓**——PA1 入口日志（`YATE_TRACE=1`）已覆盖取证需求，新 screen 属独立特性，登记为后续 nice-to-have |
| **PB5-r1 NUL 命名第二轮（真机 trace 裁决产物）** | ✅ | `54ab508` | 21:08 trace：`ctrl+shift+2 character='\x00'`×21 = chord 驱动对 Ctrl+@ 键（VK 0x32+ctrl+shift， grave 位于 Shift+2 位或手动模拟 ctrl+@）的命名，**已到达 yate** 但被当作补全/落空；`ctrl+underscore`×2 = ctrl+_ 的 C0 字节（试验键，与 ctrl+\` 无关）；**ctrl+1 零 trace 行 = 未到达 yate**（疑宿主工作台消费）。修复：`ctrl+2`/`ctrl+shift+2` 从补全分支移入 TOGGLE_KEYS（chord 驱动下 ctrl+space 单独命名，语义无歧义）；`ctrl+@` 保持 legacy 补全语义；chord 驱动新增 VK 级取证日志（`chord: vk=… state=… -> 名字`）；新增 pilot 测试锁定 ctrl+2/ctrl+shift+2 切换终端。217 passed / pyright 0 |
| **PB5 真机矩阵复测** | ⏳ | — | `verify_matrix.ps1` 三终端复测（本次预期 ctrl+1 在 WT/conhost/VS Code 全通、ctrl+` 开关终端、ctrl+space 补全）；**注意：VS Code 集成终端在工作台层消费 ctrl+1/ctrl+\`（yate 收不到，属宿主行为）——复测需在独立 Windows Terminal / conhost 进行，VS Code 下可用 ctrl+shift+2 代替**；全绿 → 关账 IKH1RA → 发布 |
