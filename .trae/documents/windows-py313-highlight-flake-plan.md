# windows-py313-highlight-flake-plan

> 任务来源：用户 2026-11-06「Windows py13 CI 修复」，附 Windows / py3.13.17 CI 腿
> 红跑日志（`test_highlighting_follows_the_override` 5s 超时）。
> 状态：**方案待批准**；批准后按 §四 实施。
> 关联：[windows-py313-ci-plan.md](windows-py313-ci-plan.md)（新增 Windows / 3.13 腿的前案，
> §七 留有「实际 CI 墙钟尚未观测」的口子，本次收尾回填）。

## 一、目标与非目标

**目标**

1. 消除 `tests/test_app_find.py::test_highlighting_follows_the_override` 在
   Windows / py3.13 CI 腿的 `wait_until` 5s 超时，使 4 条矩阵腿全绿；
2. 让该用例**自己驱动**高亮 pass 的调度，不再依赖「与测试无关的隐式重绘」；
3. 保留用例原意（`:set filetype=` 之后高亮跟随 override），不降低断言强度与覆盖率。

**非目标**

- 不改 `yate/` 下任何产品源码（本次失败是测试时序契约缺陷，不是高亮器缺陷）；
- 不改 CI 配置 `../../.github/workflows/test.yml`（矩阵、worker 数、
  `timeout-minutes: 15` 均不动；红跑墙钟 231.89s，预算充足）；
- 不改 `wait_until` / `tests/conftest.py`（300+ 调用点的公共语义不动）；
- 不处理红跑里的 `PytestUnraisableExceptionWarning`
  （`_ProactorBasePipeTransport.__del__` → `ValueError: I/O operation on closed pipe`
  是 Windows Proactor 的存量告警，来自 `test_lua_extensions.py`，不导致失败，
  且与本次超时无因果关系；另案观察）；
- 不修 `_hl_scheduled_key` 在 `_launch_highlight` / `_highlight_later` 提前返回分支
  未清理的潜在健壮性问题（实测失败态 `scheduled_key is None`，与本故障无关；
  登记为待办，另案评估）。

## 二、调研事实（每条带证据）

| # | 事实 | 证据 |
|---|---|---|
| 1 | 红跑：Windows py3.13.17 / xdist `gw0`，`test_app_find.py:451` 第一个 `wait_until(...filetype=="plaintext", timeout=5.0)` 返回 False；全腿 1 failed / 3394 passed / 10 skipped，TOTAL 92.86%，墙钟 231.89s（0:03:51） | 用户提供的 CI 日志 |
| 2 | `_hl_filetype` 初值 `""`，只有 `_highlight_later` 存结果时才被写入；`HighlightProbe.filetype` 是它的只读快照 | `../../yate/editor_components/highlighting.py:166`、`:367-376`、`:454-458` |
| 3 | 高亮 pass 的唯一调度入口是 `_tokens_for` → `_schedule_highlight`；`_tokens_for` 只由 `render_line` → `_syntax_kinds` 调用，`tokens_for()` 是它的公开等价入口 | `../../yate/editor_components/highlighting.py:192-229`、`:357-365`；`../../yate/editor_components/editor.py:355-366` |
| 4 | 空未命名 buffer 的 `render_line` 命中 `_welcome_active()` 后**提前返回** welcome 行，整帧不调用 `_tokens_for`，因此 startup 阶段根本不存在高亮 pass | `../../yate/editor_components/editor.py:398-403`、`:505-521` |
| 5 | 用例直接 `session.buffer.insert_text(...)` 不刷新视图；`wait_until` 只反复 `pilot.pause(0.01)`，不驱动渲染 | `../../tests/test_app_find.py:445-455`；`../../tests/conftest.py:311-331` |
| 6 | 原用例注释「startup pass for the pre-edit (empty) buffer is discarded」不准确：welcome 页让 startup pass 从未被调度 | 事实 4 + 事实 8 |
| 7 | `set filetype=python` 末尾调 `refresh_ui()` → `_refresh_views()` → `content_changed()` → `refresh()`，只标记重绘、实际调度在下一帧渲染 | `../../yate/editor.py:698-733`、`:432-438`、`:459-475`；`../../yate/editor_components/editor.py:181-192` |
| 8 | **本机探针实测**（Windows py3.13.2 / pytest `-n 1`）：插入文本后立即 `highlight_probe()` → `filetype='' tokens=None scheduled=None`，`_welcome_active()` 已为 False —— 零 pass 在途、零 pass 落地。原用例 13 次单跑 1 次失败（可复现 flake）；CI 原命令本地全量 3396 passed / 10 skipped / 92.92% / 194.66s 未复现（负载差异） | 一次性探针（已删除，实测记录于本表） |
| 9 | 修复预演（显式 `editor.tokens_for(0)` 驱动 + 去掉 plaintext 基线等待）连续 25 次 `pytest -q -n 1` 全绿，含 `("keyword","def")` / `("function","foo")` 断言 | 一次性探针（已删除，实测记录于本表） |
| 10 | 既有先例：`test_app_textual.py` 在 `run_command(...)` 之后显式调 `tokens_for(0)` 驱动渲染路径，再 `wait_until` 收敛 | `../../tests/test_app_textual.py:668`、`:672`、`:685` |
| 11 | 该用例由 `fb030fd`（2026-10-07 大文件拆分）迁入，非新写；但自迁入起就依赖隐式重绘 | `git log -S ... -- tests/test_app_find.py`；`git blame -L 439,471` |
| 12 | plaintext 侧的高亮切换覆盖已由 `test_app_textual.py:670-679`（python → plaintext）与 `:681-692`（doc 切换）承担，删去本用例的 plaintext 基线等待不减覆盖 | `../../tests/test_app_textual.py:655-694` |

