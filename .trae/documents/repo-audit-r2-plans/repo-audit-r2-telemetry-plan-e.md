# repo-audit-r2 · plan_e：门禁可绕过弱点收口（覆盖率本地兜底 + 冒烟接入 CI）

- 波次：**wave-3**（串行，依赖 wave-2 通过）
- 来源维度：10（门禁规则）
- 状态：**待批准**（本阶段不改代码、不改测试）

---

## 一、输入

- 总纲：[`overview.md`](overview.md) §五 维度 10、§六 M-3 / M-4
- 现状依据（主代理亲跑实测）：
  - `pyproject.toml:120-132`：`[tool.pytest.ini_options]` 只有
    `testpaths` / `addopts = "-q"` / `filterwarnings`；注释第 127-130 行明写
    「coverage 是 opt-in（`pytest --cov`）且 fail-under 门禁在 CI 工作流里，
    **不在 addopts**」
  - `pyproject.toml:150-154`：`[tool.coverage.report]` **也没有** `fail_under`
    （注释解释：coverage.py 把 `report.fail_under` 施加到**每一次** `--cov` 运行，
    部分运行会假失败）
  - `.github/workflows/test.yml:82`：CI 命令行显式带
    `--cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75`
  - `.github/workflows/test.yml` 全 125 行逐行核对：**没有任何 smoke job/step**
- 既有结论关系：
  - M-3 是**全新**（既有审计从未从「门禁可被绕过」角度审过覆盖率的本地兜底）
  - M-4 是**全新**（`2026-10-16-full-repo-audit.md` §二 维度 10 只核对「四道门禁全绿」，
    未核对门禁本身的覆盖面）
- 前置条件：wave-2（`plan_c` ∥ `plan_d`）验收通过
  （此时架构守卫为 **35 用例**，本计划的所有门禁命令都按 35 口径书写）

## 二、独占文件清单（只改这 3 个文件）

1. `pyproject.toml`
2. `.github/workflows/test.yml`
3. `tests/test_gate_config.py`（**新建** —— 见 §五，理由：门禁配置本身必须被回归，
   否则下一次有人把 `--cov-fail-under` 从 CI 挪走时没有任何测试会红）

---

## 三、具体修改

### M-3 · `pyproject.toml` —— 覆盖率门禁的本地兜底

**现状**（实测原文，`pyproject.toml:127-132`）：

```toml
# NOTE: coverage is opt-in (`pytest --cov`) and the fail-under gate lives in the
# CI workflows, not in addopts.  A ``--cov-fail-under`` in addopts would fail
# every partial run (e.g. `pytest tests/test_config.py`, which covers a fraction
# of the package) even when all selected tests pass.
# Reproduce the CI gate locally:
#   python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75
```

**为什么是问题**（这是本条的核心推理，必须完整写出）：

1. `python -m pytest tests/ -q`（`task-orchestration.md` §二 第 7 步的收尾门禁、
   `python-coding-style.md` §五 第 5 条「`pytest tests/` 全部通过」、
   绝大多数开发者的本地习惯命令）**完全不触发覆盖率**；
2. 开发者本地跑全绿 → 推到 PR → CI 的覆盖率门禁红了 → 这是**唯一**能拦住
   覆盖率回退的关卡，而它的反馈只在远端；
3. 更弱的一点：`--cov-fail-under` 完全挂在 **CI 命令行字符串** 上
   （`test.yml:82`），不在任何配置文件里。任何人改 CI 命令行（改参数、调 matrix、
   复制粘贴）都可能**静默丢掉**这个门禁，而 `pyproject.toml` 里没有任何断言
   记录「门禁阈值是 75」；
4. 也就是说：门禁阈值**既不可被本地复现**（无配置），也**不可被回归测试保护**。

**改法（两处，互相配套）**：

**(a) 在 `[tool.coverage.report]` 新增 `fail_under`，并把「部分运行豁免」显式化**

`pyproject.toml:143-149` 的 `[tool.coverage.report]` 段追加：

