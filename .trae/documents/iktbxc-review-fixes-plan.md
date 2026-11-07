# IKTBXC review fixes plan (iteration wave)

来源评审记录：[2026-11-07-iktbxc-naming-refactor.md](../reviews/2026-11-07-iktbxc-naming-refactor.md)
（code-review-expert 交付，0 blocker / **1 major** / 3 minor；评审者无写盘工具，
记录由主代理原样代落盘）。
来源方案：[iktbxc-plan.md](iktbxc-plan.md) 与
[iktbxc-plans/overview.md](iktbxc-plans/overview.md)。
无人值守会话：批准视为已通过，不询问；本计划为迭代波的唯一规范来源。

## 一、目标 / 非目标

目标：把评审的 1 major 归零，处置 3 minor，并按门禁纪律处理评审阶段出现的
冒烟时序 flake；迭代后由主代理亲跑全量收尾门禁。

非目标：

- 不改三波实现提交的产品行为、不重写历史提交（m1 仅登记）；
- 不动 `.trae/documents/**` 历史计划、`.trae/reviews/**` 历史记录、CHANGELOG；
- 不新增架构守卫用例（评审确认四次负向演练覆盖足够，m2 是规则说明问题而非漏登）；
- P2 命名项仍不在本轮范围。

## 二、处置表

| 编号 | 级别 | 处置 | 依据 |
|---|---|---|---|
| M1 | major | 删除 7 个一次性临时工具脚本（清单见 §三），删除前先落盘本计划作为记录；收尾汇报显式列出 | 脚本以 `write_bytes` 改写产品文件与架构测试，未跟踪、未忽略（`git check-ignore` exit 1），属交付卫生 |
| m1 | minor | 登记待办：三笔提交 body 为空，wave-1 未说明 docstring 重写；历史提交不重写，后续同类提交在 body 补一行 | `git-commit-message.md` 英文与 subject 规范已满足，项目历史普遍无 body |
| m2 | minor | 在 `architecture-boundaries.md` R4 附近补一句：根级 `cmdline_completions.py` 归 §一 L1、有意不入 `UI_FREE_FILES` | 消除「L1 根级文件名单」与 R4 UI-free 名单的有意分歧被下轮审计误判为漏登 |
| m3 | minor | §三.6 去掉重复的「根级 L1」前缀，层级归属只由 §一 L1 清单与 §二 表格承担 | 并列项 `format_report` / `mode_chip` / `fuzzy_match` 均无层级标注，两种写法并存 |
| flake | 门禁纪律 | 修 `tools/smoke_test/scenarios/stress.py:134-136`：回收 toggle 后改为「连续 3 轮 flag==before 且 sidebar 与 flag 对齐」的收敛谓词，再断言 `toggles_back` | 见 §四裁决：评审阶段 `--jobs 4` 首跑 1 失败，`--jobs 1` 串行复核亦复现一次，`--repeat 5 --jobs 4` 全绿；`task-orchestration.md` §二.7 要求 `-n 1` 复核**并修用例** |

## 三、M1 删除清单（删除前落盘记录）

以下 7 个文件由本任务创建、从未被 git 跟踪、未被 `.gitignore` 覆盖：

1. `.iktbxc_wave1.py` — wave-1 精确替换工具
2. `.iktbxc_wave2.py` — wave-2 精确替换工具
3. `.iktbxc_wave3.py` — wave-3 精确替换工具
4. `.iktbxc_wave3b.py` — wave-3 第 17 条措辞差异的续作工具
5. `.iktbxc_drill1.py` — 命名守卫负向演练
6. `.iktbxc_drill2.py` — R2 / R11 两个负向演练
7. `.iktbxc_drill3.py` — 层秩负向演练

删除验证：`git status --short` 必须为空（三笔实现提交 + 迭代波文档/代码提交全部落盘后），
`Test-Path .iktbxc_*.py` 为 False。
无人值守 §二.5 要求：删除未跟踪产物先落盘记录（本计划）并在收尾汇报显式列出。

