# 2026-10-17 分支 `enh/full-repo-audit` 合入前 code review

- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit`）
- 范围：`git diff master...HEAD` 全部改动（26 文件，+2385/-202）——两轮审计产出的
  分层/结构治理与其计划文档
- 形态：**只读事实文档** —— 只记录发现与核对结论，不含修复排期、不含任何代码改动
  （doc-conventions §二.1）
- 交叉引用：同分支两轮审计记录
  [`2026-10-17-repo-structure-layering-audit.md`](2026-10-17-repo-structure-layering-audit.md)、
  [`2026-10-16-full-repo-audit.md`](2026-10-16-full-repo-audit.md)；
  修复方案 [`../documents/full-repo-audit-code-review-fixes-plan.md`](../documents/full-repo-audit-code-review-fixes-plan.md)
- **溯源声明**：本轮评审由 `code-review-expert` 子代理执行（2026-10-17），其报告**未落盘**
  （`.trae/reviews/` 内无对应记录）；本记录由主代理于同日在该分支上**重构取证**——
  下列每条发现均附 `文件:行号` 与可复现的只读命令/实测输出，未做任何代码改动。
  如与原始子代理报告条目有出入，以本记录的实测证据为准。

## 一、门禁口径（子代理报告值 + 主代理收尾复测）

| 门禁 | 报告值 | 收尾复跑值（主代理，2026-10-17） |
|---|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations | 0 / 0 / 0，exit 0 |
| `pytest tests/test_architecture.py -q` | 32 passed | 32 passed，exit 0 |
| `pytest tests/ -q` | 全绿 | 2480 passed, 9 skipped，exit 0 |
| `pytest tests/ -q --cov --cov-fail-under=75` | 91.92% | 91.94%，exit 0（≥75） |

按 `subagent-workflow.md` §三.2，成员回报数字一律需主代理独立复核；**取证阶段**记录报告值，
**修复收尾**由主代理全量复跑，四项与报告值一致（覆盖率 91.92% → 91.94%）。
修复处置归方案 `../documents/full-repo-audit-code-review-fixes-plan.md`（本记录为只读事实
文档，依 `doc-conventions.md` §二.1 不放修复排期）。

## 二、确认项（复核通过，不重报）

- `yate/keymaps/keys.py`（新增 L0 单文件）：零上层依赖，`keyproto/legacy.py` 作为
  L0 消费者取自它——层秩切分成立（对应审计记录 S-1 结论）。
- 全仓向上连线实测恰 **2 条**，均在 `tests/test_architecture.py`
  `UPWARD_EDGES_FROZEN` 内（`editor_view/statusbar.py` ×2）。

## 三、逐条发现

分级：`[MAJOR]`（规则口径缺口、结构不一致）/ `[MINOR]`（口径/文档漂移）/
`[NIT]`（整洁度）。**本轮无 BLOCKER。**

### 维度 A 规则文本自身一致性

- **[MAJOR] C-1 §一 硬性依赖连线图与 R14 已登记例外自相矛盾**
  - `.trae/rules/architecture-boundaries.md:47-48` 声明"实线箭头是**允许**的依赖方向，
    **全部严格向下**；图中**未画出的连线一律禁止**（含反向箭头与跨层跳跃）"。
  - 实测该图（`:52-94`，16 条实线边）**未画出** `editor_view/*`（EV）→
    `services/extensions/*`（EXTF）这条边；而：
    - `:210-214`（R14）明文登记"**L2→L3 已登记例外**：`editor_view/statusbar.py`
      取本门面公共名（`ExtensionLoader`）与冻结的 `.bridges`（`UiExtensionBridge`）…
      这是层秩切分后全仓**唯一**的向上连线，由 §六 的层秩守卫冻结"；
    - `:373-374`（R4 后附）亦记"`keymaps/*` 同时是 UI-free 面与该包按文件切分的
      L0/L1 混合面"。
  - 守卫侧实证：`tests/test_architecture.py` `UPWARD_EDGES_FROZEN` 恰 2 条，
    即 `editor_view/statusbar.py -> yate.services.extensions` 与
    `… -> yate.services.extensions.bridges`，`_LAYER_RANKS` 中
    `editor_view/` = 2、`services/extensions/` = 3 → 该图漏画的正是**唯一合法例外**。
  - 影响：图注（"未画出的一律禁止"）与 R14（登记了例外）互相否定；后续 L2 组件
    视图取 L3 服务时，图与条文给出相反指引。

- **[MINOR] C-6 §一 清单与层秩守卫 `_LAYER_RANKS` 口径漂移**
  - `tests/test_architecture.py` 的 `_LAYER_RANKS` docstring 自述
    "Layer rank of every ``yate/`` module, **mirroring the inventory in
    architecture-boundaries.md section 1**"，但：
    - `("__main__.py", 4)` 在表中为 L4（实测该文件存在，为入口 shim），
      而 `architecture-boundaries.md:16` 的 L4 行只列
      "`app.py`（YateApp） / `cli.py`（唯一入口）"，未列 `__main__.py`；
    - `yaterc.py` / `yaterc_options.py` 由 R4（`:105`）与 `UI_FREE_FILES`
      收录为 L0 守卫面，`_LAYER_RANKS` 因未列出而**默认落 L0**（正确），
      但 `:31-41` 的 L0 行同样未列这两个文件。
  - 影响：守卫文档声称"镜像 §一 清单"，清单却比守卫表少 3 个名字；
    S-8（`dist_meta.py`）已按同一模式补齐，本条为同类残留。

### 维度 B 文档与实现一致性

- **[MINOR] C-2 §六 R12 的 UI-free L0 清单漏 `dist_meta.py`**
  - `.trae/rules/architecture-boundaries.md:391-393`（R12 条目）列 UI-free L0 为
    "`keymaps/*` `services/*` `keyproto/*` `editor_sprites/*` `session.py`
    `registries.py` `config.py` `yaterc.py` `yaterc_options.py` `logs.py`"，
    **无 `dist_meta.py`**。
  - 但同文件 `:367`（R4）已列 `dist_meta.py`，`:41`（§一 L0 行）已于 2026-10-17
    审计补入，`tests/test_architecture.py` `UI_FREE_FILES` 亦含 `dist_meta.py`。
  - 影响：同一守卫面在 R4 / §一 / 守卫表三处一致，唯独 R12 条目漏列 ——
    违反 R4 §六 文本"R4 是 UI 耦合约束，与层秩无关"的同一清单口径。

- **[MINOR] C-3 `tests/README.md` 计数口径漂移**
  - `tests/README.md:13-17`："most modules have no same-named test file
    (2026-10-17 measurement: **92 of the 139** `yate/` modules)"。
  - 实测（本 worktree，2026-10-17）：
    
```powershell
    .venv\Scripts\python.exe -c "import pathlib; ps=list(pathlib.Path('yate').rglob('*.py')); print(len(ps))"
    ```
    
输出 `140` —— `yate/` 现为 **140** 个 `.py`（本轮新增 `keymaps/keys.py` 后
    由 139 增至 140），故 "139" 已过期；分母与分子（`92`）出自审计期的两个不同
    口径（审计记录 `2026-10-17-repo-structure-layering-audit.md:137` 原文为
    "139 模块中 92 个"），当前无法原样复现"92"。
  - 影响：README 作为唯一测试组织约定文档，计数不可复现即无法被后续审计核对。

### 维度 C 代码整洁度

- **[MINOR] C-4 emulator S/T 钳制上界与用例命名语义不符（钳到屏高，非区域高）**
  - `yate/editor_term/emulator.py:674-680`：
    `_scroll_region_up` / `_scroll_region_down` 内为 `min(count, self.rows)`；
    而 `self.rows` 是**屏幕高度**，滚动区域的真实高度是
    `self.scroll_bottom - self.scroll_top + 1`（`:122-123`、`:196-197` 定义，
    `:530` 由 DECSTBM 更新）。
  - 用例侧：`tests/test_terminal_emulator.py` 新增
    `test_scroll_commands_with_huge_count_clamp_to_the_region_height` 声称
    钳到 "region height"，但其构造（`_emu(cols=6, rows=4)` 未设 DECSTBM）
    下区域 == 全屏，`rows` 与区域高恰好相等，**无法区分两种上界**。
  - 影响：语义（应为区域高）与用例（宣称区域高、实际只覆盖全屏）均未锚定；
    窄区域（DECSTBM）下会多做 `count - 区域高` 次空转平移（`_scroll_up(1)`
    区域全空后为幂等空转）。

- **[NIT] C-5 `yate/keymaps/keys.py` 文件尾多余空行**
  - 实测：该文件以 3 个换行结尾（即 **2 个尾空行**），同包其它文件为单尾换行。

    ```powershell
    .venv\Scripts\python.exe -c "p='yate/keymaps/keys.py'; t=open(p,encoding='utf-8').read(); print(len(t)-len(t.rstrip(chr(10)))-1)"
    ```

    输出 `2`。

## 四、处置汇总

| 级别 | 编号 | 主题 | 目标文件 |
|---|---|---|---|
| MAJOR | C-1 | 依赖连线图漏画唯一已登记例外（L2→L3） | `.trae/rules/architecture-boundaries.md` |
| MINOR | C-2 | R12 的 UI-free L0 清单漏 `dist_meta.py` | 同上 |
| MINOR | C-3 | `tests/README.md` 模块计数过期 | `tests/README.md` |
| MINOR | C-4 | emulator S/T 钳制应钳区域高（用例背书不足） | `yate/editor_term/emulator.py` + 其测试 |
| NIT | C-5 | `keys.py` 尾空行 | `yate/keymaps/keys.py` |
| MINOR | C-6 | §一 清单相对 `_LAYER_RANKS` 少 3 个名字 | `.trae/rules/architecture-boundaries.md` |

## 五、复现口径（只读）

```powershell
git -C ../yate-full-repo-audit --no-pager diff master...HEAD --stat   # 26 文件 / +2385-202
.venv\Scripts\python.exe -c "import ast,pathlib"                       # 逐条见 §三 附带命令
```

无自动化探针入库；上述片段均可在 `../yate-full-repo-audit` 内直接执行
（misc-rules §二：一次性探针不入库）。