```toml
# The gate threshold lives HERE (not only on the CI command lines) so a local
# ``pytest tests --cov`` reproduces CI exactly and the value itself is
# regression-tested by tests/test_gate_config.py.  coverage.py applies
# fail_under to *every* ``--cov`` run, so a partial run must opt out with
# ``--cov-fail-under=0`` -- which is why ``--cov`` itself stays opt-in and is
# NOT in addopts (adding it there would tax every keystroke-speed test loop).
fail_under = 75
```

**(b) 在 `[tool.pytest.ini_options]` 的注释里把「复现 CI」的命令更新为新口径**

`pyproject.toml:127-132` 的注释段替换为：

```toml
# Coverage is opt-in (``pytest --cov``) and stays OUT of addopts: a partial run
# must not pay for instrumentation.  The gate threshold itself is
# ``[tool.coverage.report] fail_under`` (single source of truth, asserted by
# tests/test_gate_config.py), so a bare ``--cov`` reproduces the CI gate.
# Reproduce the CI gate locally:
#   python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing
#   python -m pytest tests/test_config.py --cov=yate --cov-fail-under=0   # partial run
```

> **为何不把 `--cov-fail-under=75` 直接塞进 `addopts`**：那会让
> `pytest tests/test_config.py`（不带 `--cov`）也会尝试施加阈值吗？不会 ——
> 但它会让**任何带 `--cov` 的部分运行**失败，而这正是现有注释第 128-130 行
> 明确要避免的。`[tool.coverage.report] fail_under` + 文档化的 `--cov-fail-under=0`
> 逃生口，是「单一事实源」与「部分运行可用」两个诉求的唯一同时满足点。

### M-4 · `.github/workflows/test.yml` —— 把冒烟接入 CI

**现状**（实测，全 125 行）：
- job `test`（`:23-82`）：Changelog gate + `pip install -e ".[dev]"` + pytest 全量；
- job `lint`（`:87-119`）：pyright strict；
- **没有** `tools.smoke_test` 的任何调用。

**为什么是问题**：`tools/smoke_test` 是本仓唯一的 **Textual UI 端到端验证面**
（`tools/smoke_test/scenarios/` 实测 21 个场景模块，含 explorer / panes / diff /
find-replace / screensaver / terminal 等）。它**不在** `pytest` 的 `testpaths`
（`pyproject.toml:121` = `["tests"]`），也**不在**任何 CI job 里 —— 意味着
**所有 UI 冒烟场景在 CI 上从不执行**，回归只能靠本地手动跑
`.venv\Scripts\python.exe -m tools.smoke_test run`。
`2026-10-12-full-review.md` 等多轮评审依赖冒烟作为验收证据，而 CI 并不跑它。

**改法**：在 `test` job 之后新增独立 job `smoke`（不塞进 `test` job —— 冒烟需要
真实终端尺寸与交互时序，混进矩阵会让 `test` job 的 `timeout-minutes: 15`
把两类失败混为一谈）：

```yaml
  smoke:
    name: ui smoke (pilot, ${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
          cache-dependency-path: pyproject.toml

      - name: Upgrade pip
        run: python -m pip install --upgrade pip

      - name: Install package and dependencies
        run: python -m pip install -e ".[dev]"

      - name: UI smoke scenarios
        # Not covered by pytest: tools/smoke_test is outside testpaths, so no
        # CI job exercised the Textual end-to-end scenarios at all.  Pilot
        # drives a headless app, so TERM is set for the Linux leg only.
        env:
          TERM: xterm-256color
          PYTHONDONTWRITEBYTECODE: '1'
        run: python -m tools.smoke_test run --json smoke-report.json --report smoke-report.txt

      - name: Upload smoke report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: smoke-report-${{ matrix.os }}
          path: smoke-report.json
          if-no-files-found: warn
```

**已核对的事实 1（CLI 参数，Phase 1 已实测，无需执行者再确认）**：

