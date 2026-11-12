# 子计划 j：manual 双语手册同步（wave-5）

> 唯一规范来源：`overview.md` §1.10 + 主计划
> `../macro-record-replay-unified-plan.md` §8（双语文档同步清单）/ F19；
> 本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F19（手册**实际**在 `yate/resources/manual.{en,zh}.md`，
  issue 备注写的 `yate/docs/manual.*.md` 在当前基线不存在）、`doc-conventions.md`
  §三（双语同时新增 / 同时更新）、§五（相对路径、无本机真实路径）。
- 上游依赖：**wave-4 全部验收通过**（键位 / 命令 / which-key 文档已定稿）。
- 输出：两份手册在相同章节同步登记宏键位、`:macro-*` 命令、`rec @a` 指示与
  **count 口径**（vim 数字前缀 N 次 / vsc 恒 1 / `:` 命令双入口、`1<f12>` 沿用
  边界）；成对一致性测试。

## 1. 独占文件清单（只改这些）

- `yate/resources/manual.en.md`
- `yate/resources/manual.zh.md`
- `tests/test_macro_docs.py`（新增）

> **不动** `yate/docs/which-key.*.md`（plan-i）、`tests/test_macro_integration.py`
> （plan-k）、`tests/manual_doc_fixture.py`（既有，只回归）、
> `yate/editor_components/manual.py`（手册显示组件，不改）。

## 2. 具体修改（文件:行号）

> 英文版行号取自 F19 实测；**中文版章节位置由执行者按相同标题定位**（主计划
> §12 第 4 条：本方案不给中文版的臆测行号）。两份必须**同章节、同条目**改。

### 2.1 `yate/resources/manual.en.md`

| 章节（行号） | 新增内容 |
|---|---|
| `### 3.6 Status bar`（**第 266 行**） | 追加一句：录制态在 mode chip 旁显示 `rec @<reg>`（例 `rec @a`），停止后消失 |
| `## 5. Key Bindings`（**第 354 行**） | 在该章导语或末尾追加 count 口径说明：vim 数字前缀 `N<回放键>` 回放 N 次（N 缺省 1），vsc 无 count 状态机（`take_pending_count()` 恒 1）、按 `<f11>` 回放 1 次 / `<f12>` 沿用上次次数；`:macro-play <reg> [count]` / `:macro-replay-last [count]` 命令参数提供等价双入口；`1<f12>` 并入「沿用」为已登记边界 |
| `### 5.1 vsc keymap (default, modeless)`（**第 373 行**，键位表含 `F5` 第 475 行、`F7` 第 514 行） | 在键位表追加 3 行：`\| \`F10\` \| Toggle macro recording \|`、`\| \`F11\` \| Play a recorded macro \|`、`\| \`F12\` \| Repeat last macro replay \|` |
| `### 5.2 vim keymap (modal)`（**第 516 行**，含 `F7` 第 591 行） | 追加**同样 3 行**（同一键弦、同一动作名，AC3 的文档面证据） |
| `## 8. Command Line (ex commands)`（**第 716 行**） | 追加 4 个命令的用法：`:macro-record [reg]`（按 `F10` 等价）、`:macro-stop`、`:macro-play <reg> [count]`、`:macro-replay-last [count]`；寄存器名 `a-z0-9`；非法寄存器 / 语法错误有 warn 提示；`F10` / `F11` 后等待一个寄存器字符 |

- **不改** `## Table of Contents`（第 15 行）：本次只在既有章节内增条目，不新增
  章节，TOC 无需变动（执行者若判断需要，须按「偏离计划」回填）。
- **不改**任何既有键位行（尤其 `F7` hover、`F5` command line）。

### 2.2 `yate/resources/manual.zh.md`

按 `doc-conventions.md` §三，在**相同章节标题**下加入与 §2.1 逐条对应的中文：
`### 3.6 状态栏`（`rec @a` 指示）、`## 5` 键位总章（vim 数字前缀 N 次 / vsc 恒 1 /
`:` 命令双入口 / `1<f12>` 沿用边界的 count 口径）、`### 5.1` /
`### 5.2` 键位表 3 行、`## 8` 命令行 4 个 `:macro-*` 用法。章节标题数量与顺序
与英文版一致（由 §3 用例断言）。键位记号 `F10` / `F11` / `F12` 与命令名保持
ASCII 不翻译（与既有 `F7` 行一致）。

### 2.3 路径裁决（写入报告）

issue 备注写 `yate/docs/manual.en.md` / `manual.zh.md`，但当前基线不存在；实际为
`yate/resources/manual.en.md` / `manual.zh.md`（F19）。以实际路径为准，该偏离
依据须在执行报告与主计划 §12 回填。

### 2.4 `tests/test_macro_docs.py`（新增）

`from __future__ import annotations`；`from pathlib import Path` 读两份 md；
`re` 取章节标题；用例见 §3。