**根因链**：空 buffer → welcome 页渲染跳过 token cache（事实 4）→ 用例直接改 buffer 且
不刷新视图（事实 5）→ `wait_until` 只 pause、不渲染（事实 5）→ 没有任何代码路径调用
`_tokens_for`，`_hl_filetype` 恒为 `""`（事实 2/3/8）→ 5s 超时。
本地之所以几乎总过，是 app 启动期状态栏 / compositor 的隐式重绘恰好落在 insert_text
之后；CI 高负载下该窗口未被命中，故只在 Windows / py3.13 新腿暴露。

```mermaid
sequenceDiagram
    participant T as test_highlighting_follows_the_override
    participant V as EditorView.render_line
    participant H as HighlightMixin
    participant P as pilot.pause

    T->>V: startup frame (empty buffer)
    V-->>H: _welcome_active() -> welcome row, no _tokens_for
    Note over H: _hl_filetype = "" ; scheduled_key = None
    T->>T: buffer.insert_text (no refresh)
    loop wait_until 5s
        T->>P: pause(0.01)
        P-->>T: no repaint driven by the test
    end
    Note over T: filetype never becomes "plaintext" -> assert False

    rect rgb(220, 240, 220)
    T->>H: tokens_for(0) after :set filetype=python (fix)
    H->>H: _schedule_highlight(0.0) -> worker
    H-->>T: _hl_filetype = "py", tokens cached
    end
```

## 三、备选方案与否决理由

| 方案 | 内容 | 裁决 |
|---|---|---|
| A. 测试显式驱动渲染路径 | 删去脆弱的 `filetype=="plaintext"` 基线等待；`set filetype=python` 后显式 `editor.tokens_for(0)` 调度 pass，再 `wait_until` 等 `filetype=="py"` **且** `tokens is not None`；保留 token 断言 | **推荐**。与 `test_app_textual.py` 既有先例一致；用例自己创建所等待的事件；不动产品代码与 CI 配置 |
| B. 调大 timeout / 在谓词里调 `tokens_for` | `timeout=15.0`，或把 `tokens_for(0)` 塞进 lambda 谓词 | 否决。掩盖「测试不驱动渲染」的设计缺陷；CI 上可能整窗口都没有隐式 repaint，加时只是降低概率；谓词带副作用违反 `wait_until` 的纯查询语义（`conftest.py:315`） |
| C. 改 welcome 页渲染也调度高亮 pass | 产品源码里让 `_welcome_active()` 分支前调用一次 `_tokens_for` | 否决。空 buffer 启动 tokenizer worker 零收益，改变产品行为、扩大范围，且失败根因是测试缺刷新驱动而非渲染缺调度 |
| D. 让 `buffer.insert_text` 自动 refresh view | L0 模型层反向触碰 L2 组件 | 否决。违反架构 R4（`../../.trae/rules/architecture-boundaries.md`）；真实编辑路径已由 L3 `refresh_ui()` 负责，测试里的直接模型写入本就应自己驱动 |
| E. 顺带修 `_hl_scheduled_key` 提前返回未清理 + Proactor warning | 一并改 `highlighting.py` 与 Lua 扩展用例 | 否决（本轮）。实测失败态 `scheduled_key is None`，两者都与本故障无因果关系；混入会扩大回归面，登记为待办另案 |