- `tools/smoke_test/cli.py:336` 定义子命令 `run`；
- `:339` `run` 接受 `--coverage`（flag）；通用参数里 `:66` 是 `--json PATH`、
  `:68` 是 `--report PATH`（两者都是**文件路径**，**不存在** `--report-format` /
  `--out` 选项 —— 执行者**不得**沿用其它工具的常见写法）。

**待执行者核对的两个事实（本计划不臆造）**：
2. 冒烟场景的**基线快照**（`tools/smoke_test/baselines/`，实测存在）是否随场景数
   变化而需要重生成。若基线是固定资产且平台相关（Windows 与 Linux 渲染不同），
   则本 job 需按 `matrix.os` 分别指定基线目录，或**先只接入 Linux 单腿**
   （把 `matrix.os` 收敛为 `[ubuntu-latest]` 并在 yml 注释里写明「Windows 腿待
   基线补齐后加入」）—— 执行者须在 Phase 1 实测后二选一，并在报告中说明取舍。

---

## 四、备选方案与否决理由

| 备选 | 否决理由 |
|---|---|
| M-3 把 `--cov=yate --cov-branch --cov-fail-under=75` 直接写进 `addopts` | `addopts` 对**每一次** pytest 调用生效，包括 `pytest tests/test_config.py`。开了 `--cov` 后阈值必然施加到部分运行上（覆盖率 ~5%），本地每次改一行代码都会红 —— 现有注释 `:128-130` 拒绝的正是这条路，且它是**唯一**被显式论证过的替代方案，不得推翻。 |
| M-3 只在 `tests/README.md` 写一句「本地记得加 `--cov-fail-under=75`」 | 文档不是门禁。`subagent-workflow.md` §四「只汇报可验证的事实」的精神是：口径必须落在可执行的配置里，而不是靠人记。文档化已在 §三(b) 里做，但它**是补充**，不是替代。 |
| M-3 用 `[tool.coverage.report] fail_under = 75` 但**不改** `test.yml:82` 的命令行 | 命令行显式传 `--cov-fail-under=75` 会**覆盖**配置值（两者同值，无冲突），但会让「单一事实源」名存实亡 —— 改配置不改命令行的读者会困惑。执行者应**同时**把 `test.yml:82` 的 `--cov-fail-under=75` 去掉，让 CI 与本地走同一配置源。 |
| M-4 把冒烟塞进 `test` job 的 pytest 步骤之后 | 冒烟与单测在 `test` job 的 `timeout-minutes: 15` 内串行，两类失败的定位信号会互相污染；且冒烟失败时的报告快照上传需要 `if: always()` 的独立 step，混在一起会让 `test` job 的 YAML 难读。独立 job 是 `subagent-workflow.md` §一「文件/职责独占」的 YAML 等价形态。 |
| M-4 只在 Linux 腿接冒烟（不建 matrix） | 可以，但必须**在方案里显式二选一**而不是默认。我把两个选项写进 §三 的「待核对事实 2」，并要求执行者实测基线后决定 —— 若基线与平台无关则上 matrix（覆盖面更大），若平台相关则先单腿并登记待办。**不允许不决策就跳过冒烟接入**。 |

---

## 五、新增测试用例（详细三要素）

### 用例 1 —— 门禁阈值是配置事实且被回归

- **文件**：`tests/test_gate_config.py`（**新建**）
- **用例名**：`test_coverage_fail_under_is_declared_in_pyproject`
- **前置条件 / fixture**：`pathlib.Path`（仓库根由 `__file__` 上溯两级得到，
  与 `tests/test_architecture.py` 的 `PROJECT` 常量同形态）
- **arrange**：用 `tomllib`（stdlib，3.11+）读 `pyproject.toml`；
  取 `tool.coverage.report.fail_under`
- **act**：读取该值
- **断言**：`fail_under == 75`（与 CI 门槛同值 —— 若有人把阈值改成 60 或删掉该键，
  本用例立刻红）

