# 合并前 PR 级预评审：2026-11-07 · `ref/naming-hygiene`

> `pr-review` skill 的 `review` 模式：AI 预评审 + 人工决策，本文不代替合并决定。
> 迭代方案：[naming-hygiene-pr-review-plan.md](../documents/naming-hygiene-pr-review-plan.md)；
> 首轮评审：[2026-11-07-iktbxc-naming-refactor.md](2026-11-07-iktbxc-naming-refactor.md)；
> 主方案：[iktbxc-plan.md](../documents/iktbxc-plan.md)。

- 范围：merge-base `3e92532` → 评审起始 PR HEAD `38a918b`（48 文件 / +1641 / −65）；
  master `d53d238` 领先 47 提交；worktree `yate-naming-hygiene`，分支 `ref/naming-hygiene`。
- 方法：3 个只读 `code-review-expert` 并行（A 功能/架构、B 文档/合并面、
  C 安全/性能/门禁范围）+ 主代理逐条回读复核 + 主代理亲跑六道硬门禁。
- 基线结论：A `APPROVE`（0 BLOCKER / 0 MAJOR / 1 MINOR）；
  B `BLOCKED`（1 / 2 / 4）；C `REQUEST_CHANGES`（0 / 1 / 3）。
- 主代理裁定后基线：**0 BLOCKER / 3 MAJOR / 9 MINOR**（裁定表见 §二）。
- 噪声过滤：diff 内无 `.venv/`、lock、二进制资产或纯重排 hunk，无需跳过项。

**Overall: APPROVE**

3 MAJOR 全部当轮闭环，MINOR 修 6 登记 3；修复后六道硬门禁全部 exit 0，
`git merge-tree` 冲突标记归零，工作区干净。

---

## 一、六维度结论

| 维度 | 结论 | 依据 |
|---|---|---|
| 功能与正确性 | 通过 | 三处 `git mv` 的 blob 比对：`view.py` 与 `cmdline_completions.py` 空 diff，`key_codec.py` 仅模块 docstring 前 7 行重写；无签名 / 类名 / widget id / 主题改动。迭代波的 import 重排与收敛常量经全量 pytest + 冒烟复跑 |
| 安全 | 通过 | 无新增 shell / 反序列化 / 路径拼接 / 凭据；三模块均无线程、锁、worker |
| 性能 | 通过 | 改名只换 import 路径，顶层模块数不变；`_NAMED_KEYS` 字典推导仍在 import 期一次构建；无循环内 I/O、无朴素 O(n²) 替代需求 |
| 可维护性 | 修复后通过 | 改名留下的 5 处 import 字母序回归已修；`stress.py` 魔法数字与单键 dict 已修；其余按 §三登记 |
| 架构边界 | 通过 | `ALLOWED_PROTOCOLS` / `UI_FROZEN_FILES` / `_LAYER_RANKS` 三处守卫同步并各有负向演练；根级 L1 rank 1 登记经 drill-3 证明承重；37 条架构用例全绿；无新增 `Protocol` / `TYPE_CHECKING` / `Any` / 禁用命名 |
| 硬门禁 | 通过 | 主代理亲跑，真实退出码见 §四 |

## 二、主代理逐条复核与裁定

| # | 发现 | 来源 | 最终裁定 | 处置 |
|---|---|---|---|---|
| F1 | 评审索引 #59 与 master #59/#60/#61 撞号，且散文增量段与 master 同一位置插入产生真冲突 | B BLOCKER / C MAJOR / A MINOR | 撞号与冲突属实（`git merge-tree` 1 对冲突标记）。**BLOCKER 降为 MAJOR**：Markdown 索引冲突既非安全漏洞、架构违规、红灯门禁，也非正常使用时崩溃，不符合 skill 的 BLOCKER 定义；但会让本分支评审条目在合并时被静默淘汰，属必须修的合并阻塞 | 本分支条目重排 #62 / #63；散文段移入编号分歧登记；冲突标记归零 |
| F2 | 新加文档 3 处盘符绝对路径（`iktbxc-plan.md:8`、`:275`、评审记录 `:122`） | B/C MAJOR | 属实；`doc-conventions.md` §五/§六 禁止，存量渐进迁移条款不豁免新增违规 | 改为可移植写法；PR 变更文件扫描 0 命中 |
| F3 | 评审记录范围 `44/+1139/−65` 标成 `3e92532..HEAD`、环境信息失真、import 排序结论不实 | B MAJOR | 数字正确（`3e92532..f3299a1` 实测恰为该值），`HEAD` 标签失真；§三「4 处改动全部合规」被机械复核推翻 | 范围钉到 `f3299a1`，注记当前 HEAD，补 §十一 事实订正，环境行脱敏 |
| F4 | `yate/editor.py:61` import 字母序回归 | A MINOR | 属实并**扩展到 5 处**：`yate/editor.py`、`yate/editor_dispatch.py`、`yate/flows/completion_flows.py`、`tests/test_app_mouse.py`、`tests/test_panes.py` | 全部重排；pyright + pytest + 冒烟复跑 |
| F5 | `stress.py` 收敛谓词：`wait_until` 返回值丢弃、魔法 `3`、单键 dict | C MINOR ×3 | 全部属实 | 修后两项；第一项按理由登记（§三） |
| F6 | 6 个未跟踪 PR-review 探针文件 `base_*.txt` | 主代理 | 属实，与首轮 M1 同类交付卫生问题 | 方案落盘后删除，`git status` 干净 |
| F7 | `git diff --check` 报 `iktbxc-plan.md:300` EOF 空行 | 主代理 | 属实 | 删除尾随空行，diffcheck 归 0 |
| F8 | master 新增 `feature/<...>-<task>`（parent `develop`）分支规范，本分支为 `ref/naming-hygiene` from `master@3e92532` | A/B MINOR | 属实；本分支早于该规则变更，且语义化名称由用户 2026-11-07 明确指定，再次改名会推翻用户指令 | 登记偏离，不改 |
| F9 | `iktbxc-*` 文档词根与语义化命名方向相反 | B MINOR | 属实；用户反馈只约束分支 / worktree 名，计划文档按 `<task>-plan.md` 以 issue id 作 task，改名会断 9 处互链 | 登记偏离，不改 |

