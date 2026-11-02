# plan-c：遗留清扫（R3）

依赖：无（与 plan-a 可并行；涉及 `scenarios/filemanager.py` / `tests/test_filemgr.py` 的改动排在 plan-a / plan-b 之后执行以避撞）。

## c-1 is_mounted 死守卫 9 处

背景：Textual 8.2.8 的 `Widget.is_mounted` 只置 True 从不复位（unmount 不清），死守卫不拦截任何路径。处置按 m9 同法二选一：换 `is_attached`，或保留并 docstring 注明 defensive redundancy。**逐处定稿**：

| 文件:行 | 上下文 | 倾向 |
|---|---|---|
| `manual.py:487` | 渲染守卫 | 甄别 worker/回调上下文 → `is_attached` |
| `manual.py:493` | 同上 | 同上 |
| `manual.py:578` | `not source or not self.is_mounted` | 同上 |
| `manual.py:590`（原 :587） | 同上 | 同上 |
| `manual.py:690` | `query is None or not self.is_mounted` | 同上 |
| `find_replace.py:390` | worker 回调画守卫 | `is_attached` |
| `find_replace.py:554` | 同上 | `is_attached` |
| `highlighting.py:407` | **注意**：本类在 :106 有自有 `is_mounted` property（镜像宿主 widget），`self.is_mounted` 走的是该 property 而非 Textual 原生 | 甄别：若宿主 widget 可达且 `host.is_attached` 语义等价则换；否则保留 + docstring 注明 |
| `highlighting.py:434` | 同上 | 同上 |

既有先例（照抄口径）：`filemgr.py:452` / `palette.py:236` 的注释——"is_mounted never resets on unmount; is_attached mirrors Textual's own mount check"。

执行步骤：

1. 逐处读上下文（是否在 worker / call_after_refresh 回调内），定稿 `is_attached` 或 docstring 注明；
2. `grep -rn "\.is_mounted\b" yate/` 复核全清单，结果与逐处处置落盘本文档「执行记录」节（`editor.py:253` 的 `lambda: ed.mounted` 注入与 `panes.py` 的注入形参不在 issue 清单内，不动；`completion_flows.py` / `commandline.py` 命中的是 popup widget 的 `is_mounted`，同样不在清单内，不动——如顺手核实其同样只置 True，仅登记不改）；
3. `tests/test_filemgr.py` 风格不新增死守卫测试；既有测试全绿即可。

## c-2 filemgr 测试宿主去重（issue 表述偏差登记）

issue 原文："new_app 加 `filemanager_dir` 形参消除 filemgr 用例自建宿主重复"。

考古事实：`new_app` 实际在 `tools/smoke_test/harness.py:361`（签名 `target/keymap/theme_name/config`），**不在 conftest**；filemgr 单测宿主是 `tests/test_filemgr.py` 本地 `_Host` + `_screen` 辅助。偏差登记于本节，执行按实际落点裁量：

1. `tools/smoke_test/harness.py::new_app` 增加可选形参 `filemanager_dir: Path | None = None`：非 None 时启动后打开 filemanager 屏并返回 `(app, screen)`（或按 harness 现有返回形态最小扩展），smoke 场景 `filemanager.py` 改用之；
2. `tests/test_filemgr.py` / `tests/test_app_filemgr.py` 的本地 `_Host`/`_screen` 重复：若两文件各自复制了等价宿主，抽到测试共享处（tests 内模块级 helper 或 conftest fixture——**不建 Protocol**、不建共享类型层，只传具体对象/函数）；若仅一处本地宿主（无重复），则登记"无重复可消除"并只做第 1 步，不过度工程。

## c-3 filemanager SVG 冒烟基线

事实：`tools/smoke_test/scenarios/filemanager.py` 已在 :106 调 `snapshot_svg`，但 `tools/smoke_test/smoke_baselines/` 无 filemanager 基线文件（其余 121 场景均有 `<scenario>.json`）。

步骤：

1. 读 `tools/smoke_test/baselines.py` 与 CLI 入口，确认基线登记机制（`--baseline` / `--with-svg` 类开关）；
2. **只对 filemanager 场景**登记基线（禁止全量 snapshot——master 存量 5 处漂移登记，见项目记忆；全量重登会把漂移洗白）;
3. 冒烟门禁按总纲跑全量 121+ 场景，filemanager 场景应从"无基线跳过比对"变为"基线比对通过"。

## 验收

- 五项门禁全绿；
- `grep -rn "\.is_mounted\b" yate/` 输出与执行记录清单一致（清单外零新增）；
- 冒烟 filemanager 场景基线在位且通过。