**用例名**：`test_coverage_threshold_is_not_hardcoded_on_the_ci_command_line`
- **arrange**：读 `.github/workflows/test.yml` 全文
- **act**：检索 `pytest` 命令行里是否仍带 `--cov-fail-under`
- **断言**：**不出现** `--cov-fail-under`（阈值已由 `pyproject.toml` 单点承载；
  CI 命令行不再重复，保证「改一处即改全」）

**用例名**：`test_pytest_addopts_does_not_enable_coverage`
- **arrange**：读 `[tool.pytest.ini_options].addopts`
- **act**：检索其中是否含 `--cov`
- **断言**：**不含** `--cov`（保护 §三 决定的不变式：覆盖率保持 opt-in，
  部分运行不被仪表化 —— 这是 `plan_e` 最容易被后人「顺手优化掉」的地方）

### 用例 2 —— 冒烟场景清单完整性（门禁面的回归保护）

- **用例名**：`test_smoke_scenarios_are_discovered_by_the_harness`
- **前置条件 / fixture**：无（纯结构检查，与 `tools/smoke_test/scenarios/` 的
  `__init__` 无关）
- **arrange**：枚举 `tools/smoke_test/scenarios/*.py`（排除 `_base.py`）
- **act**：逐个用 `ast.parse` 找模块级 `SCENARIOS` 赋值
- **断言**：
  1. 每个场景模块都有模块级 `SCENARIOS` 赋值（否则它永远不会被跑 —— 这正是
     「CI 不跑冒烟」之外的第二层静默失效面）；
  2. 场景模块数 **≥ 21**（实测基线：`findstr` 实测 `tools/smoke_test/scenarios/`
     为 21 个模块；该下界防止有人误删整个目录而 CI 不报）
- **反向路径**：断言 `tools/smoke_test/cli.py` 存在且模块 docstring 非空
  （CI job 调用的入口必须真实存在，否则 yml 里的命令在 CI 上才首次暴露）

### 用例 3 —— 冒烟 CI 步骤存在（最直接的回归保护）

- **用例名**：`test_ci_workflow_runs_the_ui_smoke_suite`
- **arrange**：读 `.github/workflows/test.yml` 全文
- **act**：检索是否含 `tools.smoke_test`
- **断言**：
  1. 命中（CI 确实调冒烟 —— 这条用例就是 M-4 的「不许再删掉」保险丝）；
  2. 命中行的上下文 5 行内含 `run:` 键（确认它在 run 步骤里，而非注释里）

---

## 六、验证方案

| 验证目标 | 命令（PowerShell，仓库根） | 通过判定 |
|---|---|---|
| 门禁配置回归 | `.venv\Scripts\python.exe -m pytest tests/test_gate_config.py -q` | 退出码 0，5 个用例全绿 |
| 新门槛本地可复现 | `.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing` | 退出码 0，覆盖率 ≥ 75%（此为**执行者**的门禁命令；方案阶段不跑） |
| 部分运行逃生口可用 | `.venv\Scripts\python.exe -m pytest tests/test_config.py --cov=yate --cov-fail-under=0 -q` | 退出码 0（证明 §三 的 partial-run 逃生口真实有效） |
| 部分运行**不带**逃生口会红（反证） | `.venv\Scripts\python.exe -m pytest tests/test_config.py --cov=yate -q` | **预期退出码非 0**（证明 `fail_under` 确实生效，不是空配置） |
| 冒烟 CLI 参数核对 | `.venv\Scripts\python.exe -m tools.smoke_test --help` 与 `python -m tools.smoke_test run --help` | 退出码 0，输出与 §三 yml 里写的参数**逐字一致** |
| 冒烟本地可跑（基线事实核对） | `.venv\Scripts\python.exe -m tools.smoke_test run --json probe.json --report probe.txt` | 退出码 0；若因基线/环境失败，记录**真实**失败场景名并在报告中说明 |
| 全仓零回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 类型零诊断 | `.venv\Scripts\python.exe -m pyright tests/test_gate_config.py` | 0/0/0，退出码 0 |
| CI 配置语法有效 | `.venv\Scripts\python.exe -c "import pathlib,sys;p=pathlib.Path('.github/workflows/test.yml');print('present' if 'smoke:' in p.read_text(encoding='utf-8') else 'missing')"` | 输出 `present` |
| **yml 语法**（可选，需 yamllint） | 人工在 PR 页面确认新 job 无语法错误 | CI 能启动新 job |

