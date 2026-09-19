# yate 键盘输入重构 · 主计划（Windows Terminal 快捷键失效的根治）

> 命名前缀：`win_keybinding_*`
> 姊妹文档：**`win_keybinding_protocol_plan.md`**（方案 B 的逐步实施计划，含严格顺序）
> 状态：**决策已定 —— 采用方案 B（自建 Windows 输入通道 + 键盘协议协商）**
> 性质：这不是一次补丁，而是一次**输入层重构 + 新特性（可配置键盘协议层）**。

---

## 0. 决策摘要

| 项 | 结论 |
|---|---|
| 采纳方案 | **B**：yate 自己接管 Windows 键盘输入通道，主动协商键盘协议（win32-input-mode / kitty），自己解码协议帧 |
| 接管粒度（review 后修订） | **三档来源策略**：`OFF`→Textual 原生驱动；`STREAM`→接管字节流（协议帧）；`RECORD`→我们的驱动内部退回 Win32 记录读取（等价今天行为）。判定在 **driver 内部**完成且**运行时可回退**，而不是按"终端是不是 WT + 支不支持 kitty"在 App 构造前一次性选 driver class（理由见 §3.1） |
| 方案 A 的处置 | 不再是"可选修复"，降为 **B 的前置内嵌子模块**（Phase 1–2）。它是 B 能生效的必要条件，且**可独立发布**为一次 bugfix |
| 方案 C 的处置 | 明确**移出本计划**（WT `settings.json` unbound/sendInput）——它是"最后一公里"的用户配置助手，另立计划 |
| 新建代码 | 新子包 `yate/keyproto/`（8 个模块）+ `YateWindowsDriver` + 新 CLI/yaterc 选项 + `:keys` 排障面板 |
| 顺序铁律 | `P0 探针 → P1 KeyChord → P2 名字层(可发布) → P3 帧编解码 → P4 Driver 重构 → P5 协商 → P6 闭环(可发布) → P7 可观测性 → P8 跨平台对齐 → P9 发布`，**不许跳跃/并行换序**（理由见 §4 与姊妹文档 §12） |

---

## 1. 为什么只能选 B（三条硬约束）

1. **纯 yate 侧改名救不了所有键。** 终端只上报"有 legacy 编码"的按键，`Ctrl+1`/`Ctrl+Shift+字母` 在 Windows 上根本没有编码；Textual 的 Windows 驱动又只取 `uChar` 一个字符、丢弃 `wVirtualKeyCode`/`dwControlKeyState`（`textual/drivers/win32.py:271-278`），信息在通道中途就没了。再多的别名表也变不出 `Ctrl+1`。
2. **Textual 只"盲发"协议、不协商，且读法不对。** 它写 `\x1b[>25u`（Linux）/`\x1b[>1u`（Windows），退出写 `\x1b[<u`，但**从不查询** `CSI ? u`、也**不解析**状态回复（`_re_terminal_mode_response` 只认 DECRPM 的 2026/2048，`textual/_xterm_parser.py:23-25,311-331`）。更关键的是 Windows 侧输入走 `ReadConsoleInputW`（`win32.py:242-259`），**看不到 VT 字节流**，所以协商结果对它等于无效。
3. **win32-input-mode 是 Windows 上唯一能表达"任意物理键 + 修饰键"的通道。** `CSI Vk;Sc;Uc;Kd;Cs;Rc _` 自带虚拟键码与修饰键状态位，这正是 nvim 在 Windows 上可用的原因（`:help 'keyprotocol'` 的 `microsoft` 后端）。要用它，就必须**自己拥有输入通道**。

---

## 2. 现状与根因（证据保留）

### 2.1 输入链路

```
终端按键 ─①→ Textual 驱动 ─②→ Textual 键名 ─③→ yate 原始字节 ─④→ keymap 绑定
```

