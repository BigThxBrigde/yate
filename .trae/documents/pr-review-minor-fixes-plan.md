# pr-review MINOR 修复轮方案（feat/readme-screenshots）

> 依据：2026-11-03 pr-review（`.trae/reviews/2026-11-03-pr-review-feat-readme-screenshots.md`）
> 的 3 项 MINOR。方案先行（plan-before-execute §二）；无人值守窗口按规则 §二.5
> bypass 审批直接推进。

## 一、目标与非目标

**目标**

1. F1：which-key 固定表（F9 sheet）与帮助层不再漏出原始 C0 控制字符——
   `key_name` 补齐 C0 0x1c–0x1e 的逆向命名，附回归用例 + 全表可打印性守护。
2. F2：`tests/test_app_panes.py` 两个用例的弦驱动状态断言全部 wait_until 化
   （§4.7 禁止"pause 一拍即断言"的时序假设）。
3. F3：SVG 体量基线（24 帧 2037 KB）维持登记，不做产物优化——该条在
   pr-review 中即"体量基线记录"性质，非缺陷。

**非目标**

- 不改 `yate/keyproto`（物理层解码，`\x1d` 分发语义不动）；
- 不动 vsc `indent` 行为（test_input_assist 钉桩的长久行为）；
- 不重生成除 which-key 外的任何帧；
- 不改冒烟场景与基线（两基线 `svg_rows` 均为 `{}`，渲染变更不触 compare）。

## 二、事实清单（调研取证）

1. **F1 根因**：`yate/keymaps/keys.py:162-170` `key_name` 单字符分支只覆盖
   `code == 0`（ctrl-space）与 `1 <= code <= 26`（ctrl-a..z）；`\x1f` 由
   `KEY_ALIASES`（keys.py:82）覆盖为 `<ctrl-/>`；**0x1c/0x1d/0x1e（FS/GS/RS）
   三字节掉穿到 `return key`**，原始控制字符原样返回。
2. 漏出路径：`yate/keymaps/vsc.py:50` `_k("<ctrl-]>", "indent", ...)` →
   parse_key → `"\x1d"` → `whichkey_flows._spec_label`（whichkey_flows.py:43-52，
   非打印首字符走 `key_name`）→ 固定表 label = 原始 `0x1d`（用户反馈轮
   `scrub_svg` 只能事后符化成 `^]`，产品侧显示本身错误）。
3. `key_name` 同时是帮助覆盖层（help overlay）的命名器——修复同源受益。
4. `parse_key` 已接受 `<ctrl-\>` / `<ctrl-]>` / `<ctrl-^>`（keys.py:142-145
   `@"..""_"` 区间），仅逆向缺失，补齐即完成 round-trip。
5. **F2 事实**：`tests/test_app_panes.py:229-246` 三个弦驱动断言（cursor (0,0)、
   cursor (1,0)、focus explorer）均为 `press + pause + assert` 一拍假设；
   既有注释（:221-223、:284-288）已承认同类 reconcile/focus 竞态。
   复现取证：全量 `-n auto` ×2 + 三文件加压子集 ×1 全绿（本轮），会话早期
   两次失败均发生在全量满载（`--tb` 被截断未存 traceback）。
6. 冒烟基线 `which_key_toggle.json` / `which_key_ctrl_w_chord.json` 的
   `svg_rows` 均为 `{}`（tools/smoke_test/scenarios/whichkey.py 只冻 checks）。
7. CLI 局部再生：`python -m tools.screenshots --only which-key`（__main__.py:48-54），
   画廊按"全量注册表 × SVG 存在性"渲染（:152-156），部分再生不缩水。

## 三、备选方案与否决理由

| 方案 | 裁决 | 理由 |
|---|---|---|
| F1-a `key_name` 补 C0 逆向（**采纳**） | ✅ | 命名单源在 L0 owning 模块，帮助层同步受益；与 parse_key 构成完整逆映射 |
| F1-b 仅 `whichkey_flows._spec_label` 加兜底符化 | ❌ | 治标：帮助层照旧漏；命名逻辑第二份，违反单源 |
| F1-c vsc 绑定改写 spec 绕开 | ❌ | 行为表不动；改 spec 触碰物理分发语义（非目标） |
| F2-a 弦后断言全部 wait_until 化（**采纳**） | ✅ | §4.7 指定路线（wait_until 轮询谓词）；消除"一拍假设"整类 |
| F2-b 放宽断言/删用例 | ❌ | 削弱覆盖，禁止 |
| F2-c 等待复现到 traceback 再修 | ⏸ | 3 次满载尝试未再现；不再烧时间，加固 + 👀 观察登记（如实记录） |
| F3 压缩 SVG 产物 | ❌ | 非缺陷；画廊刚需，优化属 churn |