## 回滚

单提交 `refactor(editor-view): sweep dead is_mounted guards and filemgr test hosts`（如 c-1/c-2/c-3 分开提交更佳：`refactor(editor-view): drop dead is_mounted guards`、`test(smoke): register filemanager svg baseline` 等）；失败 reset 到波起点。

## 执行记录（2026-11-02）

四提交：`3158d12`（is_mounted 清扫）、`e27abcd`（harness 形参）、`b86e90c`（基线）、`90c7d7d`（规则行数同步）。

### c-1 逐处处置（9/9 全部换 `is_attached`，无一处需"保留 + docstring 兜底"）

依据实测 Textual 8.2.8 源码：`Widget.is_mounted` 返回 `_is_mounted`，全包仅 3 处赋值（message_pump.py:612/:668、app.py:3442），只置 True 从不复位；`is_attached`（message_pump.py:270）沿 `_parent` 链走 DOM root。宿主全部可达（MarkdownDocScreen / FindReplaceScreen 本身是 widget；highlighting mixin 宿主 EditorView 可达）：

| # | 处 | 上下文 |
|---|---|---|
| 1-5 | `manual.py` :489/:495/:580/:589/:692（改前行号 :487/:493/:578/:587/:690） | `_load_doc` / `_rerender` worker 协程、`_flush_pending_search` 定时回调 |
| 6-7 | `find_replace.py` :392/:556 | `_search_worker` / `_replace_worker` 协程 |
| 8-9 | `highlighting.py` :414/:441 | 定时回调 + tokenize worker；:106 的宿主面 stub property 一并更名 `is_mounted`→`is_attached`（docstring 注明 MessagePump.is_attached 随 DOM 退出复位） |

先例注释口径照抄 `filemgr/screen.py` 与 `palette.py:236`。

**grep 复核**（`\.is_mounted\b` over `yate/`，改后 8 处命中全为清单外存量未动）：`completion_flows.py:97/:277`（popup widget，顺手核实同样只置 True）、`commandline.py:334`（PromptBar 挂载前守卫仍活）、`panes.py:82/:216/:508/:517`（注入形参/原生读）、`highlighting.py:109`（stub docstring 解释性提法）。`editor.py:253` 的 `lambda: ed.mounted` 不匹配该模式。另将 `tests/test_manual.py:56` docstring 的守卫旧名提法同步为 `is_attached`（主代理裁定）。

### c-2 宿主去重

- `harness.py::new_app`（:361）加 `filemanager_dir: Path | None = None`，透传 `YateApp(filemanager_dir=...)`，返回形态不变；场景 `filemanager.py:61` 改用之（删直建 `YateApp` + `harness.track`，断言零变化）。
- **登记"无重复可消除"**：`test_app_filemgr.py` 经 pilot 驱动真实 YateApp、无本地宿主；`test_filemgr.py` 的 `_Host`+`_screen` 是唯一 filemgr 本地宿主；仓库另有 8 个不相干测试文件各自持 `_Host(App[None])` 惯用形，属既有惯例非重复。按计划 else 分支只做第 1 步，未抽公共宿主（避免过度工程）。

### c-3 冒烟基线

- 机制实测：`snapshot --scenario NAME [--with-svg]` 写 `smoke_baselines/<name>.json`（checks + svg_rows）；`compare` 默认丢弃双方 svg_rows（含每 run 随机 tmp 路径）；存量 120 个基线全部 `"svg_rows": {}`（checks-only 是既定约定）。
- 仅登记 filemanager：`smoke_baselines/filemanager_startup_navigation.json`（17 checks，svg_rows 空；未动其它 120 个基线，master 存量 5 处漂移未被洗白）。
- 验证：`compare --scenario filemanager_startup_navigation` → MATCH，exit 0（此前 SKIP）。

### 附加小项

- `screen.py` 实测 954 行（splitlines 口径，review-fixes 波 docstring 增补后复测 963 行）；`SIZE_EXEMPT_FILES` 只查集合成员无需改测试；规则文档 §三.7 条目 882 → 954（提交 `90c7d7d`，963 随评审修复波同步）。

### 门禁终态（plan-c 后全量）

pyright 0 诊断 / pytest 全量 exit 0 / 架构 37 passed / 冒烟全量 `run --jobs 4` **121/121 scenarios, 1463/1463 checks**，exit 0（78.85s）/ filemanager 基线 MATCH。coverage 门禁结果见总纲执行记录。