- ① Windows：`ReadConsoleInputW`，只取 `uChar`，`dwControlKeyState!=0 且 VK==0` 的记录被整条丢弃（`textual/drivers/win32.py:242-278`）；`stdin` 模式被覆盖为 `ENABLE_VIRTUAL_TERMINAL_INPUT`（`:176-180`），但该设置对记录式读取无效。
- ② 控制字符命名固化在 `textual/_ansi_sequences.py:23,39,58`（`0x00→ctrl+@`、`0x10→ctrl+p`、`0x1f→ctrl+underscore`）；kitty CSI-u 走 `_xterm_parser.py:355-409`，其中 `/` 会被 `solidus→slash` 改名（`textual/keys.py:205-212`）。
- ③ yate 只认少数拼写：`editor_view/keys.py:16` 的 `_CTRL_PUNCT = {"[","\\","]","/"}`；`keymaps/base.py:105-113` 把 `ctrl+数字` 编成 kitty 串 `\x1b[49;5u`，但 `textual_key_to_raw("ctrl+1")` 返回 `None`（死条目）。
- ④ `app.on_key` 里 `ctrl+shift+e`/`ctrl+1`/`ctrl+p` 是**字符串精确比较**（`yate/app.py:985-999`）；vim 模式下未映射键被 `_handle_normal` 吞掉（`keymaps/vim.py:415-416`），永不冒泡。

### 2.2 逐键定位

| 键 | 绑定位置 | 真实到达时的 Textual 名 | 结果 |
|---|---|---|---|
| `Ctrl+Q` / `Ctrl+W` | `vsc.py:87/86`（raw `\x11`/`\x17`） | `ctrl+q` / `ctrl+w` → 字母分支生成同一字节 | ✅ |
| `Ctrl+/` | `vsc.py:99`（raw `\x1f`） | `ctrl+underscore`（传统）或 `ctrl+slash`（kitty） | ❌ 必然失效（跨平台） |
| `Ctrl+1` | `vsc.py:102` + `app.py:990` | Windows 无编码 → 无事件，或 `U+0000` → `ctrl+@` → 被当 Ctrl+Space 触发补全（`editor.py:189`） | ❌ |
| `Ctrl+P` | 仅 `app.py:995` | 需恰为 `ctrl+p` 且冒泡到 app；vim 模式被吞 | ⚠️ vim 必失效 |

### 2.3 根因

- **R1** 键名拼写漂移（`ctrl+/`）→ 名字层不匹配即丢键。
- **R2** app 层字符串特例与 keymap 表双轨，无统一兜底。
- **R3** vim 吞键，与手册承诺（`manual.zh.md:428`）冲突。
- **R4** Windows 通道只保留 `uChar`，无 legacy 编码的键不可达（**只能靠方案 B 解决**）。
- **R5** WT 保留键（`ctrl+shift+p/w/a/k/1..9`，据 WT `defaults.json`）应用无法覆盖；但 `ctrl+p`/`ctrl+1`/`ctrl+/` **不在保留列表**，它们的问题不是 WT 抢键。

---

## 3. 目标架构（B 落地后）

```
终端 ──┬── legacy 字节 ──────────────┐
       └── 协议帧 (win32 `_` / kitty `u`) ─┐
                                          ▼
                        yate/keyproto/stream.py   ← 分帧（可注入 reader，便于测试）
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
      win32_input.py / kitty.py 解码                    XTermParser(Textual)
                    └──────────────► KeyChord ◄─────────────────┘
                                        │
                             Keymap.lookup(raw, canonical)
                                        │
                                     action
```

| 新模块 | 职责 |
|---|---|
| `yate/keyproto/model.py` | `KeyChord`（code/mods/event/source/text）+ canonical 名 |
| `yate/keyproto/aliases.py` | 拼写别名归一（吸收原 `_CTRL_PUNCT`，成为唯一权威表） |
| `yate/keyproto/legacy.py` | `KeyChord → 传统字节`（合并 `editor_view/keys.py`、`keymaps/base.py`、`editor_term/emulator.py` 三张表） |
| `yate/keyproto/win32_input.py` | `CSI Vk;Sc;Uc;Kd;Cs;Rc _` 编解码 + VK/Cs 表 |
| `yate/keyproto/kitty.py` | CSI-u 编解码 + flags 请求/关闭序列 +（P8）modifyOtherKeys |
| `yate/keyproto/negotiate.py` | 能力探测、顺序、超时、降级、运行时状态 |
| `yate/keyproto/stream.py` | 字节流分帧器（协议帧 vs 透传） |
| `yate/keyproto/driver_windows.py` | `YateWindowsDriver`：替换输入线程 + 尺寸轮询 + 三级恢复 |

### 3.1 输入来源策略（review 后修订）

