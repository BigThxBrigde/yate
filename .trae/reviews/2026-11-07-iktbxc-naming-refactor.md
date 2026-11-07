# 评审记录：2026-11-07 · iktbxc 命名重构（key_codec / view / cmdline_completions 归位）

> 主代理代落盘：`code-review-expert` 本次运行无写盘工具，下列报告全文由其返回、
> 主代理原样登记（2026-11-07 无人值守会话）。报告 §九「未解决项 1」已由本次代写闭环；
> 其余未解决项保持原样登记，修复处置见 [iktbxc-review-fixes-plan.md](../documents/iktbxc-review-fixes-plan.md)。

- Worktree：`yate-naming-hygiene`，分支 `ref/naming-hygiene`，基线 `3e92532`（评审后按语义化命名要求重命名，仅同步元信息，评审结论与实测数字不变）
- 评审范围：`3e615a9`（wave-1 key_codec 更名）、`55aee7e`（wave-2 view 更名）、`f3299a1`（wave-3 cmdline_completions 归位），`3e92532..HEAD` 共 44 文件 / +1139 / −65
- 上下文：`.trae/documents/iktbxc-issue-notes.md`、`iktbxc-reference-inventory.md`、`iktbxc-plan.md`、`iktbxc-plans/*.md`
- 结论：**0 个 blocker，1 个 major，3 个 minor**

---

## 一、总体结论

issue 要求的「零运行时行为变化」成立：三处 `git mv` 的内容比对为空 diff，所以改名本身没有夹带逻辑。

| 比对 | 结果 |
|---|---|
| `git diff 3e92532:yate/keyproto/legacy.py HEAD:yate/keyproto/key_codec.py` | 仅模块 docstring 前 7 行重写（`keyproto/key_codec.py:1-12`），其余 0 变化 |
| `git diff 3e92532:yate/editor_components/editor.py HEAD:yate/editor_components/view.py` | 空 diff（0 字节输出） |
| `git diff 3e92532:yate/flows/cmdline_completions.py HEAD:yate/cmdline_completions.py` | 空 diff（0 字节输出） |

22 个 `git mv` 与引用点均属于 import 行、路径字符串、docstring 和规则文档，没有签名、类名、widget id 或主题改动（`yate/cmdline_completions.py` 内 `tcss|theme\.|DEFAULT_CSS|id=` 零命中；`view.py` 内容逐字节等同旧 `editor.py`，所以 `DEFAULT_CSS = load_tcss(...)` 与全部 widget id 必然不变）。

---

## 二、问题清单（按严重等级）

### [major]

**M1 — 已交付提交把库外临时工具脚本留在工作区未跟踪：`.iktbxc_wave1.py` / `.iktbxc_wave2.py` / `.iktbxc_wave3.py` / `.iktbxc_wave3b.py` / `.iktbxc_drill1.py` / `.iktbxc_drill2.py` / `.iktbxc_drill3.py`（共 7 个文件、601 行）**

- 证据：`git status --porcelain` 输出 7 条 `??` 记录；`git check-ignore -v .iktbxc_drill1.py` 退出码 1（即**未**被 `.gitignore` 覆盖）；三个提交已全部产生（`git log --oneline -8` 顶部为 `f3299a1`）。
- 性质：这是交付物卫生问题，不会导致运行时崩溃。这批脚本以**写入模式**改写产品文件：`.iktbxc_drill2.py` 第 22-26 行对 `tests/test_architecture.py` 执行 `TARGET.write_bytes(...)`，`.iktbxc_drill3.py` 第 37-56 行执行同样的写入操作，`.iktbxc_drill1.py` 第 45-51 行对 `yate/keyproto/key_codec.py` 执行 `write_bytes`。留在工作区的这些脚本一旦被误运行，会产生改动 `tests/test_architecture.py` 和 `yate/keyproto/key_codec.py` 的副作用，而且它们未跟踪、未文档化，无法从提交历史辨别。
- 定级依据：issue §「Notes collected」与 plan §8 只约定 worktree 沙箱隔离，没有约定临时脚本的去留；这也违反 plan §6「每个 drill 结束后 `git status --short` 对相关文件干净」的精神，但未触及产品源码正确性，故为 major 而非 blocker。
- 修复建议：删除这 7 个 `.iktbxc_*.py`（或在提交前重命名并移入 `tools/` 并登记），并且在 plan §8 的偏差记录中补一句「drill 工具为一次性脚本，收尾删除」。

