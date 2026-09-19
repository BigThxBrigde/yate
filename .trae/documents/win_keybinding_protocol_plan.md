# 方案 B 详细实施计划：Windows 键盘输入通道重构 + 键盘协议层

> 命名前缀：`win_keybinding_*`（主计划：`win_keybinding_plan.md`；本文件：`win_keybinding_protocol_plan.md`）
> 本计划是**重构 + 新特性**：新增 `yate/keyproto/` 子包、自建 Windows 输入源、可配置键盘协议层与排障面板。
> **执行顺序不可调整**：见 §4 逐步 checklist 与 §12 顺序禁忌清单。

---

## 0. 目标 / 非目标

**目标**
1. Windows 上让"终端愿意送达 pty 的任意组合键"完整到达 yate：`Ctrl+1..9`、`Ctrl+/`、`Ctrl+;`、`Ctrl+Shift+字母`、`Ctrl+Enter`、`Ctrl+Backspace` 等。
2. 把"键名 → 字节"的三张平行表合并为**唯一权威模型**，从结构上消灭 R1/R2 这类"拼写漂移即丢键"的 bug。
3. 把输入层做成**可配置特性**：`--key-protocol auto|win32|kitty|off`、`:keys` 排障面板、`--diag [keyboard]`、`--reset-terminal` 救援。
4. 终端状态**必须**可恢复（含异常路径），不污染用户环境。
5. **接管面最小化**：先在驱动内建立"等价今天"的 `RECORD` 记录源作为基线，只有在**能确认协议收益**（字节流里真的出现协议帧）时才升到 `STREAM`；无收益环境不接管字节流。

**非目标（本计划不承诺）**
- WT 自身保留键（`ctrl+shift+p/w/a/k/1..9`）——应用层无法覆盖。
- 集成终端面板内子进程（nvim 等）自行协商协议的支持。
- macOS `modifyOtherKeys` 后端（P8 optional）。
- yaterc `[keys]` 自定义绑定体系（另立项）。

---

## 1. 总体设计与数据流

```
stdin(VT 字节流, Windows: ENABLE_VIRTUAL_TERMINAL_INPUT)
      │  os.read + WaitForMultipleObjects
      ▼
FrameSplitter.feed(data) ──► (frames: list[KeyChord], passthrough: str)
      │                              │
      │                              └─► XTermParser.feed → Key/Mouse/Resize/Paste/Focus
      ▼
KeyChord(name="ctrl+1", source="win32")
      │  events.Key(canonical_name, text)
      ▼
App.process_message → 焦点 widget → keymap(lookup(raw, name)) → action
```

**模块与公共 API**（P1/P3 完成后的期望形态）

| 模块 | 关键接口 |
|---|---|
| `model.py` | `KeyChord(code, mods, event="press", source="legacy", text="")`、`.name`（canonical）、`.legacy_bytes()`、`KeyChord.from_textual(name) / from_win32(...) / from_kitty(...)` |
| `aliases.py` | `normalize(name) -> str`、`CANONICAL_ALIASES`、`CANONICAL_NAMES`（渲染/文档用） |
| `legacy.py` | `to_legacy_bytes(chord) -> str \| None`（替代 `keys.textual_key_to_raw` 与 `emulator.key_to_terminal` 的共用内核） |
| `win32_input.py` | `decode_win32_frame(params) -> KeyChord \| None`、`WIN32_INPUT_ENABLE/DISABLE` |
| `kitty.py` | `decode_kitty_frame(params) -> KeyChord \| None`、`kitty_push(flags)`、`kitty_pop()`、`kitty_query()` |
| `stream.py` | `FrameSplitter.feed(data) -> tuple[list[KeyChord], str]`（有状态、可注入） |
| `negotiate.py` | `KeyProtocolNegotiator.negotiate() -> KeyProtocolState`、`state.backend/flags/last_frames` |
| `driver_windows.py` | `YateWindowsDriver(WindowsDriver)`（`reader_factory` 可注入） |

---

## 2. 核心数据结构与表

### 2.1 `KeyChord`（canonical 模型）

```python
# yate/keyproto/model.py
KeyEventType = Literal["press", "repeat", "release"]

@dataclass(frozen=True)
class KeyChord:
    code: str                        # "a" | "1" | "/" | "enter" | "f5" | "grave_accent"
    mods: frozenset[str] = frozenset()      # {"ctrl","alt","shift","super"}
    event: KeyEventType = "press"
    source: str = "legacy"           # legacy | kitty | win32 | xterm
    text: str = ""                   # 关联文本（kitty flag 16 / win32 Uc）

    @property
    def name(self) -> str:  # canonical：mods 排序 + code，固定写法，供显示/绑定
    @property
    def key_name(self) -> str:  # Textual 兼容名（供 events.Key 使用）
    def legacy_bytes(self) -> str | None:
```

**canonical 化规则**（P1 唯一真理，写进 docstring 与测试）：
1. `code` 一律用"原子名"：字母 `a-z` 小写、数字 `0-9`、标点用符号本身（`/ ; [ ] \ - = , . ' \` `）、功能键 `f1..f24`、特殊键 `enter/tab/escape/backspace/delete/insert/home/end/pageup/pagedown/space`、小键盘 `numpad_*`。
2. `mods` 只保留集合 `{alt, ctrl, shift, super}`，排序后拼接。
3. **shift 只在"不产生不同字符"的键上保留**（`ctrl+shift+k` 保留；`shift+1` 归一为文本 `!` 而非 `shift+1`，与 Textual 的"带 text 时丢弃 shift"行为对齐）。
4. 别名（`underscore`/`slash`/`left_square_bracket`/`right_square_bracket`/`reverse_solidus`/`circumflex_accent`/`grave_accent`）统一归到符号形式；`ctrl+_`/`ctrl+/`/`ctrl+underscore`/`ctrl+slash` → **同一个 chord `ctrl+/`**。

### 2.2 win32-input-mode 帧语法与映射表

帧格式（WT/ConPTY，开启 `CSI ? 9001 h` 后收到）：

```
CSI Vk ; Sc ; Uc ; Kd ; Cs ; Rc _
```
`Vk`=虚拟键码，`Sc`=扫描码，`Uc`=Unicode 字符码点（无则为 0），`Kd`=1 按下/0 抬起，`Cs`=控制键状态（HIGH WORD of dwControlKeyState），`Rc`=重复计数。

