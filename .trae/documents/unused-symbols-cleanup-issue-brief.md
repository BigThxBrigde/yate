# IKTR5Q 需求素材（【领会】阶段整理，非方案）

> 本文件是闭环流程步骤 1 的**情报素材**，只整理 issue 原文与环境事实，不做任务分析、
> 不产出方案。方案由【方案】阶段落盘到
> [`unused-symbols-cleanup-plans/overview.md`](unused-symbols-cleanup-plans/overview.md)
> 及同目录子计划。

来源：<https://gitee.com/jermaine/yate/issues/IKTR5Q>
标题：`ENH - 清理全仓无用的变量与函数形参：能删则删，框架契约类登记保留`
状态：待办的 / enhancement / 创建于 2026-11-08 17:53 / 评论 0 条 / 未关联分支与 PR。

## 一、背景与现状（issue 原文要点）

- 起因：`yate/app.py:186` 的 `watch_theme(self, _theme: str)` 形参从未使用。该形参是
  Textual reactive watcher 回调签名；实测 Textual 8.2.8 的 `invoke_watcher`
  （`textual/reactive.py:106-116`）按形参个数分派 0/1/2 三种形态，改成无参 watcher
  后构造与赋值时均正常触发、无异常，属**可删**一类。
- 规模：对 `yate/`、`tools/`、`tests/`、`pack/` 共 402 个 `.py` 做 AST 粗扫
  （判定口径：函数体内无任何 `Load` 引用的形参；赋值后无任何 `Load` 引用的局部名；
  含嵌套作用域，属保守口径，含契约类误报）。

| 域 | 未使用形参 | 其中 `_` 前缀 | 未使用局部名 | 其中 `_` 解包占位 |
| --- | --- | --- | --- | --- |
| `yate/` | 70 | 7 | 81 | 45 |
| `tools/` | 10 | 2 | 20 | 18 |
| `tests/` | 507 | 103 | 552 | 152 |
| `pack/` | 0 | 0 | 0 | 0 |
| 合计 | **587** | 112 | **653** | 215 |

### 关键取证表（issue 原文：数字不能直接当删除清单）

| 类别 | 证据 | 结论 |
| --- | --- | --- |
| pytest fixture 形参 | 50 处，如 `tests/conftest.py:240 isolated_home(tmp_path)`、`tests/test_changelog_tool.py:729 stub_gitdata` | 不可删：删掉会关闭 fixture 的副作用（家目录隔离、stub 数据），测试可能「通过但环境已变」 |
| Protocol / 接口桩 | `yate/editor_syntax/engine.py:33-49`（`SyntaxBackend`，R2 冻结白名单）、`yate/editor_components/highlighting.py:115-148`（镜像 Textual `refresh` / `set_timer` / `run_worker` 的宿主协议）、`yate/editor_components/view.py:63-70` | 不可删：签名即契约 |
| `@override` 覆写 | `yate/editor_components/manual.py:265 get_content_height` | 不可删：pyright `reportImplicitOverride = error` 要求签名一致 |
| 命令回调 | `yate/commands.py:266-612` 一组 `_w(args)` / `_q(args)` … | 不可删：`args` 由命令注册表按固定签名传入；除非同步改注册表契约 |
| Textual 回调 | `yate/app.py:186 watch_theme(_theme)`；`yate/editor_components/chrome.py:163,313`、`diff/pane.py:282`、`terminal.py:266`、`view.py:177,239` 的 `on_resize(_event)` / `on_focus(_event)`；`diff/screen.py:164 _pane_changed(event)` 带 `@on(...)` | 待测可删：`invoke`（`textual/_callback.py:45-59`、`message_pump.py:829`）按形参个数裁剪实参，0 参数形态可行，但须逐个跑 pilot 验证 |
| 纯内部签名候选 | `yate/cmdline_completions.py:22 session`、`yate/editor_components/file_manager/model.py:184 sort_key`、`yate/editor_core/buffer.py:856 language`、`yate/editor_term/pty_proc.py:754,759 owner` | 可删候选：须先列全调用点并同步改位置/关键字实参 |
| 解包占位 | 215 处 `_`（`_, x = ...`、`for _ in ...`） | 不可删：属语义占位，删除会改变解包/迭代结构 |
| 未使用的普通局部名 | 9 处，集中在 `tests/`（如 `tests/test_chunked.py spy.disk_reads`） | 逐条核对：多为计数器/副作用变量，可能是 AST 误报，确认无用后再删 |

## 二、目标（What，原文 4 条）

1. 对 587 个未使用形参与 653 个未使用局部名逐条判定，**能安全删除的全部删除**，
   并同步修正仓内所有调用点（含关键字实参）。
2. 优先收敛 `yate/` 产品代码（70 + 81），其次 `tools/`；`tests/` 只处理确认无
   fixture 副作用、非桩函数签名的部分。
3. 以 `yate/app.py:186` 为首个样例落地：改为无参 watcher，并补一条运行时/pilot
   证据证明主题变更仍会触发重绘。
