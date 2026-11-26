# 2026-11-26 合并前 pr-review：IKY0E8 quickfix 导航

分支：`feature/enh-quickfix-nav`；评审时点 HEAD `e242d38c`；F1 修复 HEAD `2a67fe4b`（不写“当前 HEAD”）；基线 `master` merge-base `81170b8b`（`git diff master...HEAD`：11 笔提交 / 45 文件 / +3363−49）。
方案：[`../documents/quickfix-nav-pr-review-plan.md`](../documents/quickfix-nav-pr-review-plan.md)；产品主计划：[`../documents/quickfix-nav-plan.md`](../documents/quickfix-nav-plan.md)；上一轮闭环评审：[`2026-11-26-quickfix-nav.md`](2026-11-26-quickfix-nav.md)。

三名 `code-review-expert` 只读分域评审（A 功能/安全/算法性能、B 架构/类型/文档、C 测试/键位/冒烟/纪律）全部交付；主代理逐条回读复核，不引用子代理自述数字。`python-code-review` skill 在运行时未注册，评审员按 agent 剧本回退，未阻塞。

**Overall: REQUEST_CHANGES**（初评：6 MAJOR / 16 MINOR / 0 BLOCKER；硬门禁全绿但存在用户可见语义与事实链问题）

## 1. 维度小结

| 维度 | 结论 | 关键依据 |
|---|---|---|
| 功能正确性 | 4 MAJOR | reveal 失败通道失效、空批次跨 provider 误隐藏、长行折行滚动错位、references 失败路径先压栈 |
| 健壮性 / 错误边界 | 1 MAJOR 已并入功能项 | scratch buffer 诊断条目无可解析路径，并入 reveal 失败通道统一修 |
| 安全 | clean | 未新增 exec/eval/shell 注入面；诊断文本由 `Text.append` 渲染；路径来自 `uri_to_path` |
| 算法 / 性能 | 1 MINOR | 搜索结果每次全量重建 `Text`；2000 条量级毫秒级，非 hot-path 缺陷 |
| 可维护性 / 架构 | 8 MINOR | 重复回调别名、死注入参数、导入分组、docstring/编号漂移、R9 冻结清单未登记新 id |
| 测试 / 文档 / 纪律 | 2 MAJOR + 4 MINOR | 双语手册 `:diagnostics` 仍写输出屏；评审记录基线口径漂移至旧 merge-base |
| 硬门禁 | 全绿 | pyright 0 / pytest exit 0 / 架构 48 / 覆盖率 92.85% / 冒烟 129·1575 / changelog 0 / diffcheck 0 |

## 2. 保留的 MAJOR

### [MAJOR] `yate/flows/quickfix_flows.py:160-168` — reveal 的失败通道与真实装配不符
Problem: 注入的 `Editor.reveal_match` 在目标无法打开时静默 `return`（`yate/editor.py:568-573`），不抛 `OSError`；`QuickFixFlows.jump_to` 因此继续走成功路径，压入 jump-list、刷新并弹出 `jumped to ...`，而光标并未移动。上一轮新增的失败用例使用“抛 OSError 的桩”，给出虚假保障。
Fix: 让 reveal 返回布尔成败，真实装配返回 `False` 且不打开不存在的路径；flow 按返回值判定，失败时不 push / 不报成功。

### [MAJOR] `yate/flows/quickfix_flows.py:79-87` — 单一 provider 空批次误隐藏整体非空面板
Problem: `set_results` 以“本批次为空”调用 `_hide()`；若搜索结果仍在而某个 provider 返回空集，面板被关闭但内容仍在，用户误以为结果丢失。
Fix: 仅在 `self._list.entries` 整体为空时隐藏；其余情况只重绘。

### [MAJOR] `yate/editor_components/quickfix_panel.py:99-126` — 逻辑条目号与物理滚动行混用
Problem: 长诊断/命中行在窄视口折成多行后，`scroll_offset.y` 与 `size.height` 是物理行单位，`selected` 是逻辑条目号；选中项可能完全在屏幕外却不触发滚动，`scroll_to(y=selected)` 也落到错误位置。
Fix: 保证每条结果只占一个物理行（按内容宽度裁剪显示文本），使逻辑号与物理行一一对应；补窄视口长行回归用例。

### [MAJOR] `yate/flows/lsp_navigation_flows.py:497-503` — references 跳转在失败检查前压栈
Problem: `_jump_to_row` 先 `push_jump()` 再 `_open_path()`；`doc is None` 失败返回时 back 栈已多出一条从未离开的 origin，与 quickfix 路径“成功后才 push”的契约矛盾。
Fix: 先捕获 origin，`doc is None` 检查通过后再用显式位置 push。

### [MAJOR] `yate/resources/manual.en.md:309,1468-1469` / `manual.zh.md:283,1312` — 双语手册与实现相反
Problem: 手册仍称 `:diagnostics` 在 output screen / 输出屏列出诊断；实现已删除 `OutputScreen` 路径，改为底部 quickfix 面板。用户按手册预期将完全落空。
Fix: 两处双语同步改为“发布到底部 quickfix 面板，可用 `<alt-j>`/`<alt-k>` 遍历”，与 `lsp.{en,zh}.md` 新增小节一致。