"终端能力足够就用内置、不足才接管"这个直觉方向正确，但**判定条件与回退目标必须修改**：

| 档 | 触发条件 | 输入来源 | 说明 |
|---|---|---|---|
| `OFF` | `--key-protocol off` / `YATE_KEY_PROTOCOL=off` / stdin 不是控制台（`GetConsoleMode` 失败，如 `yate < file`、被管道包裹） | **Textual 原生 `WindowsDriver`** | 真正的"用内置"逃生门，零偏差 |
| `STREAM` | `auto` 默认 + 预期有协议收益：`WT_SESSION` 存在，或 `--key-protocol=win32/kitty` 显式指定 | **我们接管字节流**：`os.read` + `FrameSplitter` + 协议解码 | 唯一能拿到 `Ctrl+1`/`Ctrl+/`/`Ctrl+Shift+X` 的路径 |
| `RECORD` | `auto` 下无协议可期（老 conhost、终端未知、`TERM` 不支持 VT），或 STREAM 运行期连续解析失败 | 我们驱动内的 **`ReadConsoleInputW` 记录源**（**直接复用上游 `win32.EventMonitor`，零复刻**） | 避免"接管了却零收益"的额外风险；行为与今天逐事件一致 |
| `STREAM` 内部再分优先级 | 见方案 B 计划 §3 D3 | **kitty 优先于 win32-input-mode**（风险不对称，见 §6.2 R-H1） | 让"能自愈的协议"承担默认路径 |

**为什么不能"WT + 支持 kitty → 用 Textual 内置"**：

1. Textual 的 Windows 驱动读的是 Win32 **记录**（`textual/drivers/win32.py:242-259`），只取 `uChar`（`:271-278`）。协议协商改变的是"终端往 pty 写什么"，改不了"驱动读什么"。
2. `Ctrl+1` 没有 legacy 编码：conhost 即便按 kitty 收到 `CSI 49;5u`，能交给读端的也只有 `uChar`（`0` 或 `'1'`），**修饰键信息不可逆丢失** → Textual 要么无事件，要么把它变成 `ctrl+@`（触发补全）或字面 `1`（比"无反应"更糟）。
3. "帧能否以字节到达读端"**必须先拥有字节流才能判断**（鸡生蛋）。所以判定要放在拥有通道之后，用**自纠正分帧器**（有帧走帧、无帧透传）替代预判；把判定放在 `App.__init__` 之前等于一次性、不可纠正。
4. 反过来，**非 Windows 已经就是你设想的形态**：Textual 的 `LinuxDriver` 本来就读字节流并解析 CSI-u（`linux_driver.py:285-292` + `_xterm_parser.py:355-409`），所以 P8 只做名字归一化，**不接管驱动**。
5. 你设想的"能力不足才接管"在这一版里被完整保留，只是换了判据：不是"终端支持 kitty 吗"，而是"**当前输入路径能不能把 VK/修饰键交给我们**"，并且**接管的最小可用形态是 RECORD 源（等价旧行为），有收益才升到 STREAM**。

**改造的既有模块**：`yate/app.py`（`driver_class` 注入、`handle_raw_key(raw, name)`）、`yate/keymaps/base.py`（名字索引）、`yate/keymaps/vim.py`（冒泡）、`yate/editor_view/{keys,editor}.py`、`yate/editor_term/emulator.py`（`key_to_terminal` 转发到 `legacy.py`）、`yate/interfaces.py`、`yate/config.py`、`yate/cli.py`、`yate/diagnostics.py`、`yate/crash.py`（恢复钩子）。

---

## 4. 阶段总览（严格顺序，不可换序）