## 七、手工验证

1. **CI 冒烟 job 首次上线**：在 PR 上确认 `smoke` job 在
   ubuntu / windows 两腿都出现且**真的执行了场景**（不是 0 场景秒过 ——
   若报告显示 `scenarios: 0`，说明场景发现被破坏，回到用例 2 排查）；
2. **覆盖率门槛本地等价**：本地跑 §六 的「新门槛本地可复现」与
   「部分运行不带逃生口会红」两条，把两条的**真实退出码与覆盖率百分比**回填总纲 §五 维度 10。

## 八、风险与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| `fail_under` 使**开发者的部分运行**（`pytest tests/x.py --cov`）突然变红 | 中 | §三(b) 已在 `pyproject.toml` 注释里给出 `--cov-fail-under=0` 逃生口；用例 1 的 `test_pytest_addopts_does_not_enable_coverage` 保证 `--cov` 永不进 addopts，故**不覆盖 `--cov` 的纯部分运行不受影响** |
| CI 上冒烟因基线差异在 Windows 腿失败，阻塞合并 | 中 | §三「待核对事实 2」已把「先只接 Linux 单腿」列为显式选项；执行者必须实测后决定，**不允许先接两腿再因失败删 Windows 腿**（那是把门禁改成摆设） |
| 冒烟在 CI 上比本地慢（headless 渲染时序） | 中 | 独立 job 的 `timeout-minutes: 20`（高于 `test` job 的 15）；`if: always()` 上传报告便于定位 |
| 去掉 `test.yml:82` 的 `--cov-fail-under` 后，若 `pyproject.toml` 的 `fail_under` 因某种原因未生效，门禁静默消失 | 低 | §六「部分运行不带逃生口会红（反证）」就是这条的**实证反证命令** —— 它证明 `fail_under` 真实生效；用例 1 又把阈值本身锁在 75 |
| 新建 `tests/test_gate_config.py` 与既有测试文件命名/风格冲突 | 低 | 命名符合 `python-coding-style.md` §4.7（`test_<module>.py` 语义为「门禁配置」）；必须 `from __future__ import annotations`（已核对全仓 0 缺失，本文件不得破例） |

**回滚**：`git revert <commit>`。
- 只回滚 M-3：`pyproject.toml` 的 `fail_under` 消失 → 回到「阈值只在 CI 命令行」的原状，
  门禁**仍然有效**（`test.yml:82` 未动），无残留；
- 只回滚 M-4：`smoke` job 消失 → 回到「CI 不跑冒烟」的原状，无残留；
- **注意**：若只回滚 `pyproject.toml` 而留 `test.yml` 的改动（去掉了命令行 `--cov-fail-under`），
  覆盖率门禁会**完全消失** —— 这是最危险的中间态。因此 §三 的 (a) 与 `test.yml:82`
  的改动**必须同一 commit**，`tests/test_gate_config.py` 的用例 1 是它的保险丝。

---

## 九、执行记录（plan-executor 实测，2026-10-18）

工作区：worktree `ref/repo-audit-r2`；解释器 `.venv/Scripts/python.exe`
（实测 Python 3.13.2 / textual 8.2.8 / rich 15.0.0 / platform Windows）。

### 9.1 Phase 1 实测：冒烟在本平台可跑（退出码 0）

命令（§六「冒烟本地可跑」）：

```text
.venv\Scripts\python.exe -m tools.smoke_test run --json probe.json --report probe.txt
```