## 四、分步实施

| 步 | 输入 | 改动文件 | 输出 | 验收命令 |
|---|---|---|---|---|
| S1 | keys.py:162-170 | `yate/keymaps/keys.py` | `key_name` 补 `28 <= code <= 30 → <ctrl-\|<ctrl-]|<ctrl-^>`（含 docstring 注记：parse_key ctrl 区间的逆向补全） | `pytest tests/test_key_notation.py -q` |
| S2 | S1 | `tests/test_key_notation.py` | 三字节 round-trip 用例（key_name + parse_key 互逆） | 同上 |
| S3 | F1 | `tests/test_whichkey_flows.py` | 全表可打印性守护：vsc+vim 固定表 label（`toggle()` 后 `panel.shown`）与 ctrl+w 弦表（WINDOW_CHORD_TABLE）逐 label `isprintable()` | `pytest tests/test_whichkey_flows.py -q`；变异自检（临时还原 S1 应变红，演练后还原） |
| S4 | F2 | `tests/test_app_panes.py` | 三个弦驱动断言 wait_until 化（焦点/游标谓词），附证据注释 | `pytest tests/test_app_panes.py -q -n 1` + 全量门禁 |
| S5 | S1 | `screenshots/which-key.svg` | `--only which-key` 重生成（scrub + 字体内嵌自动），ET 可解析 + 画廊不缩水 | `python -m tools.screenshots --only which-key`；ET 全量解析抽查 |
| S6 | 全部 | — | 收尾门禁五项 | pyright / pytest `-n auto` / 架构 / 覆盖率 / 冒烟 |
| S7 | 门禁 | `.trae/reviews/2026-11-03-pr-review-feat-readme-screenshots.md`、`README.md`(索引 #56 行)、本计划 | 修复轮回填 + 索引状态更新 | `python -m tools.changelog check`（如适用） |

## 五、风险与回滚

- S1 影响面 = 显示命名（sheet / help），不改任何 dispatch 字节；风险低。
  回滚：revert keys.py 单笔提交即恢复。
- S4 只动测试等待语义，不改断言目标；用例语义不弱化（wait_until 超时即败）。
- which-key.svg 重生成：若帧内容非预期，`git checkout` 该文件 + 画廊自愈
  （存在性过滤）。
- 冒烟基线不触（事实 6）；若 compare 意外出红，按 harness 惯例核对后处置。

## 六、模块交互

```mermaid
flowchart LR
    A[vsc.py 绑定表 &lt;ctrl-]&gt;] -->|parse_key| B["\x1d"]
    B --> C{whichkey_flows._spec_label}
    B --> D[help overlay]
    C -->|key_name| E["&lt;ctrl-]&gt;（修复后）/ 0x1d（修复前）
    E --> F[WhichKeyPanel 固定表 label]
    D --> G[帮助层键名]
```

## 七、执行记录（回填，2026-11-03）

全部按 §四 执行完毕，门禁五项全绿。偏离与增量记录：

| 项 | 记录 |
|---|---|
| S1 偏离（增量修复） | S3 守护首轮即红，暴露第二个同源缺陷：`<alt-backspace>` 经 `key_name` 两字节 ESC 分支漏出 `<alt-\x7f>`（裸 DEL）。同轮修复：alt 后缀字节改走单字符命名路径（`<alt-backspace>` / `<alt-ctrl-d>`），`test_key_name_reports_a_two_byte_escape_sequence_as_alt` 补两断言 |
| S3 变异演练 | 禁用 28..30 分支 → 3 处全红（守护 + `test_key_name_decodes_single_control_characters` + round-trip）；还原后全绿。守护对第二缺陷同样先行转红（首轮即红即演练证据） |
| S4 | `test_app_panes.py` 三处弦驱动断言 wait_until 化（焦点/游标谓词合并等待）；`-n 1` + 全量绿。三次满载复现尝试（全量 ×2 + 三文件加压 ×1）未再现早期 "asyncio exception"，残留 👀 观察登记（评审记录 §八） |
| S5 | `--only which-key` 重生成；探针：ET 可解析、无原始 C0 字节、`ctrl-]` 标签在位；画廊 README 字节不变（git diff 无该文件） |
| S6 门禁 | pyright 0（exit 0）/ 全量 pytest `-n auto`（exit 0）/ 架构 37（exit 0）/ 覆盖率 92.82%（exit 0）/ 冒烟 121/121·1463 checks（exit 0） |
| F3 | 维持体量基线不修（24 帧 2037 KB，最大 216 KB），评审记录 §八 销账为「维持登记」 |