### [minor]

**m1 — wave-1 提交信息没有体现「同时重写模块 docstring」，见 `yate/keyproto/key_codec.py:1-12`**

- 证据：`git --no-pager show --stat 3e615a9` 显示 `yate/keyproto/{legacy.py => key_codec.py} | 9 +++++++--`（7 行 docstring 实际重写），而 subject 为 `refactor(keyproto): rename legacy key codec to key_codec`，消息体为空（`git log --format="%s%n%b"` 三个提交 body 全空）。
- 规则：`.trae/rules/git-commit-message.md` 第 1、2 条要求主题与消息体全部英文并使用模板；英文已满足，模板块存在但为空。P0-1 的核心诉求之一就是「重写模块 docstring 首行」，这一点未在提交信息里说明。
- 修复建议：后续同类提交在 body 里加一行 `Docstring rewritten: "legacy" now names the terminal key-name system, not a deprecated module.`。历史提交不必重写，记录即可。

**m2 — 规则/测试守卫的「L1 根级模块」这一新层级事实，没有可执行守卫用例**

- 证据：`.trae/rules/architecture-boundaries.md:34-36` 新增 L1 条目，`tests/test_architecture.py:156-158` 新增 `("cmdline_completions.py", 1)`；但 `UI_FREE_FILES`（`tests/test_architecture.py:186-193`）仍只有 `session.py` / `registries.py` / `config.py` / `yaterc.py` / `yaterc_options.py` / `dist_meta.py`，没有新模块。
- 判断：这一项现在**不**是守卫漏登。`yate/cmdline_completions.py` 与那些 UI-free 文件不同，它不 import Textual，但也没有「UI-free」声明义务，并且 `test_no_unregistered_upward_imports` + `_LAYER_RANKS` 已覆盖其层级方向。定级 minor，属于规则清单完整性：R4 的 UI-free 名单与 L1 根级文件名单现在是有意分歧的，规则文本未说明该分歧。
- 修复建议：在 `architecture-boundaries.md` R4 附近加一句「`cmdline_completions.py` 虽无 Textual 依赖，但按 §一 L1 归类，不入 `UI_FREE_FILES`」，避免下一轮审计把它当漏登再提一次。

**m3 — 规则 §三.6 纯计算清单未随归位统一措辞，仍与 §二 表格的表述不完全对齐**

- 证据：`.trae/rules/architecture-boundaries.md:299` 为「纯计算（根级 L1 `cmdline_completions` / `format_report` / `mode_chip` / `fuzzy_match`）」，而 `:270` 表格写的是「把单一流程独立成模块（`flows/completion_flows.py`、根级 L1 `cmdline_completions.py`、`diagnostics.py`）」。同类模块 `format_report` / `mode_chip` / `fuzzy_match` 没有标注层级，读者仍无法从 §三.6 判断它们的层秩。
- 修复建议：§三.6 只保留一处「根级 L1」标注，或对 `format_report` 等同样标注归属，避免两种写法并存。

---

## 三、逐项核验结论（任务指定的重点检查）