审查员报告与本文冲突处的撤回说明：A 的 README 冲突从 MINOR 上调并入 F1
（MAJOR）；B 的 BLOCKER 按 skill 严重度定义降为 MAJOR；C 的 MAJOR 与 F1
合并为同一条，不重复计数；A 对 `editor_dispatch.py` 排序「合规」的正面结论
由主代理机械取证撤回（首轮评审记录 §三同款结论已在 §十一订正）。

## 三、问题清单（按严重等级）

### [MAJOR]

**[MAJOR] F1 `.trae/reviews/README.md:78-82`（本分支）/ `master:.trae/reviews/README.md:78/86/97` — 索引编号 #59 三方重复 + 真合并冲突**

Problem: 本分支把 IKTBXC 首轮评审登记为 #59，master 同期把
enew-args-lsp-attach 三轮评审登记为 #59/#60/#61；双方又在散文增量段的同一
位置各插一段。`git merge-tree 3e92532 master HEAD` 产出 1 对冲突标记
（`<<<<<<< .our` / `>>>>>>> .their`），合并时若按 master 侧解冲突，本分支条目
会被静默淘汰。

Fix: 本分支首轮评审重排为 #62、本次 pr-review 重排为 #63；删除与 master
撞位置的散文增量段，把两轮评审叙述并入表格 #62/#63 两行；在既有「编号分歧
登记」块引用中补 2026-11-07 条目。复核 `git merge-tree` → 0 冲突标记。

**[MAJOR] F2 `.trae/documents/iktbxc-plan.md:8`, `:275` / `.trae/reviews/2026-11-07-iktbxc-naming-refactor.md:122` — 新增盘符绝对路径**

Problem: 三处均为本 PR 新增，指向本机 `D:\Programming\...`，违反
`doc-conventions.md` §五（仓库内引用一律相对路径）与 §六（禁止暴露本机真实
路径）；「存量随下次修改迁移」不适用于新增内容。

Fix: 头信息改为 `.venv/Scripts/python.exe -c "import yate; print(yate.__file__)"`
自证沙箱，§9.7 改为 worktree 目录名，评审记录环境行改为
`worktree \`yate-naming-hygiene\``。PR 变更文件扫描 0 命中。

**[MAJOR] F3 `.trae/reviews/2026-11-07-iktbxc-naming-refactor.md:8`, `:76`, `:122` — 评审记录元信息与结论失真**

Problem: `3e92532..HEAD` 配 44 文件 / +1139 / −65，而该数字实测只等于
`3e92532..f3299a1`；当前 HEAD 已是 48 / +1641 / −65。§三 import 排序一行
断言「4 处改动全部合规」，其中 `editor_dispatch.py` 的论据「`v` > `t` 的
字母序判定成立」与 `terminal` 排在 `view` 之后的事实相反。

Fix: 范围标签钉到 `f3299a1` 并注记演进后的 HEAD；附录「十一、合并前
pr-review 的事实订正」逐条登记 4 项订正，不改写首轮发现本身
（`doc-conventions.md` §2.1：评审记录为只读事实文档）；5 处排序回归已修。

### [MINOR]（已修）

- **F4** 5 处 `view` import 留在旧 `editor` 位置 → 按 `python-coding-style.md`
  §1.3 组内字母序重排；`terminal.py` / `panes.py` 本就各自 import `view.py`，
  无新循环依赖，pyright 0 / 全量 pytest 0 / 冒烟 0。
- **F5 魔法数字** → 新增 `#: Consecutive aligned polls required ...` 注释与
  `_SETTLED_POLLS: int = 3`。
- **F5 单键 dict** → `nonlocal streak` + 整数计数，谓词语义不变。
- **F5 返回值** → 代码内注释说明有意不使用；**登记不修**：`wait_until` 仅在
  超时返回 `False`，紧随其后的 `Check("toggles_back", before, ...)` 已断言同一
  失败态；再加一个 `Check` 会抬高冻结的 `1463/1463` 冒烟基线且重复覆盖。