实测结果（Windows 本机）：`112/112 scenarios passed`、`1354/1354 checks (100%)`、
`105.33s total`、**退出码 0**。

### 9.2 Phase 1 决策：smoke job 接**双平台矩阵**（含 Windows 腿）

依据（实测，非推断）：

1. **`run` 子命令完全不读基线**：`tools/smoke_test/cli.py:336-341` 的 `run` 只调
   `cmd_run`，全文（`:172-212`）无任何 `baselines.load_baseline` / `default_baseline_dir`
   调用（仅 `:108-109` 的 `baselines.jsonable` 用于 `--json` 报告的取值清洗）；
   只有 `compare`（`:257-322`）与 `snapshot`（`:215-254`）才碰基线。因此
   §三「待核对事实 2」担心的「基线平台漂移」**对本 job 不成立** —— 计划担心的失效面
   在 `run` 路径上不存在。
2. **基线目录真实路径是 `tools/smoke_test/smoke_baselines/`**（不是 §三 写的
   `tools/smoke_test/baselines/`），实测 81 个 per-scenario JSON；基线契约只含
   checks（`tools/smoke_test/baselines.py:1-8` 说明「无绝对路径、无耗时」），
   仅 `compare` 消费。
3. **Windows 腿本机实测全绿**（9.1），故按 §四 的判据「基线与平台无关则上 matrix
   （覆盖面更大）」选择双腿矩阵，**不**收敛为 Linux 单腿。

### 9.3 与计划正文的偏差（实测依据）

| 偏差 | 计划原文 | 实测 | 处置 |
|---|---|---|---|
| 基线目录名 | §三 待核对事实 2 写 `tools/smoke_test/baselines/` | 实为 `tools/smoke_test/smoke_baselines/`（81 个 JSON） | 文档勘误，不影响 yml（`run` 不用基线） |
| 场景规模 | §五 用例 2 断言「场景模块数 ≥ 21」，依据写「findstr 实测 21 个模块」 | `scenarios/*.py` 共 21 个文件 = 19 个场景模块 + `__init__.py` + `_base.py`；运行期场景数 **112** | 下界按实测改为「场景模块（排除 `_base.py` / `__init__.py`）≥ 19」，并在用例注释里写明实测基数 |
| `--report` 产物后缀 | §三 yml 写 `--report smoke-report.txt` | `cli.py:68-69` + `cli.py:83-92`：`--report PATH` 导出的是**独立 HTML 报告**；实测 `probe.txt` 首行 `<!DOCTYPE html>` | yml **按计划原文保留** `smoke-report.txt`（不擅自改设计），上报主代理裁决是否改名为 `.html` |

### 9.4 已落地的改动（文件:行号）

| 文件 | 位置 | 改动 |
|---|---|---|
| `pyproject.toml` | `:127-132` → 新 6 行 | `[tool.pytest.ini_options]` 注释段按 §三(b) 替换：口径改为「阈值在 `[tool.coverage.report] fail_under`」，并给出 `--cov-fail-under=0` 部分运行逃生口 |
| `pyproject.toml` | `:150-159` → 新 8 行 | §三(a)：新增 `fail_under = 75` + 英文注释；原「阈值刻意放在 CI 命令行」注释段（与新口径矛盾）删除，保留 2026-09-23 的历史实测段 |
| `.github/workflows/test.yml` | `:9` | 头部「Reproduce locally」行的 `--cov-fail-under=75` 删除（用例 2 断言全文件不出现该串） |
| `.github/workflows/test.yml` | `:75-84` | pytest 步骤注释改为「阈值不在命令行，单点源在 pyproject」，`run:` 去掉 `--cov-fail-under=75` |
| `.github/workflows/test.yml` | `:86-135` | 新增 `smoke` job（§三 M-4 原文，双平台矩阵），置于 `test` 与 `lint` job 之间 |
| `tests/test_gate_config.py` | 新建 | §五 的 5 个用例 |

