# yate Code Review（评审总纲索引）

> 本目录原名 `.trae/issues/`，本次整理后统一为 `.trae/review/`。
> 原 111 KB 巨型文件 `review.md` 已按「**一轮评审 = 一个带时间戳的文档**」逐章拆分为独立文件，
> 内容**逐字迁移**（含已修复条目的证据与处置记录，未删除任何评审内容）。
> 目录深度未变，文件内指向 `yate/**`、`tests/**`、`tools/**`、`.trae/documents/**`、
> `.trae/rules/**` 的相对链接全部保持有效，已逐条校验。

**命名规范**：`YYYY-MM-DD-<topic>.md`（topic 为英文小写连字符）。无日期可考的历史条目单独置于
`legacy-issues.md`（见文末「遗留问题」）。

---

## 一、速览：仍未闭环 / 尚未通过的项

以下 10 项为各轮评审中**仍未关闭**的条目（⏸＝暂缓/不修/挂起，🔧＝待修，👀＝待观察），
按所属轮次日期排列。除此之外各轮均**已通过并全修**。

| # | 日期 | 未闭环项 | 标记 | 出处 |
|---|---|---|---|---|
| 1 | 2026-09-16 | `ctrl+digit` 绑定使用 kitty 协议，多数终端不支持 | ⏸ 暂缓（P2 决策门 G1，待 WT 键位重构后与 `FOCUS_EDITOR_KEY` 一并处理） | [2026-09-16-full-review.md](2026-09-16-full-review.md) |
| 2 | 2026-09-24 | Windows `os.replace` 对外部占用句柄的兼容面变窄 | ⏸ 明确不修（既定取舍：错误路径安全、无数据丢失，Windows 限定） | [2026-09-24-appprotocol-refactoring-review.md](2026-09-24-appprotocol-refactoring-review.md) |
| 3 | 2026-09-25 | `HighlightProbe.doc` 应使用精确类型 `Document` | 🔧 未修（成立，Low/可维护性） | [2026-09-25-recheck-supplement.md](2026-09-25-recheck-supplement.md) |
| 4 | 2026-09-26 | Gitee Go 3.12 流水线从未实际运行，镜像可用性未验证 | 👀 待观察项（非代码缺陷，下次流水线触发时确认） | [2026-09-26-py312-upgrade.md](2026-09-26-py312-upgrade.md) |
| 5 | 2026-09-26 | 全项目评审 6 条建议级问题（ConPTY 句柄竞态 / 补全 worker 静默异常 / 高亮降级零日志 / 扩展 setup 半注册 / `editor.py` 组装过载 / 失败路径断言偏弱） | 🔧 待排期（P1×3、P2×2、P3×1） | [2026-09-26-full-project-review.md](2026-09-26-full-project-review.md) |
| 6 | 2026-09-26 | WT 下 `ctrl+1` 物理层丢键（conhost 不编 C0 码、WT 无 kitty CSI-u） | 🔧 部分待修（`ctrl+p`/`ctrl+/` 已修；`ctrl+1` 需 Phase B 自建输入通道，待启动） | [2026-09-26-wt-keybinding-ikh1ra.md](2026-09-26-wt-keybinding-ikh1ra.md) |
| 7 | 2026-09-27 | 输入线程宽泛 `except Exception` 的残余建议（`exc_info` / 重置驱动 / UI 通知） | 👀 登记待评估（与「复刻 stock 基线」存在张力，需与上游修法对齐） | [2026-09-27-pr26-keybinding.md](2026-09-27-pr26-keybinding.md) |
| 8 | 2026-09-27 | `explorer._apply_theme` 每次切主题全量 `refresh_tree()` | ⏸ 挂起（当前频率可接受，出现卡顿再拆分着色与重建） | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |
| 9 | 2026-09-27 | `scrollbars.py::render_bar` 复刻上游 1/8 粒度算法 | 📌 记录保留（Textual 升级需回归 `tests/test_scrollbars.py`） | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |
| 10 | 2026-09-27 | PB5 三终端矩阵：conhost / VS Code 待人工复测（WT 已由真机 harness 覆盖） | 🔧 遗留人工项 | [2026-09-27-keybinding-branch-review.md](2026-09-27-keybinding-branch-review.md) |

---

## 二、评审轮次总表