## 四、flake 修复裁决与偏离记录

**事实**（评审实测）：`python -m tools.smoke_test run --jobs 4` 首跑
`120/121`、`1462/1463`，失败项 `stress_rapid_toggles / toggles_back`
（expected False actual True）；`--repeat 3 --jobs 1` 串行复核亦复现一次；
`--repeat 5 --jobs 4` 全绿；完整二次全绿 `121/121 · 1463/1463`。
本任务三波自己的 `--jobs 4` 两次均 `121/121 · 1463/1463`。

**裁决**：修用例，而不是登记为偶发或另案。虽然评审建议另立 issue（判定与本任务
三波无关、属既有测试卫生），`task-orchestration.md` §二.7 对「并行下出现时序
flake」要求 `-n 1` 复核**并修用例**；用户明确要求严格纪律，故按规则优先执行修复。
**偏离**：本修复会新增一个与命名重构无关的 `tools/smoke_test/scenarios/stress.py`
改动，超出 issue §五「diff 仅允许 git mv + import 行 / 路径字符串 / docstring /
规则文档 / 测试名」。修复单列一笔提交，不混入三笔实现提交，保持三波逐笔可回滚；
理由与实测依据在此显式登记。

**修法**：`stress.py:134-136` 当前只 `wait_until(flag == before)` 一次便立即读值，
而 `:113-115` 的注释已记录「the storm outruns the sidebar repaint」。改为带状态计数的
收敛谓词（连续 3 次 `wait_until` 轮询均满足 `flag == before` 且
`sidebar.display == flag` 才返回），让风暴中迟到的按键落地后重新收敛；断言不放宽，
仍为 `Check("toggles_back", before, app.editor.explorer_visible)`。
不使用固定 sleep（§4.7：`wait_until` 通过 `pilot.pause()` 让出事件循环，以谓词收敛为准）。

## 五、分步与验收命令

1. 落盘评审记录 + 本计划 + 评审索引 #59 登记（`.trae/reviews/README.md`）。
2. 执行 §三 的 7 个删除，验证 `git status --short`。
3. 规则文本 m2 / m3 两处编辑（`.trae/rules/architecture-boundaries.md`）。
4. stress.py flake 修复（单列一笔提交）。
5. 局部验收（全部 exit code 0）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.smoke_test run --scenario stress_rapid_toggles --repeat 5 --jobs 4
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
git grep -n -E "keyproto\.legacy|editor_components\.editor|flows\.cmdline_completions|keyproto/legacy|editor_components/editor|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
```

6. 主代理亲跑收尾全量门禁（六项，规则 §二.7）：pyright / 全量 pytest `-n auto` /
架构 / 覆盖率 `--cov-fail-under=75` / 冒烟 `--jobs 4` / `python -m yate --help`。
7. 回填 [iktbxc-plan.md](iktbxc-plan.md) §9 与
[iktbxc-plans/overview.md](iktbxc-plans/overview.md) §9，提交。

## 六、风险与回滚

| 风险 | 缓解 |
|---|---|
| 收敛谓词放宽了断言 | 断言仍是精确 `before`，只把「何时读」改为连续收敛；`--repeat 5 --jobs 4` + 完整冒烟双证 |
| 规则文本补充引入新漂移 | 只加说明句、去掉重复前缀，不动层秩清单与守卫集合；架构 37 用例复跑 |
| 删除临时脚本误删已跟踪产物 | `git status --short` 逐条核对，删除清单只含 7 个 `??` 文件 |
| 迭代波提交混入三波实现 | 单独提交；`git log --oneline` 逐笔核对 |

回滚：迭代波提交各自 `git revert`；三笔实现提交不受影响。

## 七、迭代结论（收尾回填）

待主代理亲跑门禁后填写真实数字、退出码、评审 major 归零结论与最终提交列表。