| Phase | 内容 | 依赖 | DoD（完成判据） | 可独立发布 |
|---|---|---|---|---|
| **P0** | 探针与事实固化（`tools/probe_keys.py`、真机抓帧、DECRQM/`CSI ? u` 行为验证） | — | 抓包报告 + `tests/fixtures/win32_input_frames.py` | 否（工具） |
| **P1** | `KeyChord` 模型 + 别名表 + `legacy_bytes`（纯函数） | P0 | 表驱动单测全绿（含所有真实拼写） | 否 |
| **P2** | 名字层接入派发（= 原方案 A）：keymap 名索引、app 迁移、vim 冒泡、集成终端对齐 | P1 | `Ctrl+/` 全平台恢复、vim 下 `Ctrl+P` 恢复、pyright/pytest 全绿 | ✅ **v0.3.0-alpha（bugfix 发布）** |
| **P3** | win32/kitty 帧编解码（纯函数，不接线） | P0 | 用 P0 fixture 的表驱动单测全绿 | 否 |
| **P4a** | `YateWindowsDriver` 骨架 + **RECORD 记录源**（复用上游 `win32.EventMonitor`，先建立"等价今天"的回归基线） | P2 | 与原生驱动**逐事件等价** | 否 |
| **P4b** | **STREAM 字节流源** + 尺寸轮询 + 三级恢复 | P4a,P3 | 无协议时的透传路径与 RECORD 等价 | 否 |
| **P5** | 来源策略（`OFF/STREAM/RECORD`）判定 + 协商状态机 + 运行期回退 + `--key-protocol` | P4b | 判定表/状态转移/回退三组单测；WT 真机确认 source | 否 |
| **P6** | 事件合成接入 keymap（闭环） | P5 | WT 下 `Ctrl+1`/`Ctrl+/`/`Ctrl+Shift+字母` 真机可用；无重复触发 | ✅ **v0.3.0-beta（Windows 真修复）** |
| **P7** | 可观测性与 feature 化（`:keys`、`[keyboard]` diag、`--reset-terminal`、扩展 API 文档） | P6 | 排障闭环；文档更新 | ✅ |
| **P8** | 跨平台对齐（Linux 走同一 KeyChord；可选 xterm modifyOtherKeys 后端） | P6 | Linux 回归零变化 + 名字归一全覆盖 | ✅ |
| **P9** | 发布整理（手册、CHANGELOG、迁移与回退指南） | P8 | 发版检查单通过 | ✅ **v0.3.0** |

**依赖铁律**：`P1→P2` 必须先于 `P3→P4`；`P3` 必须先于 `P4`；**禁止在 P3 完成前发送 `\x1b[?9001h`**（会收到无法解析的帧，把用户按键变成垃圾）；详见姊妹文档 §12「顺序禁忌清单」。

---

## 5. 与既有机制的交互（必须同步改）

| 交互点 | 位置 | 处理 |
|---|---|---|
| 集成终端面板键盘 | `editor_view/terminal.py:189-208` | `key_to_terminal` 改为 `keyproto.legacy` 的转发（面板聚焦时协议帧→chord→legacy 字节，语义不变） |
| `ctrl+@` / `ctrl+grave` 双语义 | `terminal.py:33-45`、`editor.py:184-193`、`app.py:957-964` | **保持不变**（编辑器=补全、面板=切终端），P2 加回归测试锁住 |
| vim `ctrl+w` 和弦 | `app.py:918-951`、`editor.py:224-230` | 保持在 keymap 派发之前处理，不受协议层影响 |
| `handle_raw_key` 签名 | `interfaces.py:156` | 扩为 `handle_raw_key(raw, name: Optional[str] = None)` |
| pilot/headless 测试 | `textual/app.py:3334-3350` | headless 驱动不受影响，现有测试语义不变 |
| Linux 路径 | `textual/drivers/linux_driver.py` | **不改驱动**，只在 P8 复用 KeyChord 归一化 |

---

## 6. 风险与回退

### 6.1 降低风险的五条原则（比"再加一层保险"更有效）

1. **消除优于自愈**：能让风险**不发生**的设计，优先于"发生了再恢复"。关键事实：kitty 协议的 push/pop 被终端**强制按主/备屏分栈隔离**（规范要求，Textual 也遵守"进备屏后 push、离开前 pop"，`windows_driver.py:95→99`、`:129→132`），崩溃漏 pop 也**不会污染父 shell**；而 win32-input-mode（`CSI ? 9001 h`）是**会话级私有模式、没有栈**，父 shell 与 yate 共享同一 pty 会话，漏 `l` 就会让 shell 收到 `CSI ... _` 垃圾。
2. **隔离生命周期与范围**：危险状态只允许存在于"最短窗口 + 最小环境"。例：`RECORD`/`OFF` 档一个协议序列都不发；只有协商确认后才切事件来源。
3. **恢复手段必须正交**：多层保险不能依赖同一个假设——`atexit` 依赖正常 shutdown、异常钩子依赖 Python 异常、`SetConsoleCtrlHandler` 依赖 console 事件、残留标记依赖磁盘、`--reset-terminal` 依赖用户动作。**覆盖不同失败面才有意义**。
4. **复用优于复制**：能引用上游公共 API 就不复刻代码，**复刻面 = 漂移面**。
5. **可观测即可管理**：把"降级/去重/解析失败"变成计数器与状态（`:keys`、`--diag`），把"未知的静默丢键"变成"已知的可上报现象"。