## 四、实施步骤

### 步骤 1：方案文档

- 输入：本文件；输出：`docs(plan)` 单独提交。

### 步骤 2：修 `tests/test_app_find.py`（唯一代码文件）

- 改动清单：`../../tests/test_app_find.py` 的
  `test_highlighting_follows_the_override`（`:439-471`）。
- 动作：
  1. 保留 `insert_text("def foo():\n    pass\n")`；
  2. 删除第一个 `wait_until(...filetype=="plaintext")` 及其过时注释（事实 6/12）；
  3. `app.editor.run_command("set filetype=python")` 之后加
     `assert editor.tokens_for(0) == []`，显式驱动渲染路径并保留「首帧无 token」的断言；
  4. 第二个 `wait_until` 谓词收紧为
     `probe.filetype == "py" and probe.tokens is not None`；
  5. 注释改写为真实机制：welcome 页不触碰 token cache、直接改 buffer 不刷新视图、
     故须显式调 `tokens_for` 调度 pass（全英文，遵守 `misc-rules.md` §四）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
  1..30 | ForEach-Object { .venv\Scripts\python.exe -m pytest tests/test_app_find.py::test_highlighting_follows_the_override -q -n 1 --no-header; if ($LASTEXITCODE -ne 0) { throw "flake at run $_" } }
  .venv\Scripts\python.exe -m pytest tests/test_app_find.py -q -n auto
  ```
- 期望：pyright 0；30 次连续 exit 0（原用例同期 13 次有 1 次失败）；整文件 exit 0。

### 步骤 3：回填文档

- 改动清单：[windows-py313-ci-plan.md](windows-py313-ci-plan.md) §七「环境事实」
  （补 Windows / py3.13 腿首次 CI 实测 231.89s 与本 flake 的闭环指向） +
  本文件新增「§五 执行记录」。
- 验收命令：`git diff --check`。
- 输出：`docs(plan)` 单独提交。

### 步骤 4：收尾门禁（主代理亲跑，退出码 0）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

- 追加一次 CI 原命令复跑（`--cov-report=term-missing -n auto`），确认用例数与
  `fail_under=75` 口径不变。并行下若出现时序 flake，按
  `python-coding-style.md` §4.7 用 `-n 1` 复核并修用例，不得记为「重跑即过」。
- 只提交、不推送（推送需用户显式要求）。

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| 删去 plaintext 基线等待后，用例不再覆盖「未命名 buffer 自动判 plaintext」 | 该路径由 `test_app_find.py:400-422`、`test_app_textual.py:670-679` 覆盖；本用例名与断言只针对「override 后高亮」 |
| `tokens_for(0) == []` 在 pass 已提前落地时不再成立 | `set filetype=python` 改了 `doc.filetype`，`_tokens_for` 首分支在 filetype 不匹配时必返回 `[]`（`highlighting.py:207-222`）；25 次预演全绿 |
| 显式驱动后仍有个别 worker 未在 5s 内落地 | 谓词同时要求 `tokens is not None`，`tokens_for` 已同步调度 pass；CI 腿墙钟 231.89s / 15min 预算充足，无需调 timeout |
| 覆盖门禁数字波动 | 用例数不变（不增删测试函数），仅改单个用例内部；以实测数字回填 |

回滚路径：单文件、单笔 `test(app)` 提交，`git revert` 即整体回退；文档两笔
`docs(plan)` 可独立 revert；无产品代码、依赖与 CI 配置变更。

## 六、执行记录（收尾回填）

（待批准后回填：每步提交号、验收命令实测结果与退出码、偏离记录。）

### 子代理调度说明

本任务【方案】阶段由主代理按 `task-orchestration.md` §三 兜底亲自产出：本机
CodeBuddy 插件环境已多次实证 `plan-architect-designer` 定义文件 frontmatter 的
`qwen-3.7-plus` 未注册，spawn 必败且任务书指定模型无效（见项目记忆
`reference_codebuddy_env_quirks`），不再重复无效 spawn；如实标注「子代理零产出」，
方案内容以本文件 §二 的实测证据为唯一依据。