### 9.5 已完成的验收命令（实测退出码）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `pytest tests/test_gate_config.py -q` | 0 | 5 passed（首轮 pyright 报 1 处 `reportUnnecessaryCast`，已修后复跑 0/0/0） |
| `pyright tests/test_gate_config.py` | 1 → 0 | 修前 `1 error`（`:55` 多余 cast），修后 `0 errors, 0 warnings, 0 informations` |
| `python -m tools.smoke_test --help` | 0 | 子命令 `{run,snapshot,compare}` |
| `python -m tools.smoke_test run --help` | 0 | 逐字含 `--json PATH` / `--report PATH`；**无** `--report-format` / `--out` |
| `python -c "... 'smoke:' in test.yml ..."` | 0 | 输出 `present` |

> 退出码采集口径：cmd 的 `%ERRORLEVEL%` 会在整行解析时提前展开（早期几次记录不可信），
> 改用 `cmd /v:on /c "... & echo !ERRORLEVEL!"` 或直接取工具返回的 `exitCode`。
> 9.1 的冒烟退出码 0 由 harness 自报摘要行 `exit 0` 佐证，尚需用可靠口径复跑一次（见 9.6）。

### 9.6 Phase 1 覆盖率基线（改动前，阈值仍成立）

命令（主代理指定的前置核对口径）：

```text
.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75
```

实测：`2500 passed, 9 skipped in 604.64s`、
`Required test coverage of 75% reached. Total coverage: 91.99%`、
`TOTAL 15387 995 4940 465 92%`、**退出码 0**。
→ 阈值 75 在本轮其它波次新增代码后**仍然成立**，余量约 17 个百分点；
**不下调阈值**。

### 9.7 部分运行逃生口的两条实证（子计划 §六 第 3、4 行）

| 命令 | 退出码 | 关键输出 |
|---|---|---|
| `pytest tests/test_config.py --cov=yate --cov-fail-under=0 -q` | 0 | `TOTAL ... 24%`（逃生口生效，部分运行不被阈值误杀） |
| `pytest tests/test_config.py --cov=yate -q` | **1** | `ERROR: Coverage failure: total of 24 is less than fail-under=75` / `FAIL Required test coverage of 75.0% not reached. Total coverage: 24.38%` |

→ 第二条是「`[tool.coverage.report] fail_under` 真实生效、不是空配置」的**实证反证**：
去掉 CI 命令行的 `--cov-fail-under` 之后门禁并未消失。

### 9.8 冒烟复跑（可靠退出码口径）

命令：`.venv\Scripts\python.exe -m tools.smoke_test run --json probe.json --report probe.txt --quiet`
（与 yml 同一命令，仅加 `--quiet` 压缩日志；yml 不带该参数）
实测：harness 摘要 `exit 0`、**进程退出码 0**。

### 9.9 改动后全量门禁（§六 第 2 行「新门槛本地可复现」）

命令（**不带** `--cov-fail-under`，阈值只来自 `[tool.coverage.report]`）：

```text
.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing
```

实测：`2505 passed, 9 skipped in 546.40s`、
`Required test coverage of 75.0% reached. Total coverage: 91.98%`、
`TOTAL 15387 996 4940 466 92%`、**退出码 0**。
用例数由 2500 增至 2505（= 新增的 5 个门禁配置用例）。

> 该命令的测试选择与 §六 第 7 行 `pytest tests/ -q` 完全相同（`testpaths = ["tests"]`），
> 且全部通过、退出码 0，故以此一次运行同时作为「全仓零回归」的证据，不重复再跑一遍
> 无仪表化的全量（结论等价，省一次全量门禁时长）。

### 9.10 收尾状态

- 一次性探针产物 `probe.json` / `probe.txt` 已删除；中途因工具超时残留在
  `.trae/probe_e_cov.txt` 的临时输出也已删除。
- 工作区改动仅落在独占清单内：`pyproject.toml`、`.github/workflows/test.yml`、
  `tests/test_gate_config.py`（新建）+ 本文档执行记录。
- 未执行 `git add` / `commit` / `push`。