### 6.2 风险登记册（review 后强化）

| ID | 风险 | 概率 | 影响 | 缓解（强化项加粗） |
|---|---|---|---|---|
| **R-H1** | 终端协议状态未恢复（父 shell 收到 `CSI ... _` 垃圾） | 中 | **高** | ①**消除**：默认**优先 kitty**（栈式 + 备屏隔离），win32-input-mode 降为**受控启用**（方案 B 计划 §3 D3）；②隔离：`RECORD`/`OFF` 档不发协议序列；③正交自愈：正常 `stop` → `finally` → `atexit`/`crash._excepthook` 前置恢复（`crash.py:85-102`）→ **`SetConsoleCtrlHandler`（Ctrl+C / Ctrl+Break / 关窗口）**；④**跨进程自愈：启动写"协议残留标记"，正常退出删除；下次启动发现标记 → 先发 `\x1b[?9001l\x1b[<u` 再继续**（覆盖 SIGKILL/断电）；⑤`yate --reset-terminal`；⑥关闭序列**直写 fd（`os.write(1, …)`）**，绕过可能已停的 WriterThread；⑦恢复后**读回校验** `GetConsoleMode`，失败告警 |
| R-H2 | 自建驱动破坏鼠标/尺寸/焦点 | 中 | 高 | **`RECORD` 档直接复用上游 `win32.EventMonitor`（零复刻）**；`STREAM` 档按**能力对等清单**逐项注入测试（Key/Mouse*/Resize/Focus/Paste）；尺寸**优先复用 Textual 的 in-band resize**（`CSI ? 2048` + `\x1b[48;…t`），轮询仅兜底；无收益不接管 |
| R-H3 | 协议帧与 legacy 字节双份 → 重复触发 | 中 | 中 | 批次判定 + **5ms 时间窗去重** + **`dup suppressed` 计数器**（>0 即视为终端异常，写入 `:keys`/日志可上报） |
| R-H4 | Textual 上游漂移 | 中 | 高 | ①**最大化复用上游公共 API**（只在必须处覆盖）；②`_UPSTREAM_ASSUMPTIONS` 结构性断言 → 失败**自动 OFF（不接管）**而非崩溃；③**契约测试**（固定 INPUT_RECORD ↔ 事件序列快照，上游升级即报警）；④**CI 增加 "latest textual" 作业**；⑤`pyproject.toml` 收紧 `textual>=8.0,<9` |
| R-H5 | 崩溃 / native crash 无法清理 | 低 | 中 | R-H1 的 ④⑤⑥（"下次启动自愈"专治 SIGKILL）+ `signal.SIGBREAK` |
| R-H6 | 按键路径性能 | 低 | 低 | 先 `str.find("\x1b")` 快进，仅含 ESC 才进状态机；每键预算 < 50µs；`:keys` 暴露最近 N 次解析耗时 |
| **R-H7**（新增） | 集成终端面板语义漂移（面板里的 nvim 自己向我们的 PTY 发 `\x1b[?9001h`） | 中 | 中 | 明确面板路径只做"帧 → chord → legacy 字节"；模拟器对 `?9001h` 只记录不实现，写入已知限制；补面板链路一致性测试 |
| **R-H8**（新增） | 启动期两套输入源交接丢键 | 低 | 中 | **先起新源线程、再停旧线程**；交接窗口内的已消费批次直接转交，不丢字节 |
| **R-H9**（新增） | 环境误判（SSH→Windows、WSL、VS Code 集成终端） | 中 | 低 | `SourcePolicy` 默认保守（无 `WT_SESSION` → `RECORD`/`OFF`）；这些环境本来也拿不到 win32-input-mode，不会更差 |
| **R-H10**（新增） | 用户强制 `--key-protocol=win32` 但终端不支持 | 低 | 低 | 终端不支持时仍发 legacy 字节 → 按键正常（只是拿不到额外键）；只有"能收到帧但解析失败"才降级（连续失败计数；强制模式只告警） |

