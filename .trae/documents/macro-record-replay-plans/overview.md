# 宏录制回放 子计划总纲（波次与契约唯一依据）

> 【历史产物 · 方案已排除】本组文档记录 2026-11-11 第一轮宏录制回放方案
> （`<f6>` 单前缀 chord：`r` 录制 / `p` 回放 / `@` 重复），其实现**未并入**现行代码。
> 现行实现是 2026-11-12 第二轮方案（`<f10>` / `<f11>` / `<f12>` 三单键，
> 见 `../macro-record-replay-unified-progress.md`），键位、API 与命令契约以产品源码为准。
> 本文出现的 `MACRO_PREFIX_KEY`、`pre_dispatch`、`macro_awaiting`、`<f6>` 等符号
> 在现行代码中不存在，**不得**作为开发或施工依据。
> 2026-11-12 合并 `replay` 分支时仅为保留历史轨迹收录本组文档，代码未采纳。

主计划：`../macro-record-replay-plan.md`；issue 素材：
`../macro-record-replay-issue.md`（AC1–AC8）。路径基准：本目录
`.trae/documents/macro-record-replay-plans/` 下 `../../../yate/...` 即仓库根
同名文件；代码块内命令相对基准是仓库根。解释器统一
`.venv\Scripts\python.exe`。

## 一、子计划索引

| 子计划 | wave | 独占文件 | 交付 |
| --- | --- | --- | --- |
| `macro-record-replay-helper-plan-a.md` | 1 | `yate/session.py`、`yate/flows/macro_flows.py`（新）、`tests/test_macro_flows.py`（新） | L1 状态 + L3 核心逻辑 + headless 单测 |
| `macro-record-replay-keymaps-plan-b.md` | 1 | `yate/keymaps/keys.py`、`yate/keymaps/base.py`、`yate/keymaps/vim.py`、`yate/keymaps/vsc.py`、`tests/test_macro_key_binding.py`（新） | 双表统一键弦 + count 钩子 + 守卫用例 |
| `macro-record-replay-dispatch-plan-c.md` | 1 | `yate/editor_dispatch.py`、`yate/editor_compose.py`、`yate/editor.py` | pre_dispatch 接线 + 组装 |
| `macro-record-replay-ui-plan-d.md` | 2 | `yate/editor_components/statusbar.py`、`yate/flows/whichkey_flows.py`、`yate/actions.py`、`yate/commands.py`、`tests/test_macro_commands.py`（新） | 录制指示 / which-key 提示 / `:macro-*` 命令 |
| `macro-record-replay-e2e-plan-e.md` | 3 | `tests/test_macro_app.py`（新） | pilot 端到端 AC1/AC2/AC4/AC5 |

职责划分（`subagent-workflow.md` §一.3）：`yate/**` 产品源码一律**主代理
亲改**；`tests/` 新文件（a/b/d 的测试与 e 的 e2e）可派 `plan-executor`
（Hy4、`bypassPermissions`、探活同回合闭合）或主代理兜底，成员回报数据
一律独立复核，只认落盘结果。

## 二、API 契约（波内并行的唯一规范来源，签名逐字定死）

### 2.1 `yate/session.py` — `EditorSession.__init__` 追加字段（含 `#:` 注释）

```python
self.macro_registers: dict[str, list[str]] = {}
self.macro_recording: tuple[str, list[str]] | None = None
self.macro_playing: bool = False
self.macro_last_register: str | None = None
self.macro_awaiting: str | None = None  # "record" | "play" | None
```

### 2.2 `yate/keymaps/keys.py` — 新常量（`HOVER_DOC_KEY` 同款形态）

```python
MACRO_PREFIX_KEY: str = "<f6>"   # both built-in keymaps import this (AC3)
```

键弦裁决（2026-11-11 wave-1，详见 §六偏离 2）：原拟 `q` / `@` 可打印前缀
在 vsc（无模式）下是文本输入字符，绑定即破坏输入语义（存量守卫
`test_colon_is_inserted_literally` 锁定）；改单功能键前缀 chord——
`<f6> r {reg}` 录制 / 录制中 `<f6>` 停止 / `<f6> p {reg}` 回放 /
`<f6> @` 重复上次。