- **F6** 删除 6 个 `base_*.txt` 探针文件（删除清单先落盘于迭代方案 §1）。
- **F7** 删除 `iktbxc-plan.md` EOF 空行，`git diff --check` 归 0；顺带修掉
  README 表格中间的两处空行（原会截断 Markdown 表格）。
- **链接断链** 机械扫描 PR 变更 Markdown 的相对链接，发现
  `.trae/documents/iktbxc-plans/overview.md` 指向首轮评审记录少了一级
  `../`；改为 `../../reviews/...`，复核 `broken_links 0`。

### [MINOR]（登记不修，理由见 §二）

- **F8** master 新增 git-flow 分支规范与分支现状漂移。
- **F9** `iktbxc-*` 文档词根。
- 首轮评审 §八的三条观测项（R11 枚举与 `UI_FROZEN_FILES` 既有漂移、
  `key_codec.py` 首行 "legacy" 字样、包级 rename 全历史考古）与 P2-4 / P2-5
  另案，均不在本轮 PR 范围。

## 四、主代理亲跑硬门禁（真实退出码）

环境：worktree `yate-naming-hygiene`，解释器 `.venv/Scripts/python.exe`
（Python 3.13.2 / Textual 8.2.8 / rich 15.0.0 / Windows）。

| # | 命令 | 实测 | 退出码 |
|---|---|---|---|
| 1 | `python -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | **0** |
| 2 | `python -m pytest tests/ -q -n auto` | 进度条 100%，仅 `s` 跳过标记（本环境不打印 summary 行，以退出码为准） | **0** |
| 3 | `python -m pytest tests/test_architecture.py -q` | `37 dots` | **0** |
| 4 | `python -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | `TOTAL 19392/1092/6190/579 = 93%`；`Required test coverage of 75% reached. Total coverage: 92.88%`；`3395 passed, 10 skipped in 203.57s` | **0** |
| 5 | `python -m tools.smoke_test run --jobs 4` | `1463/1463 checks (100%)`，`121/121 scenarios passed  95.16s` | **0** |
| 6 | `python -m tools.changelog check` | `released changelog sections are up to date`；unreleased lag 与 missing-zh 为发布期刷新信息，非错误 | **0** |
| 补 1 | `python -m yate --help` | usage / options 正常输出 | **0** |
| 补 2 | `git diff --check 3e92532..HEAD` | 无空白错误 | **0** |
| 补 3 | 三旧路径残余 `git grep`（源码 / 测试 / tools / pack / rules / wikis / README 面） | 0 命中 | **1**（期望绿灯） |
| 补 4 | PR 变更文件盘符绝对路径扫描 | 0 命中 | **0** |
| 补 5 | 旧分支 / worktree 名 grep | 0 命中 | **1**（期望绿灯） |
| 补 6 | `git merge-tree 3e92532 master HEAD` | 冲突标记 0；`changed in both` 2 个文件（README 与层秩规则）均可自动合并 | **0** |
| 补 7 | `git status --short` | 空 | **0** |

迭代波局部验收另测：`--scenario stress_rapid_toggles --repeat 5 --jobs 4`
五次 `12/12`、exit 0；架构 37 dots、pyright 0 errors，均在代码改动后复跑。

## 五、合并面与范围核对

- master 相对 merge-base 变更 47 个文件；与本分支改动文件重叠仅
  `.trae/reviews/README.md`（已消除冲突）与
  `.trae/rules/architecture-boundaries.md`（双方改不同 hunk，可自动合并）。
- master 的 `.trae/rules/task-orchestration.md` 为单边变更，登记为 F8 偏离。
- master 新增 / 变更文件与三旧路径引用面交集为 0；三旧路径在源码面残余
  grep 0 命中。
- 三处 rename 的 `git log --follow` 追踪保留：R093 / R100 / R100。
- 分支全程**只提交、不推送**。

## 六、Strengths

1. 三笔实现提交严格保持「零运行时行为变化」：两处 blob 完全相同、一处仅
   docstring，且 `git mv` 的 rename 追踪逐笔可回滚。
2. 根级 L1 rank 裁决有据：`cmdline_completions.py` 直接消费 L1
   `registries` / `session`，放 `services/` L0 会产生未登记向上边；四次负向
   演练证明三个守卫集与层秩登记都承重。
3. 规则、守卫集合、wiki、双语 README、手册与冒烟场景同步面完整，旧路径在
   源码 / 测试 / tools / rules / wikis / README 面零命中。
4. 首轮评审的 smoke 时序 flake 按 §二.7 串行复核后修用例而非记为偶发；
   本轮再把收敛谓词的魔法数字与状态容器收紧，断言未放宽、冒烟基线未抬高。
5. 评审记录与修复方案互链，历史事实以「补记」方式订正而非静默改写，编号
   分歧显式登记，合并冲突在 PR 阶段清零。