| 检查项 | 结论 | 证据 |
|---|---|---|
| 三波是否夹带行为/签名/类名/widget id/主题改动 | **无** | 三次 `git diff <old>:<path> HEAD:<new>` 均为空或仅 docstring；`view.py` 与 `cmdline_completions.py` 逐字节等同 |
| `_LAYER_RANKS` 前缀匹配顺序是否安全 | **安全** | `_layer_rank()` 用 `rel.startswith(prefix)` 按顺序返回首个命中（`tests/test_architecture.py:523-528`）；新增条目 `"cmdline_completions.py"` 不可能遮蔽 `"commands.py"` / `"editor.py"`，因为它不是它们的前缀（`"cmdline_completions.py".startswith("commands.py")` 为 False）；同理 `"editor.py"`（L3）不会误命中 `"editor_compose.py"`，因为它也不以它为前缀 |
| `test_no_unregistered_upward_imports` 是否覆盖归位模块 | **覆盖** | `_yate_files()` 为 `YATE.rglob("*.py")`（`:502-507`），根级新路径自动在列 |
| `test_flow_modules_hold_no_app_handle` 是否覆盖 | **覆盖** | `scan_roots = [YATE.glob("*.py"), (YATE/"flows").glob("*.py")]`（`:1318`），根级 `yate/cmdline_completions.py` 在 `YATE.glob("*.py")` 中 |
| `test_keymaps_services_and_models_stay_ui_free` | 不覆盖且**无需**覆盖 | 新的模块不在 `UI_FREE_PACKAGES` / `UI_FREE_FILES`（`:177-193`）；该模块也确实不 import `editor_components`（`yate/cmdline_completions.py:12-14` 仅 registries / services.workspace / session） |
| `test_no_relative_imports` | **覆盖** | `_python_files()` = `YATE` + `tests` + `tools` rglob（`:481-489`），根级新模块在 YATE rglob 内 |
| `test_source_files_within_size_threshold` | **覆盖** | `_source_files()` = `YATE` + `tools` rglob（`:884-896`）；`yate/cmdline_completions.py` 52 行，远低于 800 |
| `test_comments_and_docstrings_stay_ascii` | **覆盖** | 同名函数 `:1432` 遍历 `[*_python_files(), *_template_files()]`；`tools/smoke_test/scenarios/guards.py:200` 的新 ASCII 路径串已改对 |
| 旧守卫集是否留下陈旧项（ALLOWED_PROTOCOLS / UI_FROZEN_FILES / UI_FREE_FILES / SIZE_EXEMPT_FILES / PRINT_EXEMPT_SITES） | **未发现不匹配** | `ALLOWED_PROTOCOLS` 键已改 `"editor_components/view.py"`（`:130`）；`UI_FROZEN_FILES` 两处值已改 `"yate.editor_components.view"`（`:216`、`:228`），且**没有** `flows/cmdline_completions.py` 键（`:198-260` 逐条核对 10 个键均为 `*_flows.py` / `lsp_sync.py`）；`SIZE_EXEMPT_FILES` / `PRINT_EXEMPT_SITES`（`:474-478`）三旧路径零引用；没有新增无效键 |
| 规则文档同步完整性 | **完整** | `.trae/rules/architecture-boundaries.md` §一 L3（`:25` 移除）/ L0（`:47`）、R2（`:113`）、R11 枚举与注（`:133`、`:142-144`）、§二 表（`:270`）、§三.6（`:299`）、§六 R11 守卫面（`:457`）逐处核对，`git grep "cmdline_completions"` 仅剩 4 处新写法的命中，无旧路径 |
| wiki 同步 | **完整** | `.trae/wikis/yate-architecture.md:151-152`（flows 行拆出根级 L1 行）、`:157`、`:168`、`:185`、`:195` 均为新名；`:23` Mermaid FLOWS 节点已去掉 `+ lsp_sync/cmdline_completions` |
| README 双语「无需改动」论证是否成立 | **成立** | 基线 `git show 3e92532:README.md` / `README.zh.md` 第 272 / 290 行本来就是裸文件名 `cmdline_completions.py`，位于 `yate/` 根级树（`README.md:272`、`README.zh.md:290`）；移动后该行**才**变准确，改动前反而错。`git grep` 对两 README 在三旧路径上均为 0 命中（`git grep ... -- README.md README.zh.md` 退出码 1） |
| import 排序（`python-coding-style.md` §1.3「每组内按字母序」） | 4 处改动全部合规 | `yate/editor_compose.py:23`（`yate.cmdline_completions` 在 `yate.editor_components.*` 之前）；`tests/test_cmdline_completions.py:19`（`yate.cmdline_completions` 在 `yate.commands` 之前，且旧行从 `yate.flows.cmdline_completions` 位置移走）；`tests/test_app_find.py:18`（`yate.app` < `yate.cmdline_completions` < `yate.keymaps.vim`）；`yate/editor_dispatch.py:19-23`（`editor_components.view` 在 `editor_components.terminal` 前，`keyproto.key_codec` 在 `keymaps.base` 后，`v` > `t` 的字母序判定成立） |
| ASCII 注释 / docstring 质量 | 合规 | 新增 docstring `yate/keyproto/key_codec.py:1-12` 为英文多段（摘要 + 空行 + 详述，符合 `python-coding-style.md` §2.1/§2.2），首行说明「legacy 指终端键名体系，不是废弃模块」，正是 P0-1 的诉求；`pytest tests/` 中 `test_comments_and_docstrings_stay_ascii` 绿 |
| `git mv` rename 跟踪 | 三处均保留 | `git log --follow -- yate/keyproto/key_codec.py` 追溯到 `1db6175`/`5cd97d1`；`-- yate/editor_components/view.py` 追溯到 `ef1d964` Initial commit；`-- yate/cmdline_completions.py` 追溯到 `9fa5ac8`。三次 `--stat` 均显示 `{old => new}` 形式 |
| 豁免清单是否正当 | **正当** | `.trae/documents/**`：`iktbxc-reference-inventory.md:11` 明记 171 行为历史计划（issue 明示不回头改）；`.trae/reviews/**`：`doc-conventions.md:45`「评审记录是只读事实文档」；`CHANGELOG*` / `zh_overrides.json`：`iktbxc-reference-inventory.md:18-19` 实测 **0** 命中，豁免是空转（无害）。豁免之外扫描真实结果见下 |
| 四次负面演练覆盖面是否足够 | 充分（附一处建议） | 见 §四 |