### [MAJOR] `.trae/reviews/2026-11-26-quickfix-nav.md:3`、`.trae/reviews/README.md`、主计划 §10、本轮方案 §首部 — 评审事实链基线漂移
Problem: 上一轮记录以 `b97a695c` 为基线并称“8 笔提交”，而本轮真实 merge-base 已前移到 `81170b8b`（两者差 15 笔）；本轮方案写 HEAD `069408ad`，评审时点已是 `e242d38c`。索引权威因此无法回答“评了哪些提交”。
Fix: 统一口径：功能分支起点 `b97a695c` 保留历史叙述，评审范围明确为 `81170b8b..HEAD`；门禁表标注测量时点 HEAD；本方案回填最终 HEAD。

## 3. 保留的 MINOR

| # | 位置 | 问题与处置 |
|---|---|---|
| M1 | `quickfix_flows.py:80-81` | 搜索每次扫描都自动打开面板。属于计划中“新结果即呈现”的既定行为；无 sticky-close 需求，降为设计提示，登记不修。 |
| M2 | `session.py:236-237` | provider 切片收缩后绝对下标选中项漂移。主计划已明确“替换使旧选择失效”，属既定语义；与计划文字“first row”存在措辞漂移，登记文档一致性待办。 |
| M3 | `quickfix_panel.py:71-86` | `on_key` 的 up/down/enter/escape 从无 `focus()`，真实路径不可达；用户可见文档只承诺 `alt+j/k/q`，故不构成功能缺陷。登记为死路径清理待办。 |
| M4 | `quickfix_flows.py:25,29-33` | `RevealFn` 重复定义、`ShowFn/HideFn/RefreshFn` 三同签名别名；随 MAJOR 修复一并收敛。 |
| M5 | `lsp_sync.py:43,123` | `set_quickfix` 注入签名未入 `flows/__init__.py` 共享词表；随修复波收敛。 |
| M6 | `lsp_sync.py:41,56` | `push_overlay` 在移除 OutputScreen 后成为死注入参数；随修复波删除。 |
| M7 | `quickfix_panel.py:28-30` | 内部导入分组/字母序漂移；随修复波整理。 |
| M8 | `session.py:439` / `tests/test_architecture.py:4` | “future LSP goto-definition”与 `R1-R12` 编号过期；随修复波同步。 |
| M9 | `.trae/rules/architecture-boundaries.md:186` | R9 冻结 ID 清单未登记 `#quickfix-panel`；随修复波补登记。 |
| M10 | `quickfix_flows.py:103` | `hit_lines` 缺键时 label 静默为空；随修复波改为显式空态并补用例。 |
| M11 | `quickfix_flows.py:119-124,131-140` | `toggle()` 无调用方且空列表提示分支零覆盖；随修复波删除死方法并补空列表用例。 |
| M12 | `tools/smoke_test/scenarios/lsp_navigation.py:430-436` | SVG 断言用 `or` 且 `"references"` 弱匹配；随修复波收紧为双文件名与确定性前缀。 |
| M13 | `lsp_sync.py:142` | 非标准 severity 显示裸整数；随修复波改为 `unknown`。 |

## 4. 撤回 / 降级证据

- A-3 初判 MAJOR：反证为计划 AC5 明确要求新结果进入面板且保持可遍历，用户未要求 sticky-close；降为 M1。
- A-4 初判 MAJOR：反证为主计划 §4 明确选择“替换使旧选择失效”的确定性语义；降为 M2（仅措辞漂移）。
- A-6 初判 MAJOR：反证为用户文档只描述全局 `alt+j/k/q`，`on_key` 四键未在用户路径承诺；降为 M3。
- A-7 独立 MAJOR：并入 A-1 的统一修复（reveal 拒绝不存在的非已打开路径），不重复计数。
- A-12 初判 MAJOR：反证为 2000 行 `Text` 构建在毫秒级且面板隐藏时不绘制；降为性能提示，登记不修。
- B-10/11/12/13/14/15/16/17/18/19/20/21/22/23/24 与 C-03/07/09/10/11/13：逐条回读后有注册豁免、既有惯例或反证，删除，不进入 findings。

## 5. 门禁（评审时点，主代理亲跑，全部 exit 0）

| 命令 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors / 0 warnings / 0 informations |
| `pytest tests/ -q -n auto` | exit 0 |
| `pytest tests/test_architecture.py -q` | 48 passed |
| `pytest tests/ --cov=yate --cov-branch -n auto` | 4084 passed / 10 skipped；92.85% |
| `tools.smoke_test run --jobs 4` | 129/129 scenarios；1575/1575 checks |
| `tools.changelog check` | released 段最新，exit 0 |
| `git diff --check master...HEAD` | 无空白问题 |

## 6. Strengths

- L1 纯数据模型不持 widget/document/server 引用，`replace` 的原位切片插入经实测无错位。
- R11 先登记后 import、R13 主题自持、R15 滚动条双调用、六工厂契约与键位双表守卫均落地且由架构测试冻结。
- 失败 reveal 的负向用例结果态有效（旧实现下会红），jump-list 单点由逐位置断言而非仅计数保护。
- 三 provider 双发布、空态文案与搜索替换报告互不覆盖的交互有专门回归。

## 7. 回填区（修复波后填写）

- 迭代结论：
- 修复提交：
- 修复后门禁：