## 3. 详细测试用例（`tests/test_macro_docs.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_manual_both_languages_list_all_three_macro_keys` | 无 | 读两份 md，取 `### 5.1` / `### 5.2` 段 | 两份的 5.1 段与 5.2 段**各自**都含 `F10` / `F11` / `F12` 三个记号（共 4 个段 × 3 = 12 处命中）；每处所在行含 `macro`（英文）/「宏」（中文）说明 |
| `test_manual_both_languages_document_macro_commands` | 无 | 取 `## 8` 段 | 两份都含 `:macro-record` / `:macro-stop` / `:macro-play` / `:macro-replay-last` 四个命令名；都含 `a-z0-9` 寄存器名说明 |
| `test_manual_both_languages_document_recording_indicator`（AC5） | 无 | 取 `### 3.6` 段 | 两份都含 `rec @` 字面量；英文含 `status bar` / 中文含「状态栏」 |
| `test_manual_both_languages_document_count_limitation`（AC2 口径） | 无 | 取 `## 5` 段 | 两份都明确「vim 数字前缀 N 次 / numeric prefix N」「vsc 恒 1 / always one」「`:macro-play` / `:macro-replay-last` 命令双入口」；英文含 `count` / `prefix`，中文含「次数」/「前缀」；**不含**「把按键回放次数写死为单次 / fixed one replay」类旧限制 |
| `test_manual_en_zh_section_headings_stay_paired`（doc-conventions §三） | 无 | 正则 `^## ` / `^### ` 取两份标题列表 | 两个列表**完全相等**（数量与顺序），且都含 `## 5`、`### 5.1`、`### 5.2`、`## 8`、`### 3.6` 对应标题 |
| `test_manual_paths_use_actual_resources_location`（F19 路径裁决） | 无 | `Path` 判断 | `Path("yate/resources/manual.en.md").exists()` 与 `.zh.md` 均为 `True`；`Path("yate/docs/manual.en.md").exists()` 为 `False` |
| `test_manual_existing_f7_hover_rows_unchanged`（回归 / 边界） | 无 | 取两份 `F7` 行 | 两份都仍含 `F7` 与 hover 说明（未被宏键行覆盖或删除） |
| `test_manual_new_sections_contain_no_machine_local_paths`（异常 / doc-conventions §五） | 无 | 逐行匹配新增段落 | 不含盘符 / 用户目录 / POSIX 家目录 / macOS 家目录四类本机绝对路径形态（按 `doc-conventions.md` §五 的口径）；仓库内引用均为相对路径 |

## 4. 验证方案

- **验证目标**：证明 doc-conventions §三双语同步、§五路径纪律、AC2/AC3/AC5 的
  文档面覆盖（**含按键 count 前缀 N 次 / vsc 恒 1 / `:` 双入口的新 count 口径，
  且无「把按键回放次数写死为单次」旧限制残留**）、F19 路径裁决落地、`F7` 等既有键位零回归。
- **需一并回归的既有测试**：`pytest tests/ -q -k "manual"`（含
  `tests/manual_doc_fixture.py` 相关用例）；`.venv\Scripts\python.exe -m
  tools.smoke_test run --jobs 4` 中 manual modal 相关场景（执行者按实际场景名取）；
  `tests/test_architecture.py::test_no_machine_local_home_paths_in_sources`
  （源码面守卫，文档面不设守卫，本计划自查新增段落）。
- **通过判定标准**：pytest 退出码 0、断言全绿；两份 md 成对一致；既有
  `F7` / `F5` 行未变；新增段落无本机绝对路径。
- **无法自动化部分**：手册在应用内（`<f8>`）渲染后的视觉效果人工验证：启动
  编辑器 → `<f8>` 打开手册 → 定位 §5.1 / §5.2 / §8，确认中英两版新增行显示
  正常、无表格错位。记录在报告。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pytest tests/test_macro_docs.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "manual"
.venv\Scripts\python.exe -m pyright tests/test_macro_docs.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

**D11 延伸（主代理补登）**：wave-4 实测证明「无产品源码改动」不能省略
pyright 与全量架构守卫（`test_comments_and_docstrings_stay_ascii` 会扫 `tests/`，
pyright strict 会扫新增测试文件）。故本子计划出口硬条件新增上面第 3、4 条命令，
要求 `pyright` 零诊断、`tests/test_architecture.py` 全量 exit 0。

**D12（并发冒烟避让）**：原第 3 条 `tools.smoke_test run --jobs 4` 与同波
plan-k §5 的同名全量冒烟并发执行，存在 `subagent-workflow.md` §三.3 与
`macro-record-replay-unified-integration-plan-k.md` §7 已登记的 timing 干扰风险。
主代理裁定：plan-j 本波**不跑全量冒烟**；manual modal 场景由 plan-k 的全量冒烟
与 wave-6 主代理独立复跑覆盖（wave-4 plan-i 已实测 `123/123 scenarios passed`）。
覆盖不降低，且避免两个 `--jobs 4` 冒烟互相踩踏；该偏离在进度文档登记。

## 6. 架构边界与守卫

- 触碰层级：资源文档（`yate/resources/`）+ 测试；**不改产品源码**。
- R 条款：不触碰任何架构边界；doc-conventions §三 / §五、
  `test_no_machine_local_home_paths_in_sources`（源码面，只回归）、
  §六 #34 注释 ASCII 守卫扫描面含 `yate/` 但不含 `.md` 文档（本计划改 md）。
- 守卫用例：`test_no_machine_local_home_paths_in_sources`（**只跑不改**；
  新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 双语只改一侧 / 章节不对齐 | §2.1/§2.2 同章节 + 标题配对用例 | `git checkout -- yate/resources/manual.en.md yate/resources/manual.zh.md tests/test_macro_docs.py` |
| 误用 issue 备注的 `yate/docs/manual.*.md` 路径 | §2.3 路径裁决 + 存在性用例 | 同上，并回填偏离依据 |
| 键位表两侧写法漂移（AC3 文档面） | §2.1 明确「同样 3 行」+ 两段各自断言 | 同上 |
| 新增行破坏既有 Markdown 表格 / TOC | 只在既有表格追加行、不动 TOC；人工渲染验证 | 同上 |
| 文档写本机绝对路径 | doc-conventions §五 + 专门用例 | 同上 |
| count 口径两侧文案不一致 / 残留把回放次数写死为单次的旧限制表述 | §2.1/§2.2 同章节逐条对应 + `test_manual_both_languages_document_count_limitation` 新口径断言与旧表述负向检查 | 同上 |