```python
# Cs 位（只关心修饰键；ENHANCED 0x0100 忽略）
CTRL_STATE = {0x0001: "alt", 0x0002: "alt", 0x0004: "ctrl", 0x0008: "ctrl", 0x0010: "shift"}

VK_CODES = {
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "escape", 0x20: "space",
    0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home",
    0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2D: "insert", 0x2E: "delete",
    **{0x30 + d: str(d) for d in range(10)},          # 0..9
    **{0x41 + i: chr(0x61 + i) for i in range(26)},   # a..z
    0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4", 0x74: "f5", 0x75: "f6",
    0x76: "f7", 0x77: "f8", 0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/",
    0xC0: "grave_accent", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
    0x60: "numpad_0", 0x61: "numpad_1", 0x62: "numpad_2", 0x63: "numpad_3",
    0x64: "numpad_4", 0x65: "numpad_5", 0x66: "numpad_6", 0x67: "numpad_7",
    0x68: "numpad_8", 0x69: "numpad_9", 0x6A: "numpad_multiply",
    0x6B: "numpad_add", 0x6D: "numpad_subtract", 0x6E: "numpad_decimal",
    0x6F: "numpad_divide",
}
```

**合成规则（严格按序判断）**：
1. `Kd == 0` → `release`：**丢弃**（除非将来支持 key-release；`Rc` 不在此列）。
2. `Rc > 1` → 视为 repeat：**折叠为一次 press**（避免长按刷屏；可用 yaterc 开关放行）。
3. `Uc` 可打印，且 `mods ⊆ {shift}`，且 `Vk` 不是功能键 → 直接 `KeyChord(code=chr(Uc))`（文本路径）。
4. 否则查 `VK_CODES[Vk]`；查不到 → 返回 `None`（**保留原始帧到日志**，不猜）。
5. `Cs` 含 ctrl/alt 而 `Vk` 为 0 → 记日志丢弃（对齐 Textual `win32.py:273-277` 的语义，但我们**记录**而不是静默）。

> ⚠️ 表内容必须在 **P0 用真机抓帧校正**：`Uc` 的填充、`Cs` 的具体位、`Vk=0` 的边界、以及 `Ctrl+1` 的 `Vk/Uc` 组合以实测为准，本表是"待验证的假设"。

### 2.3 kitty 帧语法与序列

```
解码：CSI <code>[:<shifted>[:<base>]] ; <mods>[:<event>] ; <text-as-codepoints> u
编码/控制：push `CSI > <flags> u`   pop `CSI < u`   查询 `CSI ? u` → 回复 `CSI ? <flags> u`
flags：1=消歧 2=事件类型 4=备用键 8=全部按键上报 16=关联文本
yate 选用：`1|8|16 = 25`（与 Textual Linux 一致）；保守模式 `1`
```
- `mods-1` 位分解顺序 `shift(1) alt(2) ctrl(4) super(8) hyper(16) meta(32)`（见 `model.py` 常量，避免各处手写）。
- 带 `text` 时丢弃 shift（与 Textual `_xterm_parser.py:391-395` 的行为一致，防止 `shift+1` 变成 `shift+1` 而非 `!`）。

### 2.4 别名与 legacy 字节（唯一权威表，吸收原方案 A）

