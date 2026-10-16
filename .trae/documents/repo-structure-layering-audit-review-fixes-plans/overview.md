# repo-structure-layering-audit-review-fixes —— 子计划总纲

- 主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)（v3：干净切分）
- 来源：[`../../reviews/2026-10-17-repo-structure-layering-audit.md`](../../reviews/2026-10-17-repo-structure-layering-audit.md)
- 分支 / worktree：`enh/full-repo-audit` / `../yate-full-repo-audit`
- 日期：2026-10-17
- 唯一规范来源：本总纲 + 各子计划 + 主计划 + [`../../rules/`](../../rules/) 全 8 个规则文档。
  子代理执行时**以各自子计划为唯一规范来源**，不得凭常识增删。

## 一、目标（v3：层秩切分干净，且不违反规则）

| 编号 | 修复项 | 子计划 |
|---|---|---|
| Fix-F | S-1 代码切分：记法下沉 `yate/keymaps/keys.py`（L0），`base.py` 收敛 L1，`keyproto/legacy.py` 改指向 | **plan-f** |
| Fix-A | S-1 层秩登记（新切分）+ S-8 `dist_meta.py` + S-7 `theme.py` 例外 + S-4 `yxp.py` 归属 | plan-a |
| Fix-B | S-2 登记 L2→L3 扩展门面例外（切分后**唯一**的向上连线） | plan-a |
| Fix-C4 | S-8 `dist_meta.py` 入 UI-free 守卫面 | plan-b |
| Fix-D | 层秩向上连线守卫（白名单 2 条） | plan-b |
| Fix-C1 | S-6 `tests/README.md` 失效路径与覆盖表口径 | plan-c |
| Fix-C3 | S-4 门户 docstring（代码侧） | plan-d |
| Fix-D2 | S-11 wheel 资源取证（**已完成**） | plan-e |

**非目标**（另案）：S-3 `editor_view/` 子域化、S-5 `tools/pack` 改名、S-9 `editor.py` 拆分、
S-10 `tests/` 目录化、6 包导入环重构。

## 二、子计划索引与波次

| 波次 | 子计划 | 独占文件清单 | 执行者 |
|---|---|---|---|
| wave-1 | [plan-f keys-split](repo-structure-layering-audit-review-fixes-keys-split-plan-f.md) | `yate/keymaps/keys.py`(新)、`yate/keymaps/base.py`、`yate/keyproto/legacy.py` | plan-executor #1 |
| wave-1 | [plan-a rules](repo-structure-layering-audit-review-fixes-rules-plan-a.md) | `.trae/rules/architecture-boundaries.md` | plan-executor #2 |
| wave-2 | [plan-b guard](repo-structure-layering-audit-review-fixes-guard-plan-b.md) | `tests/test_architecture.py` | plan-executor #3 |
| wave-2 | [plan-c tests-readme](repo-structure-layering-audit-review-fixes-tests-readme-plan-c.md) | `tests/README.md` | plan-executor #4 |
| wave-2 | [plan-d services-init](repo-structure-layering-audit-review-fixes-services-init-plan-d.md) | `yate/services/__init__.py` | plan-executor #5 |
| wave-3 | [plan-e wheel-probe](repo-structure-layering-audit-review-fixes-wheel-probe-plan-e.md) | 无（已完成，结论见主计划 §7.3） | 主代理 |

**波次硬性依赖**：plan-b **必须在 plan-f 之后**——切分前 `yate/keyproto/legacy.py → yate.keymaps.base`
仍是向上连线，守卫会红。其余文件互不重叠。

## 三、跨子计划一致性契约（硬性）

1. **层秩切分（plan-f 落地后的定稿）**：

   | 路径 | 层秩 |
   |---|---|
   | `yate/keymaps/keys.py` | **L0**（键位记法：`SPECIAL_KEYS` / `KEY_ALIASES` / `parse_key` / `key_name`） |
   | `yate/keymaps/` 其余（`base.py` / `vim.py` / `vsc.py` / `registry.py` / `__init__.py`） | **L1** |

2. **守卫白名单**（plan-b 落盘内容必须与 plan-a 登记语句逐字一致）：

   ```
   editor_view/statusbar.py -> yate.services.extensions
   editor_view/statusbar.py -> yate.services.extensions.bridges
   ```

   实测口径：切分后 `keyproto/legacy.py → keys.py` 同层、`keymaps/base.py → yate.session` 同层，
   全仓向上连线**恰为上述 2 条**（均由 plan-b 的用例实测复核）。

3. **规则用例计数**：plan-b 落地后 `pytest tests/test_architecture.py -q` 必须 **32 passed**；
   plan-a 的 §六 计数与对照表按 32 回填。两处不一致 = 阻塞。
4. **`extensions/`**（随包插件示例）在层秩守卫中**跳过**；其门面纪律由 R14 守卫
   （`test_extension_machinery_hides_behind_facade`）覆盖。

## 四、统一验收（wave-3，主代理亲跑）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/ -q --cov --cov-fail-under=75
```

本批含产品代码与测试改动，**不适用** [`misc-rules.md`](../../rules/misc-rules.md) §三 的纯文档豁免。

## 五、风险与回滚

| 风险 | 缓解 / 回滚 |
|---|---|
| 记法符号引用点漏改 | `base.py` 保留记法再导出 → 既有引用零改动；仅 `legacy.py` 单行改指；全量 pytest 兜底 |
| `keys.py` 误带上层依赖 | 只搬记法块（`re` 是唯一 import）；层秩守卫 + pyright |
| 规则四处互引不同步（§一 L0/L1、§二 表、§三.5③、§六 计数） | plan-a 逐处锚点验收 + 命中数断言 |
| 守卫白名单与规则登记不一致 | §三.2 逐字契约 + 主代理收口比对 |
| 子代理零产出 / 方案变更 | 同回合探活；判死或方案变更即主代理接手并如实标注 |
| 回滚 | 每步单笔提交，`git revert <sha>` |

## 六、回填位

- 主计划 §7.4（门禁前后数字、向上连线实测条数）、§7.5（步骤-提交对照、负向演练输出、偏离记录）；
- 审计记录 §四 处置列（S-1/S-2/S-6/S-7/S-8 → 已修；S-4 → 规则+文档侧已修，代码结构侧登记；
  S-11 → 关闭）。