**回退开关（三层）**：环境变量 `YATE_KEY_PROTOCOL=off` → CLI `--key-protocol off` → yaterc `key_protocol = "off"`；终极回退 `TEXTUAL_DRIVER=textual.drivers.windows_driver:WindowsDriver`（用回原生驱动）。

---

## 7. 整体验收

1. **P2 后**：任意终端下 `Ctrl+/` 生效；vim 模式下 `Ctrl+P`/`Ctrl+1` 生效（与手册一致）。
2. **P6 后**：Windows Terminal 下 `Ctrl+1`、`Ctrl+/`、`Ctrl+Shift+字母`、`Ctrl+Enter` 等**凡终端愿意送达 pty 的组合**全部可达；不再出现"被误报成 `ctrl+@` 触发补全"。
3. **恢复专项**：正常退出 / 未捕获异常 / 强杀 / 本地 native crash 四类场景后，终端均无协议残留。
4. **性能**：按键端到端延迟无可见退化；空闲无轮询热点（尺寸轮询与输入等待合并）。
5. **门禁**：`.venv\Scripts\python.exe -m pyright` 0 errors；`$env:PYTHONDONTWRITEBYTECODE='1'; .venv\Scripts\python.exe -m pytest tests -q` 全绿。
6. **不承诺**：WT 自身保留键（`ctrl+shift+p/w/a/k/1..9`）——那是方案 C 的领域（WT `settings.json`），本计划不处理。

---

## 8. 明确不在本计划范围

- 方案 C：WT `settings.json` 的 unbound / sendInput 助手（未来 `terminal_keys_install_plan.md`）。
- yaterc 的 `[keys]` 自定义绑定体系（可作为 P7 的可选子项，单独立项）。
- 集成终端模拟器（`yate/editor_term`）对 win32-input-mode 的支持（面板里跑 nvim 自己开协议的情形）。
- macOS `modifyOtherKeys` 后端（P8 的 optional，不阻塞发布）。

---

## 9. 关键证据速查

| 事实 | 位置 |
|---|---|
| Textual 只 push kitty、不查询不解析（Linux `\x1b[>25u`） | `textual/drivers/linux_driver.py:29-34,285-292,388-390` |
| 非 Windows 驱动**本来就**读字节流并解析 CSI-u（所以那边不需要接管） | `linux_driver.py:285-292` + `_xterm_parser.py:355-429` |
| Windows 只 push 且无 `DISABLE_KITTY_KEY` 判断 | `textual/drivers/windows_driver.py:99,129` |
| 只有 2026/2048 是真协商（DECRQM `$p` + DECRPM `$y`） | `linux_driver.py:315-324`、`_xterm_parser.py:23-25,311-331` |
| Windows 输入只取 `uChar`、丢弃 VK/修饰键 | `textual/drivers/win32.py:242-278` |
| 控制字符命名表 | `textual/_ansi_sequences.py:23,39,58` |
| `solidus→slash` 改名 | `textual/keys.py:205-212` |
| App 先查 bindings 再调 `on_key`；Textual 自带 ctrl+p 绑定 | `textual/app.py:4341-4343`、`:441,874-889` |
| yate 只认 `ctrl+/`、`ctrl+数字` 是死条目 | `editor_view/keys.py:16,72-79`、`keymaps/base.py:105-113` |
| app 层字符串特例 | `yate/app.py:985-999` |
| vim 吞键 | `yate/keymaps/vim.py:170,415-416` |
| 集成终端键表缺 `/` | `yate/editor_term/emulator.py:139-148` |
| WT 默认绑定清单（`ctrl+p`/`ctrl+1`/`ctrl+/` 无绑定） | WT `defaults.json` |
| WT 1.25 preview 起支持 kitty 键盘协议 | devblogs：Windows Terminal Preview 1.25 Release（2026-03-05） |
| nvim 经 `'keyprotocol'` 协商 kitty/xterm/microsoft(win32-input-mode) | Neovim `:help tui-input`、`:help 'keyprotocol'` |

> 逐步实施细节、接口签名、表内容、序列顺序、测试与工作量估算见 **`win_keybinding_protocol_plan.md`**。