### 2.3 `yate/keymaps/base.py` — `Keymap` 新方法（vim 覆写）

```python
def take_pending_count(self) -> int:
    """Consume and return the pending count prefix (1 when absent)."""
    return 1
```

`vim.py` 覆写：直接 `return self._take_count()`（读 `count_str` 并清零，
语义对齐先例 vim.py:1260-1266）。

### 2.4 `yate/flows/macro_flows.py`（新模块，L3，禁止 import editor_components）

```python
type RawKeySink = Callable[[str], bool]      # ed.handle_raw_key
type MessageSink = Callable[[str], None]     # ed.message
type CountSource = Callable[[], int]         # keymaps.active.take_pending_count
REGISTER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")

class MacroFlows:
    def __init__(self, session: EditorSession, handle_raw_key: RawKeySink,
                 message: MessageSink, count_source: CountSource) -> None: ...
    def is_control_key(self, raw: str) -> bool: ...        # raw == <f6>
    def pre_dispatch(self, raw: str) -> bool: ...          # True = consumed
    def toggle_record(self, register: str | None = None) -> None: ...
    def play(self, register: str | None = None, count: int | None = None) -> None: ...
    def repeat_last(self, count: int | None = None) -> None: ...
```

`pre_dispatch` 行为规格（分支按序，落定形态）：

1. `session.macro_playing` 为真 → 返回 `False`（回放产生的键原样派发，
   不触发宏控制、不记录）。
2. `macro_awaiting == "prefix"`：清 awaiting；`r` → 置 `"record"` 返回
   `True`；`p` → 置 `"play"` 返回 `True`；`@` → `repeat_last()` 返回
   `True`；否则 warn 用法并返回 `False`（该键照常派发）。
3. `macro_awaiting == "record"`：清 awaiting；raw 是寄存器字符 →
   开始录制（`macro_recording = (reg, [])`）返回 `True`；否则 warn
   `macro: register name must be a-z or 0-9` 并返回 `False`。
4. `macro_awaiting == "play"`：清 awaiting；raw 是寄存器字符 →
   `play(reg)` 返回 `True`；否则 warn 并返回 `False`。
5. raw 为 `MACRO_PREFIX_KEY`：录制中 → 停止（序列覆盖写入
   `macro_registers`、记 `macro_last_register`）返回 `True`；否则置
   `awaiting="prefix"` 返回 `True`。
6. 录制中 → `macro_recording[1].append(raw)` 后返回 `False`。
7. 其余返回 `False`（照常派发）。

`play` 行为：录制中或 `macro_playing` → warn 拒绝（AC4）；空寄存器 →
warn（AC5/AC6）；否则记 `macro_last_register`，`count` 缺省时用
`count_source()`（vim `3` 前缀 → `take_pending_count`；vsc 恒 1），
`for _ in range(count): for raw in list(seq): handle_raw_key(raw)`，
`finally` 复位 `macro_playing`。`repeat_last` 无 last → warn。

### 2.5 `yate/editor_dispatch.py` — `_handle_raw_key` 顶部接线

`event_to_raw` 之后、keymap 派发之前：

```python
if ed.macro.pre_dispatch(raw):
    ed.refresh_ui()
    return True
```

`Editor` 委托入口（`handle_raw_key`）不变；回放回调即 `ed.handle_raw_key`。

### 2.6 `yate/editor_compose.py` / `yate/editor.py`

`editor.py` 声明 `self.macro: MacroFlows | None = None`（类属性注解形态
随 `_build_*` 工厂惯例，接入清单 §三.8：构造注入 `session` /
`ed.handle_raw_key` / `ed.message`，不持 App 句柄——`handle_raw_key` /
`message` 是绑定方法注入，属语义能力注入先例）；`editor_compose.py`
工厂内构造。组装顺序注释同步。

### 2.7 `yate/actions.py`（wave-2）

`populate` 注册 `macro_record_prefix` / `macro_play_prefix`（动作体分别
`ctx.session.macro_awaiting = "record" | "play"`；守卫锚点 + fallback）。

### 2.8 `yate/commands.py`（wave-2）

- `:macro-record [reg]`：无参 → 录制中则停止，否则 error 用法；有参 →
  校验寄存器字符后 `toggle_record(reg)`。