```python
# yate/keyproto/aliases.py
CANONICAL_ALIASES = {
    # 同一个 chord 的多种拼写 → canonical
    "ctrl+underscore": "ctrl+/", "ctrl+slash": "ctrl+/", "ctrl+_": "ctrl+/", "ctrl+/": "ctrl+/",
    "ctrl+left_square_bracket": "ctrl+[", "ctrl+[": "ctrl+[",
    "ctrl+reverse_solidus": "ctrl+\\", "ctrl+backslash": "ctrl+\\",
    "ctrl+right_square_bracket": "ctrl+]", "ctrl+]": "ctrl+]",
    "ctrl+circumflex_accent": "ctrl+^", "ctrl+^": "ctrl+^",
    "ctrl+`": "ctrl+grave_accent", "ctrl+grave": "ctrl+grave_accent",
    "ctrl+@": "ctrl+space",           # 注意：保留 widget 侧的双语义，见主计划 §5
}
```
`legacy.to_legacy_bytes(chord)` 的规则（替代 `editor_view/keys.py:49-86`）：
- ctrl + `a-z` → `chr(ord-96)`；ctrl + `[ \ ] ^ _ ? /` → C0；ctrl + 空格 → `\x00`；
- **ctrl + 数字 → `\x1b[<ord>;5u`**（与 `keymaps/base.py:110-113` 一致，保持绑定表自洽）；
- ctrl + shift + 字母 → C0（沿用 `emulator.py:156-161` 现状）；
- alt + 单字符 → `\x1b` + ch；alt + 命名键 → `\x1b` + 命名序列；
- 超出表达能力 → `None`（**并记日志**，这是"丢键可观测化"的关键）。

---

## 3. 关键设计决策（含被否方案）

| # | 决策 | 理由 | 被否的做法 |
|---|---|---|---|
| D1 | **自己分帧**，协议帧先被 `FrameSplitter` 吃掉，其余透传给 `XTermParser` | Textual 的 parser 不认 win32 `_` 帧，且会把它当未知序列在 100ms 后按字符重放（`_xterm_parser.py:176-198,233-244`），产生杂散按键 | 直接 `feed(全部字节)`，指望 Textual 解析 |
| D2 | **canonical 名 + 别名归一**，不按平台假设名字 | 实测同一按键在 Linux(flags=25, 全 CSI-u) 与 Windows(flags=1, Win32 记录) 下名字不同；上游改名也会漂移 | 继续维护"Textual 名 → 字节"的多份映射 |
| D3 | **协议优先级按"残留风险"排序：kitty 优先，win32-input-mode 受控启用** | kitty 是**栈式**协议，且规范要求主/备屏各持独立键盘栈 → 崩溃漏 pop 只影响备屏，**父 shell 天然免疫**；win32-input-mode 是**会话级私有模式、无栈无隔离**，漏 `l` 会污染共享同一 pty 会话的父 shell。win32 信息更全（VK+Cs），但风险高一级 | ①"win32 无条件优先"（把最高残留风险的协议放在默认路径）；②同时开两种（双份事件/优先级不确定） |
| D4 | **复制并改造**父类 `start/stop_application_mode`，附"上游实现假设断言" | 父类在启动里直接创建 `win32.EventMonitor`（`windows_driver.py:103-106`），无法只替换其中一环；Textual 无上限约束易漂移 | 猴子补丁父类的 EventMonitor（更脆） |
| D5 | 尺寸变化用 **`GetConsoleScreenBufferInfo` 轮询**补偿 | 字节流路径拿不到 `WINDOW_BUFFER_SIZE_EVENT`；轮询与输入等待合并，空闲无热点 | 依赖 Textual 的 resize 逻辑（无来源） |
| D6 | **三级恢复 + 救援命令** | 协议残留会污染用户 shell，是最严重的失效模式 | 只在正常路径恢复 |
| D7 | **只接管输入**，输出/渲染/鼠标/粘贴全部沿用 Textual | 把重构面缩到最小、可回退 | 自研完整驱动 |
| D8 | **来源分档**（`OFF`/`STREAM`/`RECORD`），判定在 driver 内部、可运行期回退 | 接管本身有成本（尺寸轮询、上游耦合、恢复风险），无协议收益时接管是纯负债；而"有无收益"**必须拥有字节流后才能确认**（鸡生蛋） | ① 在 `App.__init__` 之前按 `WT_SESSION`+kitty 检测一次性选 driver class；② 无条件接管；③ 在 RECORD 源下发协议序列 |
| D9 | **复用优于复制**：`RECORD` 档直接用上游 `win32.EventMonitor`；子类只 `super().start_application_mode()` + 按需接管 | 复刻面 = 漂移面；`RECORD` 的价值就是"与今天完全一致"，自己重写反而制造差异 | 整段复制父类 `start/stop_application_mode`（首版方案） |

**D3 展开：Windows 协议优先级（按残留风险从低到高）**

| 优先级 | 启用条件 | backend | 残留风险与理由 |
|---|---|---|---|
| 1 | kitty 查询（`CSI ? u`）有回复（WT ≥ 1.25、kitty/WezTerm 等） | `kitty`（flags=25） | **低**：备屏键盘栈隔离；即使漏 pop，切回主屏即免疫 |
| 2 | `--key-protocol=win32` 显式指定；**或** kitty 不可用 且 DECRQM 确认 `?9001` 可用 且 P4b.5/P4b.6 恢复基建就位 且 P0.6 实测结论允许 | `win32_input` | **中**：无栈、无隔离，必须靠"标记自愈 + Ctrl handler"兜底 |
| 3 | 以上都不成立 | `legacy`（`RECORD` 档） | **无** |

---

## 4. 严格实施顺序（Phase 0–9，逐步 checklist）

> **规则**：每步有编号 `Px.y`；**上一个 Phase 的 DoD 未全部勾选前，不得进入下一个 Phase**。允许在 Phase 内并行，禁止跨 Phase 倒置（见 §12）。

### Phase 0 — 探针与事实固化（前置，零侵入）
- [ ] **P0.1** 新增 `tools/probe_keys.py`：默认模式循环 `ReadConsoleInputW`，逐条打印 `(VK, Sc, Uc(hex), Kd, Cs(hex), Rc)`，并附"Textual 会命名成什么"（复用 `textual._ansi_sequences.ANSI_SEQUENCES_KEYS`）。
- [ ] **P0.2** `probe_keys.py --vt` 模式：设置 `ENABLE_VIRTUAL_TERMINAL_INPUT`，发送 `\x1b[?9001h`，`os.read` 原始字节并 hexdump（验证"开启后到底收到什么"）。
- [ ] **P0.3** 抓包四组按键（`Ctrl+P` / `Ctrl+1` / `Ctrl+/` / `Ctrl+Q`）在四种环境的输出：WT 1.24、WT 1.25 preview、conhost(cmd)、WezTerm。
- [ ] **P0.4** 验证两个探测假设：① `CSI ? 9001 $p`（DECRQM）是否被 WT 回复 `CSI ? 9001 ; 1 $y`；② `CSI ? u`（kitty flags 查询）是否被回复。结论决定 P5 的探测策略。
- [ ] **P0.5** 把实测帧固化为 `tests/fixtures/win32_input_frames.py`（`FRAMES: list[tuple[bytes, list[str]]]`），并在文件头写下环境/版本。
- [ ] **P0.6** **残留与恢复实测**（决定 R-H1 的真实等级与 D3 默认优先级）：在 WT 里发 `\x1b[?9001h` 后 `taskkill /F` 掉进程，观察父 shell（pwsh/bash）是否开始收到 `CSI … _` 垃圾；对照组：kitty 的 `\x1b[>25u` 漏 pop 后退出备用屏的后果。
- [ ] **P0.7** 验证 `SetConsoleCtrlHandler` 在 Ctrl+C / 关窗口（CTRL_CLOSE_EVENT）下能否完成一次小 `os.write`（关窗口只有约 5s 窗口）。
- **DoD**：抓包报告 + **残留/恢复实测结论**（追加到本文件 §13）+ fixture 入库。
- **禁**：此阶段不得修改 yate 运行时行为。

### Phase 1 — `KeyChord` 模型（纯函数，无 IO）
- [ ] **P1.1** 创建 `yate/keyproto/{__init__,model,aliases,legacy}.py`；实现 `KeyChord`、`normalize()`、`to_legacy_bytes()`。
- [ ] **P1.2** 把 `editor_view/keys.py` 的表搬进 `aliases.py`/`legacy.py`（**保留旧函数为薄包装**，签名不变，内部转发）→ 让 P2 可以小步改。
- [ ] **P1.3** 表驱动单测：`ctrl+underscore`/`ctrl+slash`/`ctrl+/`/`ctrl+_` → `ctrl+/`；`ctrl+1` → canonical `ctrl+1` 且 legacy 为 `\x1b[49;5u`；`shift+1` → 文本 `!`；`ctrl+shift+k` → `ctrl+shift+k`；未知键 → `None`（且日志可断言）。
- **DoD**：新增测试全绿；`pyright` 0 errors；**运行时行为零变化**（旧函数仍是唯一被调用者）。

### Phase 2 — 名字层接入派发（原方案 A 落地；**可独立发布 bugfix**）
- [ ] **P2.1** `keymaps/base.py`：`Keymap.__init__` 构建 `_name_index`（用 `aliases` 的 canonical + 别名）；`lookup(key, name=None)`、`handle_key(ctx, key, name=None)`、`add_binding` 同步登记。
- [ ] **P2.2** `interfaces.py:156` 扩签名 `handle_raw_key(raw, name: Optional[str] = None)`；`app.py:739-744` 实现。
- [ ] **P2.3** `editor_view/editor.py:231-236` 与 `app.py:1002-1007` 传入 `event.key`。
- [ ] **P2.4** 把 `app.py:985-999` 的 `ctrl+shift+e`/`ctrl+1`/`ctrl+p` 特例迁移为 `vsc.py`/`vim.py` 的正式绑定（动作已注册：`actions.py:158-161`），`app.on_key` 只保留 `TOGGLE_KEYS` / `ctrl+w` 和弦 / `alt+shift+p`。
- [ ] **P2.5** `keymaps/vim.py:170,415-416`：未映射的**不可打印**键返回 `False` 冒泡；补 vim 回归用例。
- [ ] **P2.6** `editor_term/emulator.py:139-148` 的 `key_to_terminal` 转发到 `legacy.to_legacy_bytes`（补 `/`、`underscore`、`slash`）。
- [ ] **P2.7** 单测：真实拼写驱动的派发测试（**不经过 `pilot.press` 的名称合成**）；`ctrl+@`/`ctrl+grave` 双语义回归测试。
- [ ] **P2.8** 手册（`manual.zh.md:1122-1128`）与 CHANGELOG 更新。
- **DoD**：`Ctrl+/` 在 WT/conhost/WezTerm/kitty 全部生效；vim 下 `Ctrl+P`/`Ctrl+1` 生效；pytest+pyright 全绿。
- **可发布点**：`v0.3.0-alpha`（纯 bugfix，不含协议层；风险最低）。

### Phase 3 — 协议帧编解码（纯函数，暂不接线）
- [ ] **P3.1** `win32_input.py`：`decode_win32_frame()` + §2.2 的 `VK_CODES`/`CTRL_STATE`；未识别 → `None` + 日志。
- [ ] **P3.2** `stream.py`：`FrameSplitter`（状态机：地面态 / `ESC` / `CSI` / 参数缓冲；终止符 `_`→win32、`u`→kitty；参数不合语法 → **整段交还透传**；缓冲区上限与 Textual 的 `_MAX_SEQUENCE_SEARCH_THRESHOLD=32` 对齐，防止吞字节）。
- [ ] **P3.3** `kitty.py`：`decode_kitty_frame()` + `kitty_push/pop/query`。
- [ ] **P3.4** 单测：用 P0 fixture 逐帧断言 canonical 名；分帧器"帧/透传"切分测试（含跨 read 边界的半截帧）。
- **DoD**：纯函数测试全绿；**尚未有任何序列被发送**（此时终端行为仍与 P2 完全一致）。

### Phase 4a — `YateWindowsDriver` 骨架 + RECORD 记录源（先建"等价今天"的基线）
- [ ] **P4a.1** `driver_windows.py`：`YateWindowsDriver(WindowsDriver)`，**继承而非整段复制**（`super().start_application_mode()` 完成输出/模式/上游输入源初始化，再按来源决策接管）；加 `_UPSTREAM_ASSUMPTIONS` 结构性断言（父类是否仍有 `_event_thread`/`_writer_thread`/`_enable_mouse_support`），失败 → **自动 OFF（不接管）**而非崩溃。
- [ ] **P4a.2** `RECORD` 档：**直接复用上游 `win32.EventMonitor`，零复刻**（RECORD 的语义就是"与今天完全一致"）。⚠️ 停上游线程时**不要用 `disable_input()`**——它会顺带关掉鼠标支持（`windows_driver.py:108-120`）；只做 `exit_event.set(); _event_thread.join(); exit_event.clear()`。
- [ ] **P4a.3** `yate/app.py:158` 注入 `driver_class`；`--key-protocol off` 时不注入（用原生驱动）。
- [ ] **P4a.4** 契约测试：`FakeRecordReader` 喂固定 INPUT_RECORD → 断言事件序列与原生驱动**逐事件等价**（该快照同时充当"上游漂移报警器"）。
- **DoD**：默认行为与今天**逐事件一致**（本阶段不做任何改进）；pytest 全绿。
- **禁止跳过**：P4a 是后续所有改动的对照基线。

### Phase 4b — STREAM 字节流源（真正的接管）
- [ ] **P4b.1** 输入线程：`wait_for_handles([stdin], 100)` + `os.read(fd, 1024)`；`reader_factory` 可注入（测试用 `FakeReader`）。
- [ ] **P4b.2** 字节流 → `FrameSplitter` →（本 Phase 只走透传）`XTermParser`；`process_message` 保持不变。
- [ ] **P4b.3** 尺寸变化：**优先复用 Textual 的 in-band resize**（把 `\x1b[48;…t` 透传给 `XTermParser` 即可，前提是 `CSI ? 2048` 探测成功），`GetConsoleScreenBufferInfo` 轮询仅作兜底。
- [ ] **P4b.4** **交接顺序**：先启动新源线程 → 再停上游记录线程（消除 R-H8 的丢键窗口）。
- [ ] **P4b.5** 恢复基建（对应主计划 §6.2 R-H1）：
  - `restore_terminal_best_effort()` 幂等；关闭序列**直写 fd**（`os.write(1, b"\x1b[?9001l\x1b[<u")`），**不依赖 WriterThread**；
  - 接入 §5.3 的**五个正交入口**（`stop` / `finally` / `atexit` / excepthook / **`SetConsoleCtrlHandler`**）；
  - 恢复后**读回校验** `GetConsoleMode`，失败写日志 + 提示 `--reset-terminal`。
- [ ] **P4b.6** **跨进程自愈**：协商成功时写 `~/.yate/data/terminal-state.json`（pid、已发序列、控制台模式原值、时间戳）；正常退出删除；**启动时若发现残留 → 先发保守恢复序列再继续**（覆盖 SIGKILL/native crash）。
- [ ] **P4b.7** 等价性测试：给 STREAM 源喂"无协议终端的 legacy 字节"，断言与 RECORD 源**同结果**（证明分帧器不吞字节）。
- **DoD**：STREAM 的透传路径与 RECORD 基线语义等价；`--key-protocol off` 逃生门可用；五类退出路径（正常/未捕获/Ctrl+C/关窗口/强杀）后终端均干净。

### Phase 5 — 来源策略 + 协商状态机 + 运行期回退
- [ ] **P5.1** `SourcePolicy.decide(...)`（见 §3 D8）：输入 = CLI/yaterc/env 的 `key_protocol`、`GetConsoleMode(stdin)` 是否成功、环境能力表（`WT_SESSION`、`ConEmuANSI`、`TERM_PROGRAM`、`WEZTERM_*`、`KITTY_WINDOW_ID`、`VTE_VERSION`、`LC_TERMINAL`）；输出 = `OFF | STREAM | RECORD`。
  - **判定位置**：driver 内部的 `start_application_mode`，**不是**在 `App.__init__` 之前选 driver class。
- [ ] **P5.2** 协议协商（仅 STREAM）：`KeyProtocolState(source, backend, flags, detected, last_frames)`；探测策略按 P0.4 结论二选一：
  - DECRQM 可用：发 `CSI ? 9001 $p`，等 `CSI ? 9001 ; 1 $y` → 确定；
  - 否则：**无害开启 + 观察**（`CSI ? 9001 h`，300ms 内出现 `_` 帧即确认，同时保留 legacy 通路）。
- [ ] **P5.3** 严格开启/关闭顺序实现（§5 表）；**RECORD 档不得发送任何协议序列**。
- [ ] **P5.4** 运行期回退：STREAM 连续 N 帧解析失败、或 300ms 内既无帧又无有效字节 → `_switch_source(RECORD)`（停线程 → 恢复控制台模式 → 启动记录线程），原因写入状态与日志。**用户显式强制（`--key-protocol=win32/kitty`）时不自动降级，只告警**。
- [ ] **P5.5** `cli.py` 新增 `--key-protocol {auto,win32,kitty,off}`、`--reset-terminal`；`config.py`（`_KNOWN_OPTIONS:48-51`、`YateConfig:77-110`、校验区）新增 `key_protocol`。
- [ ] **P5.6** 单测三组：① 来源判定表（含 stdin 非控制台 → `OFF`/`RECORD`）；② 状态转移（确认 win32 / 超时降级 / kitty 回复 / 无回复 / off / 强制模式不降级）；③ 回退切换不丢按键、不残留。
- [ ] **P5.7** 真机验证四档：WT 1.25（期望 `STREAM+win32`）、WT 1.24（期望 `STREAM+kitty(未确认)` 或 `RECORD`）、conhost（期望 `RECORD`/`OFF`）、`yate < file`（期望 `OFF`，走原生驱动）。
- **DoD**：`--key-protocol off|win32|kitty|auto` 四档行为可预期且可观测；`--reset-terminal` 可从"协议残留"状态恢复终端。

### Phase 6 — 事件合成闭环（真修复）
- [ ] **P6.1** `FrameSplitter` 的帧 → `KeyChord` → `events.Key(chord.key_name, chord.text)` → `process_message`。
- [ ] **P6.2** 批次级去重：同一次 `read` 中若含协议帧，则该批次不再让同名 legacy 字节走 `XTermParser`（防双触发）。
- [ ] **P6.3** `ctrl+@`/`ctrl+grave` 双语义在协议路径下的等价性（win32 的 `Vk=0xC0 + ctrl` → `ctrl+grave_accent`；`Vk=0x20 + ctrl` → `ctrl+space`）回归。
- [ ] **P6.4** 集成终端面板：面板聚焦时 chord → `legacy.to_legacy_bytes` → PTY（`terminal.py:189-208`）；`shift+pageup/pagedown` 行为不变。
- [ ] **P6.5** 真机验收矩阵（§7 表）。
- **DoD**：WT 下 `Ctrl+1`、`Ctrl+/`、`Ctrl+;`、`Ctrl+Shift+字母` 全部可用且语义正确；无重复触发；vim/vsc 两种 keymap 均通过。
- **可发布点**：`v0.3.0-beta`（Windows 真修复）。

### Phase 7 — 可观测性与 feature 化
- [ ] **P7.1** `:keys` 覆盖层：当前 backend/flags、最近 N 条 `(原始帧 → canonical → 命中 binding)`；`YATE_DEBUG_KEYS=1` 时同时写 `~/.yate/data/keys.log`。
- [ ] **P7.2** `diagnostics.py`（`sections:84-97`、`_section_terminal:193-207`）新增 `[keyboard]` 段。
- [ ] **P7.3** `--reset-terminal` 完善（发 `\x1b[?9001l\x1b[<u\x1b[?1049l\x1b[?25h`，无需启动 App）。
- [ ] **P7.4** 扩展 API 文档：`api.bind_key` 接受 canonical 名（`services/extensions.py:242-266`）。
- **DoD**：用户能自助定位"某个键到底变成了什么"。

### Phase 8 — 跨平台对齐（可并行于 P7，但必须在 P6 之后）
- [ ] **P8.1** Linux/macOS：不改驱动，只把 `KeyChord` 归一化接入派发（Textual 的 kitty push 已在，`linux_driver.py:285-292`）。
- [ ] **P8.2** 回归：Linux 行为零变化（含 tmux 场景：`extended-keys` 缺失时应自然降级）。
- [ ] **P8.3**（optional）`xterm modifyOtherKeys` 后端（macOS Terminal / iTerm2），不阻塞发布。

### Phase 9 — 发布整理
- [ ] **P9.1** 手册新增"Windows Terminal 按键与协议"章节（含 WT 保留键清单、`--key-protocol`、`--reset-terminal`、"终端乱了怎么办"）。
- [ ] **P9.2** `python -m tools.changelog` 生成双语 CHANGELOG。
- [ ] **P9.3** 版本与迁移说明：默认 `auto`、回退路径、已知不支持清单。
- [ ] **P9.4** 更新 `.trae/issues/issues.md:171` 与主计划状态。

---

## 5. 终端序列顺序规范（严格）

### 5.1 开启（`start_application_mode`，严格按此序）
| # | 动作 | 备注 |
|---|---|---|
| 1 | 记录 `get_console_mode(stdin)` / `(stdout)` | 供恢复比对 |
| 2 | stdout `|= ENABLE_VIRTUAL_TERMINAL_PROCESSING` | 与 Textual 一致（`win32.py:176-178`） |
| 3 | stdin `= ENABLE_VIRTUAL_TERMINAL_INPUT` | STREAM 必需；RECORD 下与 Textual 现状保持一致（`win32.py:179`） |
| 4 | 启动 WriterThread | 之后所有写出走它 |
| 5 | `\x1b[?1049h`（备用屏） | **必须先于协议 push** |
| 6 | `\x1b[?25l`、`\x1b[?1004h`、鼠标 `1000/1003/1015/1006h`、`\x1b[?2004h` | 沿用父类 |
| 7 | **启动输入线程** | 必须先于第 8 步，否则探测回复会丢失 |
| 8 | **来源决策**（`OFF`/`STREAM`/`RECORD`）→ 仅 STREAM 时做协议协商与开启（win32 → kitty → legacy 降级） | §6 状态机；RECORD 档到此为止，不发任何协议序列 |
| 9 | 首次渲染 | 由 App 正常流程触发 |

### 5.2 关闭（`stop_application_mode`，严格逆序）
| # | 动作 | 备注 |
|---|---|---|
| 1 | `\x1b[?2004l`（关粘贴） | 避免后续字节被当 paste |
| 2 | 停输入线程并 join | 确保不再有帧在处理中 |
| 3 | 协议关闭：win32 → `\x1b[?9001l`；kitty → `\x1b[<u` | **必须在离开备用屏之前**（kitty 栈语义）；**直写 fd（`os.write(1, …)`）并立即 flush，绕过可能已停的 WriterThread** |
| 4 | 鼠标 `1000/1003/1015/1006l` | |
| 5 | `\x1b[?1004l` | |
| 6 | `\x1b[?1049l` + `\x1b[?25h` | |
| 7 | flush | |
| 8 | 恢复 stdin/stdout 控制台模式（原值） | 与步骤 1-3 对应；恢复后**读回校验** `GetConsoleMode`，失败告警并提示 `--reset-terminal` |
| 9 | atexit 二次兜底（幂等） | 见 5.3 |

### 5.3 异常路径（必须正交：不依赖同一个假设）
| 场景 | 处理 | 依赖的机制 |
|---|---|---|
| Python 未捕获异常 | `yate/crash.py:85-102` 的 excepthook 在写日志**之前**调用 `restore_terminal_best_effort()` | Python 异常钩子 |
| `finally`（App.run 退出） | 与 5.2 相同（幂等，重复调用安全） | 控制流 |
| 正常退出 | 5.2 + `atexit` 二次兜底（幂等） | `atexit` |
| Ctrl+C / Ctrl+Break / 关窗口 / 注销 / 关机 | **`SetConsoleCtrlHandler`** 回调内直写关闭序列（返回 FALSE，让默认链继续） | Windows console 事件 |
| 进程被强杀 / native crash（SIGKILL 等价） | 当场无法清理 → **残留标记 + 下次启动自愈** + `yate --reset-terminal` | 磁盘状态 + 用户动作 |
| 恢复到一半失败 | 逐条 try/except，保证后续步骤继续执行；失败写日志 | 防御式恢复 |

---

## 6. 协商状态机

状态是**两维**的：`source ∈ {OFF, RECORD, STREAM}` × `backend ∈ {legacy, win32_input, kitty}`。

**来源决策（先于一切协议动作）**

| 条件 | source | 备注 |
|---|---|---|
| `--key-protocol off` / env `YATE_KEY_PROTOCOL=off` | `OFF` | 不注入自定义驱动，用 Textual 原生驱动 |
| `GetConsoleMode(stdin)` 失败（输入被重定向/管道） | `OFF` | 无法做字节流，退回原生 |
| `auto` + `WT_SESSION` 存在 | `STREAM` | 按 D3 优先级：先试 **kitty**，再考虑受控启用 win32 |
| 用户显式 `--key-protocol=win32` / `=kitty` | `STREAM` | 跳过探测直接使用；只告警不自动降级 |
| `auto` + 无能力信号（老 conhost / 未知终端） | `RECORD` | 等价今天行为，不做无收益的接管 |

**协商与回退（仅 STREAM）**

| source | 事件 | 动作 | 下一状态 |
|---|---|---|---|
| STREAM/legacy | 启动 | **先试 kitty（D3 优先级 1）**：发 `CSI ? u` + push `CSI > 25u` | 探测中(kitty) |
| 探测中(kitty) | 收到 `CSI ? <flags> u` | 记录 flags | STREAM/kitty |
| 探测中(kitty) | 150ms 无回复 | 保持 push（无害）但标 `detected=False`；**仅当 P0.6 实测允许且恢复基建就位**才尝试 win32 | STREAM/kitty(未确认) 或 探测中(win32) |
| 探测中(win32) | 发 `CSI ? 9001 $p` 收到 `CSI ? 9001 ; 1 $y`，或收到首个 `_` 帧 | 标记确认 | STREAM/win32_input |
| 探测中(win32) | 300ms 超时且无帧 | `CSI ? 9001 l` 回滚 | RECORD/legacy |
| STREAM/* | `--key-protocol=win32/kitty` 显式强制 | 跳过探测直接使用 | 对应 backend |
| STREAM/* | 收到无法解析的 `_` 帧 | 计数 + 日志；连续 N 次 → `_switch_source(RECORD)` | RECORD/legacy |
| STREAM/* | 运行期 300ms 无有效字节且无帧 | `_switch_source(RECORD)`（用户强制模式除外，只告警） | RECORD/legacy |
| RECORD/* | 用户运行中 `:set key_protocol=win32`（若实现） | 重建线程并升到 STREAM | STREAM/* |

> **回退安全性**：`_switch_source` 必须"停线程 → 恢复控制台模式 → 启动另一来源线程"，期间不丢按键（用短生命周期缓冲）；协议关闭序列必须在停线程后、离开备用屏前发出（§5.2）。

超时值集中在 `negotiate.py`（`PROBE_TIMEOUT = 0.15`、`WIN32_OBSERVE_TIMEOUT = 0.3`），便于测试注入。

---

## 7. 测试计划

| 层 | 内容 | 位置 |
|---|---|---|
| 单元 | `KeyChord`/别名/legacy 字节表驱动；win32/kitty 帧解码；`FrameSplitter` 边界（半截帧、非法参数、双 ESC） | `tests/test_keyproto_model.py`、`test_keyproto_frames.py` |
| 单元 | 协商状态机（注入伪响应与伪时钟） | `tests/test_keyproto_negotiate.py` |
| 注入式集成 | `FakeRecordReader`（RECORD 基线）与 `FakeReader`（STREAM）→ `YateWindowsDriver` → 断言 Key 事件与 binding 命中 | `tests/test_keyproto_driver.py` |
| 等价性 | ① RECORD 源 vs Textual 原生驱动 **逐事件等价**；② STREAM 源喂 legacy 字节 vs RECORD 源 **同结果**；③ stdin 非控制台/无协议 → 不接管 | 同上 |
| 来源切换 | `STREAM→RECORD→STREAM` 往返：不丢按键、无协议残留、状态与日志正确；用户强制模式不自动降级 | `tests/test_keyproto_source.py` |
| 恢复（正交） | 五类退出路径（正常 / 未捕获 / Ctrl+C / 关窗口 / 强杀）后终端干净；**残留标记在下次启动触发自愈** | `tests/test_keyproto_recovery.py` + 手工 |
| 契约/漂移 | 上游 INPUT_RECORD ↔ 事件序列快照；CI 增加 "latest textual" 作业，漂移即报警 | 同注入式集成 |
| 去重 | 5ms 时间窗去重 + `dup suppressed` 计数（正常为 0；异常路径可注入验证） | `tests/test_keyproto_driver.py` |
| pilot | **仅覆盖名字层**（合成 Textual 名）；注释中明确"测不到终端字节层" | `tests/test_app_textual.py` |
| 回归 | `ctrl+@`/`ctrl+grave` 双语义、vim 冒泡、集成终端按键、`ctrl+w` 和弦 | 现有测试文件 |
| 手工矩阵 | WT 1.24 / WT 1.25 preview / conhost / PowerShell / cmd / WezTerm /（Linux）kitty + tmux | `§7.1` |
| 崩溃矩阵 | 正常退出 / `raise` / `taskkill /F` / faulthandler native crash → 检查终端状态与 `--reset-terminal` | 手工 |

### 7.1 手工验收矩阵
| 环境 | 期望 backend | `Ctrl+1` | `Ctrl+/` | `Ctrl+;` | `Ctrl+Shift+K` |
|---|---|---|---|---|---|
| WT 1.25 preview | win32 | ✅ | ✅ | ✅ | ❌（WT 保留） |
| WT 1.24 | kitty(未确认) 或 legacy | ⚠️ 视 kitty 生效情况 | ✅ | ⚠️ | ❌ |
| conhost / cmd | legacy | ❌（平台上限，`--diag` 明确提示） | ✅ | ❌ | ✅ |
| WezTerm | kitty | ✅ | ✅ | ✅ | ✅ |
| Linux kitty / tmux | kitty / legacy | ✅ / 视 tmux | ✅ | ✅ | ✅ |

---

## 8. 兼容性与上游漂移

- `pyproject.toml:13` 目前是 `textual>=8.0`（无上限）。本计划引入对 Textual 内部实现的依赖（`WindowsDriver.start_application_mode` 的结构、`win32.enable_application_mode`、`XTermParser.feed`、`events.Key`），建议 **P4 同期收紧为 `textual>=8.0,<9`**，并在 `driver_windows.py` 顶部写"上游实现假设"注释 + 运行时断言。
- 断言失败/`ImportError` → 自动降级为原生 `WindowsDriver` + 在消息栏提示一次（不阻断启动）。
- Textual 若将来自己支持 win32-input-mode，则 P4/P5 可整体退役 —— 在代码里留 `# retire-when: textual supports win32-input-mode` 标记。

---

## 9. 工作量估算与里程碑

| Phase | 人日 | 主要不确定性 | 可发布点 |
|---|---|---|---|
| P0 | 1 | 抓包环境；残留/恢复实测（P0.6/P0.7） | — |
| P1 | 1 | 别名边界（shift/text 规则） | — |
| P2 | 1.5 | `ctrl+@` 双语义回归 | **v0.3.0-alpha** |
| P3 | 1.5 | `_MAX_SEQUENCE_SEARCH_THRESHOLD` 对齐、半截帧 | — |
| P4a | 1.5 | 上游断言、契约快照 | — |
| P4b | 2.5 | 恢复基建（Ctrl handler + 残留自愈）、交接顺序、尺寸 | — |
| P5 | 2 | 来源判定表、协议优先级（取决于 P0.4/P0.6 结论）、运行期回退 | — |
| P6 | 2 | ConPTY 往返折损、双触发 | **v0.3.0-beta** |
| P7 | 1 | — | ✅ |
| P8 | 1 | tmux 降级 | ✅ |
| P9 | 0.5 | — | **v0.3.0** |
| **合计** | **≈16 人日** | 相比首版 +3：RECORD 基线（P4a）、来源策略/回退（P5）、恢复基建与实测（P4b.5/6 + P0.6/7） | 2 个中间可发布点 |

---

## 10. 风险登记册（协议层视角；等级定义见主计划 §6.2）

### 10.1 降低风险的手段分类（本计划的落点）

| 手段 | 本计划中的体现 |
|---|---|
| **消除** | kitty 优先（备屏栈隔离）；`RECORD`/`OFF` 档不发协议序列；无收益不接管 |
| **隔离** | 来源分档 + 运行期回退；确认后才切事件来源；面板路径只做 legacy 翻译 |
| **自愈（必须正交）** | `stop` / `finally` / `atexit` / `SetConsoleCtrlHandler` / **残留标记跨进程自愈** / `--reset-terminal` |
| **复用** | `RECORD` 档直接用上游 `EventMonitor`；输出/鼠标/粘贴全部沿用 Textual |
| **可观测** | `:keys`、`[keyboard]` diag、`dup suppressed` 与"解析失败"计数 |

### 10.2 登记表

| ID | 风险 | 触发信号 | 立即动作 | 本版新增的更强手段 |
|---|---|---|---|---|
| R-H1 | 终端状态未恢复 | 用户报"shell 里按键变 `CSI … _`" | `yate --reset-terminal`；核对 §5.2/§5.3 | kitty 优先（消除）；**残留标记 + 下次启动自愈**（覆盖 SIGKILL）；**Ctrl handler**（覆盖关窗口） |
| R-H2 | 自建驱动丢事件 | 鼠标/尺寸/粘贴异常 | `--key-protocol off` 回原生定位 | `RECORD` 档**复用上游（零复刻）**；STREAM 档按能力对等清单验收 |
| R-H3 | 双触发 | 一次按键两次动作 | 检查 P6.2 批次判定 | **5ms 时间窗去重 + `dup suppressed` 计数**（静默 → 可观测） |
| R-H4 | 上游漂移 | 断言失败/导入异常 | 自动 OFF + 收紧版本上限 | **契约快照 + CI "latest textual" 作业**（提前发现而非等用户报告） |
| R-H5 | 帧格式与假设不符 | P0 fixture 与 §2.2 表不一致 | **以实测为准更新表**，不得反向改 fixture | P0.6/P0.7 把"残留与恢复"也纳入事实清单 |
| R-H7 | 面板语义漂移 | 面板里 nvim/子程序按键异常 | 记录并关闭协议转发 | 面板只走 legacy 翻译；模拟器 `?9001h` 仅记录不实现 |
| R-H8 | 交接丢键 | 启动瞬间按键失效 | 检查 P4b.4 顺序 | **先起新源、再停旧源** |
| R-H9 | 环境误判 | SSH→Windows / WSL / VS Code 终端异常 | `--key-protocol off` | 默认保守（无 `WT_SESSION` → `RECORD`/`OFF`） |
| R-H10 | 强制模式但终端不支持 | 额外键不可用（legacy 仍可用） | 无需动作 | 连续解析失败计数；强制模式只告警 |

> 触发信号与计数统一经 `:keys` / `YATE_DEBUG_KEYS` / `--diag [keyboard]` 暴露，保证"降级"永远可见。

---

## 11. 顺序禁忌清单（必须遵守）

1. **禁止**在 P1/P2 完成前进入 P4：协议层会把帧解成 canonical 名，而名字层没有索引 → 拿到的键谁也认不出（等于白做）。
2. **禁止**在 P3 完成前发送 `\x1b[?9001h`：会收到无法解析的帧，用户按键变成垃圾（这是唯一可能"比现在更糟"的操作）。
3. **禁止**把 `CTRL_STATE`/`VK_CODES` 的假设当成事实：P0 抓包是唯一权威；表与实测冲突以实测为准。
4. **禁止**改动 §5 中序列的相对顺序（尤其 `kitty pop` 必须在离开备用屏之前；输入线程必须早于探测序列）。
5. **禁止**在 P6 之前删掉 legacy 通路：任何阶段都必须保留"协议不可用 → 传统字节"的降级路径。
6. **禁止**在没有回归基线（P4a.4 的逐事件等价测试）的情况下替换输入线程；**P4a 必须先于 P4b**。
7. **禁止**把"来源决策"放在 `App.__init__` 之前（一次性、不可纠正）；必须由 driver 在 `start_application_mode` 内决策，并支持 `STREAM→RECORD` 运行期回退。
8. **禁止**在 `RECORD` 档发送任何协议序列（含探测序列）：既无收益，又引入"残留"风险。
9. **禁止**让"终端支持 kitty 吗"成为唯一判据：判据是"**VK/修饰键能否交到我们手里**"，而不是终端的能力清单。
10. **禁止**把 win32-input-mode 放在默认优先级 1：它是**无栈、无备屏隔离**的会话级模式；必须先落地恢复基建（P4b.5/P4b.6）且 P0.6 实测允许后才可（D3）。
11. **禁止**用 `disable_input()` 停上游输入源——它会顺带关掉鼠标支持（`windows_driver.py:108-120`）。
12. **禁止**让多层恢复依赖同一假设：任何新增的终端状态改动都必须至少登记到 §5.3 的两个**不同**机制里。
13. **禁止**让协议残留退化成"只能重启终端"：必须同时具备"当场恢复 + 下次启动自愈 + 手动救援"三条路。

---

## 12. 附录：骨架伪代码

```python
# yate/keyproto/driver_windows.py
class YateWindowsDriver(WindowsDriver):
    # Upstream assumptions (textual 8.x): see _UPSTREAM_ASSUMPTIONS check.
    def __init__(self, app, *, reader_factory=None, **kw):
        super().__init__(app, **kw)
        self._reader_factory = reader_factory or _console_byte_reader
        self._splitter = FrameSplitter()
        self._protocol: KeyProtocolNegotiator | None = None

    def start_application_mode(self) -> None:      # 5.1 的顺序
        ...
        self._input_thread.start()                 # 7
        self._source = SourcePolicy.decide(self._options)   # 8a：OFF / STREAM / RECORD
        if self._source is Source.STREAM:
            self._protocol = KeyProtocolNegotiator(self.write, self.flush)
            self._protocol.negotiate()                      # 8b

    def stop_application_mode(self) -> None:       # 5.2 的顺序（幂等）
        ...

    def _input_loop(self) -> None:
        parser = XTermParser(debug=constants.DEBUG)
        while not self.exit_event.is_set():
            data = self._reader_factory(0.1)
            if not data:
                continue
            frames, passthrough = self._splitter.feed(data)
            for chord in frames:
                self.process_message(events.Key(chord.key_name, chord.text))
            if passthrough:
                for event in parser.feed(passthrough):
                    self.process_message(event)
            self._poll_size()          # D5：尺寸轮询与输入等待合并
```

```python
# yate/keyproto/stream.py（分帧器要点）
class FrameSplitter:
    _LIMIT = 32                       # 与 Textual 的搜索阈值对齐
    def feed(self, data: str) -> tuple[list[KeyChord], str]:
        """返回 (协议帧, 需要交给 XTermParser 的透传字符串)。

        规则：仅当 ESC '[' 起、以 '_' 或 'u' 结束且参数符合语法时才算协议帧；
        参数非法或缓冲超限 → 整段交还透传（宁可让它走 legacy 路径，也不吞字节）。
        """
```