---

## 四、四次负面演练的覆盖充分性

| 演练 | 目标守卫 | 覆盖扫描路径 | 结论 |
|---|---|---|---|
| 1（naming） | `test_no_banned_identifier_names` | `_yate_files()` → `keyproto/key_codec.py` | 证明 wave-1 新路径仍在 rglob 扫描面内 |
| 2a（`ALLOWED_PROTOCOLS` 键） | `test_no_new_protocols` | `_yate_files()` + 路径键 | 证明 `view.py` 键是承重的 |
| 2b（`UI_FROZEN_FILES` 值） | `test_collaborators_keep_widget_coupling_frozen` | 模块字符串白名单 | 证明两处值更新是承重的 |
| 3（`_LAYER_RANKS` 条目） | `test_no_unregistered_upward_imports` | 根级 rglob + 层秩 | 证明 rank-1 登记是承重的（`.iktbxc_drill3.py:62-70` 断言两条边 `-> yate.registries` / `-> yate.session`） |

**覆盖面评估**：四次演练覆盖了 wave-1 与 wave-2 的全部「路径变更导致守卫失聪」风险点，以及 wave-3 的层秩风险点，**足够**。wave-3 另外两个扫描面（`test_flow_modules_hold_no_app_handle` 的 `YATE.glob("*.py")`、`test_no_relative_imports` 的 `_python_files()`）没有被单独演练，但这两者的扫描根是**目录级 rglob/glob**，与演练 1（同样目录级 rglob）等价，无需重复演练。建议（非阻塞）：若下一轮再加根级模块，为 `test_flow_modules_hold_no_app_handle` 补一个「根级模块持有 `self.app` → 必须报红」的守卫用例，因为该断言目前只对 `yate/flows/*.py` 有过历史回归，根级分支从未被验证。

---

## 五、残余 grep 实测

```
git grep -n -E "keyproto\.legacy|editor_components\.editor|flows\.cmdline_completions|keyproto/legacy|editor_components/editor|flows/cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md
→ 无输出，exit code 1（期望的绿灯信号，即零命中）
```

补充口径（把豁免面也纳入，验证「不回头改」之外确实没有漏删）：

```
git grep -n -E "keyproto[.]legacy|editor_components[.]editor|flows[.]cmdline_completions" -- yate tests tools pack pyproject.toml .trae/rules .trae/wikis README.md README.zh.md CHANGELOG.md CHANGELOG.zh.md tools/changelog/zh_overrides.json
→ exit code 1（0 命中）
```

```
同正则加 .trae/documents .trae/reviews
→ exit code 0，全部命中都落在豁免面：.trae/documents/**（历史计划，含本任务 plan/notes 引用旧路径作为「旧→新」对照）与 .trae/reviews/2026-10-03-python-code-review.md:167 一处历史事实记录
```

结论：豁免清单**只**覆盖了 issue 明示不回头改的历史文档，产品源码 / 测试 / 工具 / 打包 / 规则 / wiki / README 全部 0 命中。

---

## 六、实测命令与退出码（本次评审真实执行）