- `:macro-play {reg} [count]`：`count` 非法（非正整数）→ error。
- `:macro-repeat [count]`。

### 2.9 statusbar / whichkey（wave-2）

- `statusbar.refresh_status`：`session.macro_recording` 非空时模式 chip
  旁追加 `rec @{reg}` 段（pull，R13，不改样式注入方式）。
- `whichkey_flows.refresh()` 优先级链：pinned > ctrl+w > **macro awaiting**
  （record → 寄存器提示；play → `@ again repeats last` + 寄存器提示）>
  pending 候选 > 隐藏。

## 三、波次表

| wave | 内容 | 前置 | 验收（退出码 0 才进下一波） |
| --- | --- | --- | --- |
| 1 | 主代理亲改 a → b → c | 方案批准 | `pyright yate/ tests/ tools/ pack/`；`pytest tests/test_architecture.py -q`；`pytest tests/test_vim_keymap.py tests/test_editor_core.py -q` |
| 2 | 主代理亲改 d | wave-1 全绿 | 同上 + `tools.changelog check` |
| 3 | 测试落盘（执行者并行或主代理兜底）+ e | wave-2 全绿 | 4 个新测试文件 + 全量 `pytest tests/ -q -n auto` |
| 4 | 【审核】+【收尾】 | wave-3 回填 | 七项门禁 + 评审 0 blocker / 0 major |

## 四、wave-3 文件互斥矩阵（测试执行者）

| 文件 \ 执行者 | t1 | t2 |
| --- | :---: | :---: |
| `tests/test_macro_flows.py` | W | . |
| `tests/test_macro_key_binding.py` | W | . |
| `tests/test_macro_commands.py` | . | W |
| `tests/test_macro_app.py` | . | W |

## 五、偏离登记规则

同总纲先例：任何阈值 / 范围 / 选型偏离当轮回填本文件 §六并附实测命令与
退出码；子代理 spawn 失败 / 零产出按 `task-orchestration.md` §一.3.5 / §三
最多重试一次后主代理兜底并登记；并发跑 pytest 出现 timing 失败先
`-n 1` 复核再下结论。

## 六、偏离记录

| 轮次 | 偏离 | 实测依据 | 裁定 |
| --- | --- | --- | --- |
| 【方案】 | `plan-architect-designer` 未派发（本机运行时 `qwen-3.7-plus` / `Hy4 preview` 前轮均 spawn 失败在案，同环境不再重试） | pack-dist-zip 进度文档「失败与重试记录」 | 主代理按剧本亲自产出主计划 + 本总纲 + 5 子计划，如实标注「子代理零产出」 |
| 【方案】 | 执行职责重排：产品源码全由主代理亲改（§一职责划分），wave-1 的 a/b/c 由主代理按序完成而非三执行者并行 | `subagent-workflow.md` §一.3 禁止子代理改 `yate/**`；wave-1 三子计划产品文件本就归主代理 | 合并为「主代理串行亲改 + 测试执行者并行」，波次验收口径不变 |
| wave-1 | 键弦由 `q` / `@` 双可打印键改为 `<f6>` 单前缀 chord（`r` record / `p` play / `@` repeat），常量合并为 `MACRO_PREFIX_KEY`；两表绑定合一 `macro_prefix` 动作 | 冲突探针 `q`/`@` 两表空闲，但 vsc 为无模式编辑器、可打印字符是文本输入（存量守卫 `test_colon_is_inserted_literally` 锁定）；issue IKUOAM 明文授权「具体键弦在方案文档定稿」且要求两表同键弦同动作——`<f6>` 同时满足三约束（两表空闲 / 不吞文本 / AC3 统一） | 采纳；§2.2/§2.4 契约已更新为落定形态，子计划 a/b 原文键弦描述为历史事实 |
| wave-1 | `editor.py`（802 行）登记 `SIZE_EXEMPT_FILES` 豁免 | big-module-split-2 拆分后恰 800 行，MacroFlows 属性 + 导入 +2 行越线；`test_source_files_within_size_threshold` 实测 `AssertionError: [('editor.py', 802)]` | 单一职责（组装工厂薄委托）按 §三.7 登记豁免，`tests/test_architecture.py` 与 `.trae/rules/architecture-boundaries.md` 两处同步 |