结论取自各文档自身记载（四维度表、⛔/✅ 结论行、条目勾选状态）；「当前处置状态」为照实标注，
本次仅为文档整理，未对任何未修条目做代码修改。

| 日期 | 评审范围 / 对象 | 结论（通过与否） | 阻断项 / 改进项数量 | 当前处置状态 | 文档 |
|---|---|---|---|---|---|
| （早期，无日期） | 历史问题登记：输入闪烁、不存在文件名卡住 | 通过 | 0 阻断 / 2 项 | ✅ 已全修 | [legacy-issues.md](legacy-issues.md) |
| 2026-09-16 | **全量代码审查（首次全量，`yate/` 全仓）** | ❌ 未通过（Critical 10 条必须修复） | 10 Critical / 29 Suggestion / 15 Nice-to-have | 🟡 部分待修：53/54 已修，1 项 ⏸ 暂缓（kitty `ctrl+digit`） | [2026-09-16-full-review.md](2026-09-16-full-review.md) |
| 2026-09-23 | 全量代码审查（第二轮：原子写 / undo 上限 / `modified` O(n) / 期望列 / 扩展自动加载 / 静默 except / symlink 环） | ✅ 通过 | 0 阻断 / 7 项 | ✅ 已全修（`05106d5` / `5190225` / `b0d154d` / `a89a720`） | [2026-09-23-full-review.md](2026-09-23-full-review.md) |
| 2026-09-23 | 已失效条目归档（复核基准 2026-09-23 当前代码） | ➖ 不适用（已失效，仅存档） | 0 / 0（3 条表格） | ⬜ 已失效：Python 3.9 兼容、中文 docstring、未使用导入 | [2026-09-23-invalidated-items.md](2026-09-23-invalidated-items.md) |
| 2026-09-23 | 冒烟补场景调查（`run --coverage` 缺口，`0984361`） | ✅ 通过 | 0 阻断 / 2 项 | ✅ 已全修（P2 决策门 G2 + 波次二 SP6，含冒烟 `terminal_focus_editor`） | [2026-09-23-smoke-scenarios.md](2026-09-23-smoke-scenarios.md) |
| 2026-09-23 | 补全弹窗按键放行修复的附带发现（Esc 后在途 worker 重开弹窗） | ✅ 通过 | 0 阻断 / 1 项 | ✅ 已全修（三状态标记 + 3 条守卫） | [2026-09-23-completion-popup-race.md](2026-09-23-completion-popup-race.md) |
| 2026-09-23 | 测试 mock 目标核对（22 处 / 15 个不同目标，分层重构后） | ✅ 通过（无需改动） | 0 阻断 / 0 缺陷 | ✅ 结论：无静默失效，`tests/` 无需改动 | [2026-09-23-test-mock-audit.md](2026-09-23-test-mock-audit.md) |
| 2026-09-24 | **PR #13 审查修复**（Gitee AI 审查，两轮触发） | ❌ 初评未通过 → ✅ 复评通过 | 2 阻断 / 4 改进（+1 附带发现） | ✅ 已全修（9/9），门禁实测全绿 | [2026-09-24-pr13-review.md](2026-09-24-pr13-review.md) |
| 2026-09-24 | **全量代码审查**（分支 `issues/appprotocol-refactoring`，54 commits / 132 files / +16655−4469） | ❌ 未通过（4 处可复现 Major 回归 M1–M4 + 2 处存量功能缺陷） | 0 Critical / 4 Major / 27 Minor / 12 Suggestion | 🟡 部分待修：42/43 已修，1 项 ⏸ 明确不修（Windows `os.replace`） | [2026-09-24-appprotocol-refactoring-review.md](2026-09-24-appprotocol-refactoring-review.md) |
| 2026-09-24 | 复审补充 `yate/logs.py`（外部审查工具 2 项） | ✅ 通过（均 Low） | 0 阻断 / 2 项 | ✅ 已全修（`warn()` stderr 为 None 静默丢弃；崩溃/trace 文件名加 pid） | [2026-09-24-logs-review.md](2026-09-24-logs-review.md) |
| 2026-09-25 | 复审补充（外部审查工具 2 项，`issues/nice-to-have-enh`） | 🟡 部分通过（1 误报 + 1 成立） | 0 阻断 / 2 项 | 🟡 部分待修：EOL 写回＝⛔ 误报已归档；`HighlightProbe.doc` 精确类型 🔧 未修 | [2026-09-25-recheck-supplement.md](2026-09-25-recheck-supplement.md) |
| 2026-09-26 | Python 3.12 升级迁移审查（分支 `py-upgrade-3.12`，4 commits） | ✅ 通过（无 critical / major） | 0 阻断 / 2 minor | 🟡 部分待修：1 已修（`harness.py` 导入扁平化）；Gitee Go 3.12 镜像 👀 待观察 | [2026-09-26-py312-upgrade.md](2026-09-26-py312-upgrade.md) |
| 2026-09-26 | readonly feature 评审（两轮：本地自查 + Gitee PR #24） | ⛔ PR 初评未通过 → ✅ 修复后通过 | 1 阻断 / 13 改进（6 自查 + 8 PR，去重 1） | ✅ 已全修（`8b6b1b4` / `d960a08` / `1f82fae` / `dd47be0`） | [2026-09-26-readonly-feature.md](2026-09-26-readonly-feature.md) |
| 2026-09-26 | **全项目评审报告**（master `faa6d75`，5 只读子代理 + 主代理复核） | ✅ 通过（总评 8.5/10，无致命 / 严重） | 0 阻断 / 6 建议级 | 🟡 部分待修：P1×3 / P2×2 / P3×1 待排期整改 | [2026-09-26-full-project-review.md](2026-09-26-full-project-review.md) |
| 2026-09-26 | Windows Terminal 键位失效（Gitee Issue IKH1RA） | 🟡 部分通过 | 0 阻断 / 1 项（含 3 个子根因） | 🟡 部分待修：`ctrl+p` / `ctrl+/` 已修；`ctrl+1` 需 Phase B，🔧 待启动 | [2026-09-26-wt-keybinding-ikh1ra.md](2026-09-26-wt-keybinding-ikh1ra.md) |
| 2026-09-27 | 日志/devtools 桥接评审（分支 `fix/logging-tracing-wt`，3 commits，2 名验证子代理交叉复核） | ✅ 通过（无致命 / 严重，全建议级） | 0 阻断 / 4 项 | ✅ 已全修（`44972c9` / `5d3399d` / `e754b27` / `905385f`） | [2026-09-27-devtools-bridge.md](2026-09-27-devtools-bridge.md) |
| 2026-09-27 | 日志/devtools 桥接评审（**PR #28** Gitee AI 审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 3 改进 | ✅ 已全修（`c13f407`，3 项建议全部采纳） | [2026-09-27-pr28-devtools-bridge.md](2026-09-27-pr28-devtools-bridge.md) |
| 2026-09-27 | 分支评审 `issues/keybinding-fix-wt`（keyproto + 分层 trace 日志） | ✅ 通过（总评 9/10，分支可合并质量） | 0 阻断 / 2 项（1 严重 + 1 建议） | ✅ 已全修（`b21ff37`）；遗留 PB5 三终端矩阵 🔧 人工复测 | [2026-09-27-keybinding-branch-review.md](2026-09-27-keybinding-branch-review.md) |
| 2026-09-27 | **Gitee PR #26** 评审（键位修复分支，AI 队友审查） | ⚠️ 无阻断项，可优化后合并 | 0 阻断 / 3 改进 | 🟡 部分待修：3 项已处置，1 条残余建议 👀 登记待评估 | [2026-09-27-pr26-keybinding.md](2026-09-27-pr26-keybinding.md) |
| 2026-09-27 | tcss 拆分实现评审（分支 `enh/tcss-enh`，Issue IKINFT） | ✅ 通过（总评 93/100） | 0 阻断 / 3 建议 | ✅ 已全修（全部当场修复于 `7e51d6b`） | [2026-09-27-tcss-split.md](2026-09-27-tcss-split.md) |
| 2026-09-27 | UI refine 评审（分支 `enh/ui-refine`，Issue IKINF3）+ **PR #29** AI 审查 | ❌ PR #29 功能性未通过（1 阻断）→ ✅ 已修复 | 1 阻断 / 3 改进（PR #29）+ 2 架构张力 | 🟡 部分待修：阻断与改进已修 + T1/T2 已治理；1 性能项 ⏸ 挂起、1 项 📌 记录保留 | [2026-09-27-ui-refine.md](2026-09-27-ui-refine.md) |