环境：`d:/Programming/yate-naming-hygiene`，解释器 `.venv/Scripts/python.exe`（Python 3.13.2 / Textual 8.2.8 / rich 15.0.0 / Windows；评审阶段为重命名前的 worktree，重命名后于新 worktree 复跑门禁，见主计划 §9.7）。

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/ pack/` | `0 errors, 0 warnings, 0 informations` | **0** |
| `python -m pytest tests/ -q -n auto` | 全绿（进度条到 100%，仅 `s` 跳过标记；本环境不打印 summary 行，以退出码为准） | **0** |
| `python -m pytest tests/test_architecture.py -q` | `37 passed`（`--co` 报 `tests/test_architecture.py: 37`），100% | **0** |
| `python -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75`（`--cov-report=term`，输出落 `.review_cov.log`） | `TOTAL 19392 stmts / 1104 miss / 6190 branch / 577 partial / 93%`；`Required test coverage of 75% reached. Total coverage: 92.81%`；`3395 passed, 10 skipped in 174.74s` | **0** |
| 其中三个被移动/改名模块的覆盖 | `yate/cmdline_completions.py 21 0 8 0 100%`；`yate/editor_components/view.py 334 13 114 10 94% 265, 300, 333, 349, 387, 410->412, 499->501, 553-558, 591, 595, 597`；`yate/keyproto/key_codec.py 52 3 36 3 93% 124, 142, 145` | — |
| `python -m tools.smoke_test run --jobs 4`（第 1 次） | `1462/1463 checks`，`120/121 scenarios`，失败项 `stress_rapid_toggles` / `toggles_back` expected False actual True | **1** |
| `python -m tools.smoke_test run --scenario stress_rapid_toggles --repeat 3 --jobs 1`（串行复核） | 先一次 11/12（复现），再 `1/1 scenarios passed  12/12` | 1 → 0 |
| `python -m tools.smoke_test run --scenario stress_rapid_toggles --repeat 5 --jobs 4` | `12/12`，`1/1 passed` | **0** |
| `python -m tools.smoke_test run --jobs 4`（第 2 次，完整） | `1463/1463 checks (100%)`，`121/121 scenarios passed  81.47s` | **0** |
| `python -m yate --help` | 完整 usage 与 options 列表正常输出 | **0** |

**关于 smoke 失败的处理记录（按要求用 `-n 1` / `--jobs 1` 复核而非记成偶发）**：`stress_rapid_toggles` 的 `toggles_back` 在 `--jobs 4` 下首跑失败、二次全绿，**串行 `--jobs 1` 亦复现一次失败**，所以它**不是**纯并行负载下的假象，而是一个负载敏感的时序断言。定位：`tools/smoke_test/scenarios/stress.py:134-136` —— 先 `await pilot.press("ctrl+b")`，然后 `wait_until(... explorer_visible == before)`，再立刻断言 `toggles_back`（无 `wait_until` 包裹的二次读取）。`:131-132` 的前一个 toggle 有 `wait_until`，`:134-136` 的回收 toggle 只等 flag 收敛、**不等 sidebar 重绘**，而 `:113-115` 的注释本身就记录了「the storm outruns the sidebar repaint (one pause is not enough under a parallel full run)」。这是既有测试卫生问题，**与本 issue 三个提交无关**（本 issue 未改 `stress.py`，且改动集中在 `keyproto` / `editor_components.view` / 根级补全，均不在 explorer 重绘路径上）。建议另立 issue：`:134` 之后同样用 `wait_until(pilot, lambda: sidebar.display == app.editor.explorer_visible)` 再读值（与 `:116-120` 同款收敛规则），而不是把断言放宽。

---

## 七、强制自我批判（逐条结论登记）

**M1（临时脚本未清理）**
- 反证：重新 `git status --porcelain` → 7 条 `??` 真实存在；`git check-ignore -v` 退出码 1，确认未被忽略；`git --no-pager log --oneline -8` 三个提交已在 HEAD。证据成立。
- 上下文反推：`.trae/documents/iktbxc-plan.md:138-141` 只要求「每个 drill 后 `git status --short` 对该文件干净」，未要求删除脚本；但 issue §五 non-goals 与 plan §2 的「diff 只含 mv + 引用行」指向的交付物应当干净。没有规则明确豁免临时脚本留存，所以成立。
- 等级复核：初判 `[minor]`，复核后**升为 `[major]`**——理由是这些脚本含 `write_bytes` 到产品文件与架构测试的写入操作，属于「对冻结守卫面的潜在副作用 + 未跟踪不可追溯」，量级超出风格/可读性问题。
- **状态：确认保留（升级为 major）**

**m1（wave-1 提交 body 为空）**
- 反证：`git log --format="%H%n%s%n%b---" -3` 三个 body 均为空；`git --no-pager show --stat 3e615a9` 确认 codec 文件 `9 +++++++--` 含 docstring 重写。证据成立。
- 上下文反推：`git-commit-message.md` 第 2 条「使用 conversation 模板，生成提交信息」——项目历史提交普遍无 body（`git log --oneline` 全部单行），所以「必须写 body」并非项目既有硬实践；但第 1、3-7 条是硬约束且均已满足。因此**不得**升级为 major。
- 等级复核：初判 `[minor]`，维持。
- **状态：确认保留**

**m2（L1 根级模块未入 UI_FREE_FILES）**
- 反证：初判时我怀疑这是「守卫漏登」。回代码复核：`yate/cmdline_completions.py:12-14` 无 `editor_components` 导入，`test_keymaps_services_and_models_stay_ui_free` 对该文件没有任何要求；`UI_FREE_FILES` 的语义是「L0 纯逻辑单文件」，而本模块排 rank 1。**上下文推翻了「漏登」定性**。
- 降级处理：从「守卫漏登」降为「规则清单完整性（R4 名单与 §一 L1 名单的有意分歧未写说明）」。
- **状态：降级保留（minor）**

**m3（§三.6 措辞不齐）**
- 反证：`architecture-boundaries.md:299` 与 `:270` 两处表述确实不同；但两者**不矛盾**（都写 `cmdline_completions`，都标注根级 L1）。是否构成缺陷？按「不做无谓的风格挑剔」，纯措辞重复接近噪音。
- 等级复核：初判 `[minor]`，维持但降为最低优先级；理由保留是因为 §三.6 的并列项 `format_report` / `mode_chip` / `fuzzy_match` 无层级标注，会诱导后续审计重复提问（本轮评审就被要求核对这一点）。
- **状态：确认保留（minor，最低优先级）**

**漏报自查（反向扫六维度）**
- 正确性：三处 mv 内容比对为空 → 无逻辑变化；无 off-by-one / None / 可变默认参数引入。**无新增。**
- 安全：无新 shell / 反序列化 / 路径拼接；`picker`/`subprocess` 面未动。**无新增。**
- 性能：`yate/editor_compose.py` 的 import 从 `yate.flows.cmdline_completions` 变为 `yate.cmdline_completions`，顶层模块数不变、无新增惰性导入或循环；`_NAMED_KEYS` 字典推导仍在 import 期一次构建（与旧 `legacy.py` 完全一致）。**无新增。**
- 并发安全：三模块均无线程/锁/worker；`view.py` 内容逐字节相同。**无新增。**
- 异常处理：`cmdline_completions` 与 `key_codec` 内容未变，无裸 except / 吞异常引入。**无新增。**
- 类型：pyright `0 errors, 0 warnings`；`_LAYER_RANKS` 新增条目为 `tuple[tuple[str, int], ...]` 合法元素；无新 `Protocol` / `TYPE_CHECKING`（`test_no_new_protocols` / `test_no_type_checking` 绿）。**无新增。**
- 测试覆盖：三个被移动模块 100% / 94% / 93%，无「新增代码无测试」问题（本任务零新逻辑）。**无新增。**
- 额外补扫：`git grep -E "\beditor\.py\b|\bcompletion\.py\b" -- yate/editor_components/* yate/editor_compose.py` 仅命中指代 L3 `yate/editor.py` 的既有注释（`yate/editor_components/welcome.py:19`、`yate/editor_compose.py:9/382-384`），语义正确、无需改动——**定性为不成立的疑似项，已删除**。
- 额外补扫：`yate/editor_components/__init__.py:5,26`、`completion.py:4`、`highlighting.py:3`、`welcome.py:3`、`panes.py:24,40`、`terminal.py:40`、`mouse_flows.py:3,19`、`completion_flows.py:24`、`session.py:272`、`resources/editor-view.tcss:2` 共 14 处旧引用全部已改为新名（与 `iktbxc-reference-inventory.md:49-54` 的 14+1 条清单逐条对照），**零遗漏**。
- 额外补扫：`keyproto/__init__.py:13`、`keyproto/key_codec.py:1-7` 中残留的「legacy」字样（`:1` 首行、`:24`、`:35`、`:86`、`__init__.py:12`）经核对**均指终端键名体系 / legacy C0 字节**，语义正确，不是路径残留——**定性为不成立的疑似项，已删除**。

---

## 八、观测项（不构成问题，仅记录）

1. `tests/test_architecture.py:25-27` 的模块 docstring 已从 R11 列表移除 `flows/cmdline_completions.py`，但该列表**原本就不含** `flows/document_flows.py` / `window_flows.py` / `extension_flows.py` / `whichkey_flows.py` / `file_manager_flows.py`（`UI_FROZEN_FILES:198-260` 实际有 10 个键）。docstring 的 R11 枚举与 `UI_FROZEN_FILES` 的键集长期不同步——既有问题，本次未引入。可另立 minor 补齐，或把 docstring 改为「详见 `UI_FROZEN_FILES` 列表」。
2. 规则 §六 R11 守卫列表（`architecture-boundaries.md:457`）同样只列 4 个 flows 模块，与 `UI_FROZEN_FILES` 的 10 键不一致。同上，既有漂移。
3. `yate/keyproto/key_codec.py:1` 首行「Current key codec for **legacy** terminal key names」：`legacy` 一词仍出现在首行。issue P0-1 的诉求是消除「被读成待删除」的歧义，现 docstring 第 4-6 行已显式说明「not a deprecated module」，语义问题已解决；但若下游再有一次命名自查，首行的 `legacy` 仍可能被当作残留命中。建议（非阻塞）改为「Current key codec for terminal key names」。

---

## 九、未完成 / 未解决项

1. **无法写入评审记录文件**（本该是任务的交付动作）：本人没有文件写入工具；Bash 层面尝试 Python 写文件时，工具层把 `&&` 与嵌套引号破坏成字面量（`.gen.py` 内容变成 `'# temp'` 带引号字面量）。**主 agent 必须把本报告原样写入 `.trae/reviews/2026-11-07-iktbxc-naming-refactor.md`。** （主代理注记：已代写闭环。）
2. **smoke 的 `stress_rapid_toggles` 时序缺陷未修复验证**：按「评审不改产品源码」的约束只做定位与建议，未验证修复后是否稳定。已确认是本 issue 之外的既有测试卫生问题。
3. **`git log --follow` 对 `yate/editor_components/view.py` 的跨包追溯**：`--follow` 只跟踪单文件重命名链，`860ae95`（`editor_view` → `editor_components`）这一个**包级**迁移它跟到了，但更早的 `editor_view/editor.py` 历史可能需要在包路径上另做对照；本次只确认了三条重命名本身可追溯，未做全历史考古。

---

## 十、命令退出码汇总

| # | 命令 | 退出码 |
|---|---|---|
| 1 | `pyright yate/ tests/ tools/ pack/` | **0**（0 诊断） |
| 2 | `pytest tests/ -q -n auto` | **0** |
| 3 | `pytest tests/test_architecture.py -q` | **0**（37 passed） |
| 4 | `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | **0**（92.81% ≥ 75；3395 passed / 10 skipped） |
| 5 | `tools.smoke_test run --jobs 4`（第 1 次） | **1**（1462/1463；`stress_rapid_toggles`） |
| 6 | 同上 `--scenario stress_rapid_toggles --repeat 3 --jobs 1` | **1 → 0**（先 11/12 后 12/12） |
| 7 | 同上 `--repeat 5 --jobs 4` | **0** |
| 8 | `tools.smoke_test run --jobs 4`（第 2 次完整） | **0**（1463/1463，121/121） |
| 9 | `python -m yate --help` | **0** |
| 10 | 残余 `git grep`（源码面） | **1**（0 命中，期望绿灯） |
| 11 | 残余 `git grep`（含 CHANGELOG / zh_overrides） | **1**（0 命中） |
| 12 | 残余 `git grep`（含 `.trae/documents` / `.trae/reviews`） | **0**（命中全部落在豁免面） |

**最终评级：通过（条件式）——0 个 blocker、1 个 major（M1 临时脚本）、3 个 minor。** M1 属交付卫生，不影响运行时正确性；三个核心验收面（pyright 零诊断、pytest 全绿、覆盖率 ≥75、冒烟 121/121）均已实测通过，残余 grep 在源码/规则/wiki/README 面零命中。
