# yate Code Review — 历史问题（早期登记，无日期）

## 历史问题

- [x] 输入时候，屏幕会闪烁，影响输入体验，加入放抖动机制。
- [x] yate 输入一个不存在的文件名，进程会卡住无任何输出，希望和vim一样，直接进入enew新建一个bug。

## 已知设计权衡与守卫局限（2026-10-01 登记）

来源：语义能力注入 PR 的 AI 审查（2026-10-01 00:18 第四轮，无阻断项、3 个改进建议）。
三条均为方案文档已登记的权衡或有意设计，当前不修复；触发条件出现时再评估。

- [ ] `spawn` 动词签名擦除：`Callable[..., Worker[object]]` 的 `...` 使调用处关键字
  参数（`group=` / `exclusive=` / `exit_on_error=`）失去静态拼写校验，目前靠冒烟
  测试兜底（6 个流程模块，如 `yate/document_flows.py`）。若 `run_worker` 调用形态
  扩张或需更强静态保障，再评估更具体的 Callable 签名（注意 R2 禁新增 Protocol）。
- [ ] AST 守卫 `_stringified_imprecise` 仅匹配顶层精确形态（`"App[Any]"` /
  `"App[object]"`），不捕获嵌套字符串化注解（如 `"list[App[Any]]"`）；当前仓库无
  此形态，扫描面已由方案声明（变量 / 参数 / 返回值三处顶层）。
- [ ] 守卫 `test_flow_modules_hold_no_app_handle` 为非递归扫描
  （`YATE.glob("*.py")`），仅覆盖 `yate/` 顶层——L3 流程模块均居顶层，L2
  （`editor_view/*`）的向上依赖由 R3 守卫覆盖；模块布局调整时须同步复核扫描范围
  与该测试 docstring。

## pack wiki 进度刷新与 Ctrl+C 治理：审查轮问题（2026-10-06 登记）

> **已迁出**：本轮 skill 审查的发现与逐条证据按 `doc-conventions.md` §二登记在独立
> 评审记录 [2026-10-06-pack-wiki-progress-skill-review.md](2026-10-06-pack-wiki-progress-skill-review.md)，
> 修复方案与执行记录见
> [pack-wiki-progress-refresh-plan.md](../documents/pack-wiki-progress-refresh-plan.md)
> §6.8–§6.11。本节只保留跟踪指针与仍未处置的流程风险。

- **本轮跟踪指针**：R-01…R-20 的状态以
  [评审记录](2026-10-06-pack-wiki-progress-skill-review.md) §二/§三/§四 与
  方案的处置表为准（R-09/R-10/R-13 为"接受并附理由"，R-15 的退出延迟为遗留限制）。

### 流程风险（仍未处置）

- [ ] **R-11 · 修复分支落后 master** — `fix/pack-wiki-progress-refresh` 基于
  `d691bfb`，master 之后合入了 PR !57（smoke 测试，5000+ 行）。本分支改动集中在
  `tools/pack/wiki.py`、`tools/translate/cli.py`、三个测试文件与两份 README，与
  smoke 改动基本不重叠，但 **`.trae/reviews/README.md` 与 `README.md` 两边都改过**，
  合并顺序不当会产生冲突。状态：待用户决策（建议先合 PR !57，再 rebase 本分支）。