**状态图例**：✅ 已全修 ｜ 🟡 部分待修 ｜ ⬜ 已失效 ｜ ➖ 不适用

---

## 三、附录 A：原 `review.md` 章节 → 新文件映射表

| 原 `review.md` 章节（顶层 `##`） | 原行号区间 | 新文件 |
|---|---|---|
| `# yate Code Review`（文件标题） | 1 | 本文件（索引标题） |
| `## 历史问题` | 3–6 | `legacy-issues.md` |
| `## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27`（首次，分支评审） | 8–57 | `2026-09-27-devtools-bridge.md` |
| `## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27`（第二节，PR #28 AI 审查） | 61–97 | `2026-09-27-pr28-devtools-bridge.md` |
| `## Windows Terminal 键位失效（IKH1RA）— 2026-09-26` | 101–123 | `2026-09-26-wt-keybinding-ikh1ra.md` |
| `## 全量代码审查 — 2026-09-16`（含 Critical / Suggestion / Nice-to-have 三个子节） | 126–426 | `2026-09-16-full-review.md` |
| `## 全量代码审查 — 2026-09-23` | 428–448 | `2026-09-23-full-review.md` |
| `## 已失效条目` | 451–461 | `2026-09-23-invalidated-items.md` |
| `## 冒烟补场景调查 — 2026-09-23` | 464–483 | `2026-09-23-smoke-scenarios.md` |
| `## 补全弹窗按键放行修复的附带发现 — 2026-09-23` | 487–503 | `2026-09-23-completion-popup-race.md` |
| `## 测试 mock 目标核对 — 2026-09-23` | 507–532 | `2026-09-23-test-mock-audit.md` |
| `## PR #13 审查修复 — 2026-09-24` | 536–601 | `2026-09-24-pr13-review.md` |
| `## 全量代码审查 — 2026-09-24（issues/appprotocol-refactoring 分支）` | 605–984 | `2026-09-24-appprotocol-refactoring-review.md` |
| `## 复审补充（logs.py）— 2026-09-24` | 988–1010 | `2026-09-24-logs-review.md` |
| `## 复审补充 — 2026-09-25` | 1014–1058 | `2026-09-25-recheck-supplement.md` |
| `## Python 3.12 升级迁移审查 — 2026-09-26` | 1062–1123 | `2026-09-26-py312-upgrade.md` |
| `## readonly feature 评审（两轮）— 2026-09-26` | 1127–1235 | `2026-09-26-readonly-feature.md` |
| `## Gitee PR #26 评审（键位修复分支）— 2026-09-27` | 1237–1283 | `2026-09-27-pr26-keybinding.md` |