4. 产出一份「不可删登记表」：`文件:行号 → 类别 → 保留理由`，至少覆盖
   fixture / Protocol / `@override` / 开放 API / 解包占位 / 框架固定签名 六类，
   避免后续重复审计。

## 三、判定口径（硬要求，原文）

**可删**

- 纯内部函数/方法的未使用形参，且全部调用点在仓内可同步调整（位置与关键字两种
  传参都要核）。
- 赋值后从未读取、且无副作用的局部变量（排除计数器、`nonlocal` 写入、上下文
  管理器句柄）。
- Textual `watch_*` / `on_*` / `@on(...)` 回调：仅当**实测**证明 0 参数形态仍被
  框架调用、且对应 pilot/渲染用例通过时才删。

**不可删（登记理由，不删）**

- pytest fixture 形参、monkeypatch 桩函数与回调签名（调用方按位置/关键字传参，
  删了即 `TypeError`）。
- `@override` 覆写、开放 API（`python-coding-style.md` §1.2）、插件手册
  `yate/docs/extensions.*.md` 引用的成员、跨仓/插件可调用签名。
- Protocol 方法签名、`Callable` 类型别名约束的回调、ctypes / CONPTY / 线程
  `target` 等外部固定签名。
- `_` 解包占位与 `for _ in ...`；`_*` 形参若属框架固定签名则保留下划线写法
  （它本来就是「有意忽略」的惯用表达，且 pyright strict 不报未使用参数）。
- 任何需要靠 `# type: ignore` / `# noqa` / 新增架构守卫豁免才能成立的删除。

## 四、约束与红线（原文）

- 不改变任何公开 API、插件 API、CLI 行为、函数语义与返回类型；`git diff` 只含
  签名与局部赋值删除，不夹带逻辑改动。
- 依赖方向与架构边界（R1-R15）不变；不新增 `Any`、`TYPE_CHECKING`、`Protocol`、
  `# type: ignore`，不新增 `NON_ASCII_COMMENT_EXEMPT` 等守卫豁免。
- 注释与 docstring 保持英文 ASCII（`misc-rules.md` §四）；双语手册 / CHANGELOG 仅在
  行为变化时同步。
- 不引入 linter（ruff / ARG\*）、不改 `pyproject.toml` 来「制造」告警。
- 提交信息遵守 `git-commit-message.md`，分波提交、只提交不推送；
  **原文写「工作分支以 `develop` 为 parent」**。

## 五、验收标准（原文 5 条）

1. 全量门禁退出码 0：

   ```powershell
   .venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
   .venv\Scripts\python.exe -m pytest tests/ -q -n auto
   .venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
   .venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
   .venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
   ```

2. 并行下若有时序 flake，按 `python-coding-style.md` §4.7 用 `-n 1` 复核并修用例，
   不得记成「偶发」。
3. 每处删除附「调用点清单 + 改动前后行为一致证据」；Textual 回调类附运行时探针
   或 pilot 断言，证明 0 参数形态确实被调用。
4. 覆盖率不低于 75%、架构测试 37 passed、冒烟全通过、changelog check 通过。
5. 「不可删登记表」与最终删除清单同时交付，数量可对账；禁止按 AST 粗扫的
   587 / 653 直接全删。

## 六、非目标（原文）

- 重命名、性能优化、架构/分层调整。
- 未使用导入清理、`_` 解包占位批量替换、pytest fixture 重构（另案）。
- 为消除告警新增任何豁免注释或改动门禁配置。

## 七、风险（原文）

- 关键字调用或第三方扩展按形参名传参 → 删形参后 `TypeError`，且未必被现有用例覆盖。
- fixture 形参误删 → 测试隔离静默失效（用例仍绿但环境已变）。
- `on_*` / `watch_*` 改签名 → 框架分派形态变化，必须跑对应 pilot/主题切换用例。
- 解包占位 `_` 误删 → 解包失败或语义变化。
- AST 粗扫含嵌套作用域与协议桩误报，**数字只是规模估计，不是清单**。

## 八、【领会】环境事实（供规划者使用，非分析结论）

| 项 | 实测值 |
| --- | --- |
| 主工作区 | `master` HEAD `fb3c398`，与 `origin/master` 同步，工作树干净 |
| master HEAD 规则 | `git show master:.trae/rules/task-orchestration.md` 已为单主干 `master` 口径，`develop` 弃用 |
| 本任务 worktree | 仓库同级目录 `yate-unused-symbols-cleanup`，独立 `.venv` |
| 本任务分支 | `feature/enh-unused-symbols-cleanup`，parent 为 `master` |
| 命名依据 | `task-orchestration.md` §二.1（唯一规范来源）；类型前缀取 issue 标题 `ENH` |
| 待规划者登记 | issue §四「以 `develop` 为 parent」与 `task-orchestration.md` §二.1 冲突，须在方案/评审记录显式登记偏离及依据 |
| 无人值守 | 用户本次显式指令「所有问题无须过问」，【批准】按通过处理，子代理一律 `bypassPermissions` |