**原独立文件改名：**

| 原文件（`.trae/issues/`） | 新文件（`.trae/review/`） |
|---|---|
| `review_20260926.md` | `2026-09-26-full-project-review.md` |
| `review_20260927.md` | `2026-09-27-tcss-split.md` |
| `review_keybinding_20260927.md` | `2026-09-27-keybinding-branch-review.md` |
| `review_ui_refine_20260927.md` | `2026-09-27-ui-refine.md` |

---

## 四、附录 B：遗留问题（需主代理决策）

1. **`legacy-issues.md` 无日期**：原 `## 历史问题` 章节未记载任何日期（两条早期 UX 问题，
   早于 2026-09-16 首次全量审查），故未按 `YYYY-MM-DD-` 前缀命名。
   **（2026-09-29 决策：保持现状**——文件名保留 `legacy-issues.md` 不加日期前缀**）**。
2. ~~仓库内仍有 3 处指向旧路径 `.trae/issues/review.md` 的引用~~
   **（2026-09-29 已修复**：三处均已改为指向 `.trae/review/2026-09-24-pr13-review.md`，
   以 `tools/changelog/zh_overrides.json` 为源修改并重新生成全部四个 changelog 目标，
   `python -m tools.changelog check` 通过；同时按 d66ace9 惯例回填合并后新出现的
   8 个提交的中文摘要，缺译 112 → 104，剩余均为 v0.2.6 之前积压**）**：
   - `CHANGELOG.zh.md`（已重新生成）
   - `yate/resources/changelog.zh.md`（已重新生成）
   - `tools/changelog/zh_overrides.json`（源）
3. **同日同名章节**：原 `review.md` 中「日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27」
   出现两次且标题完全相同（前者为分支评审，后者为 PR #28 AI 审查），拆分时按内容区分为
   `-devtools-bridge` 与 `-pr28-devtools-bridge` 两个文件，未合并。
