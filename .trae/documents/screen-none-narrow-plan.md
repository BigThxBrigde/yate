# screen-none-narrow-plan

> 状态：已批准（用户明确指示"新建分支和 worktree 执行"，本档即执行依据）｜
> 分支：`ref/screen-none-narrow`（基于 `fix/scrollbar-style-unify` @ `2c545d4`）｜
> worktree：`../yate-screen-none-narrow`
> 执行方式备注：`plan-architect-designer` spawn 失败（定义模型 `qwen-3.7-plus` 运行时未注册，
> `Model "qwen-3.7-plus" not found`；task 工具无 spawn 时指定模型参数，回退规则
> `task-orchestration.md` §1.3.5 的"spawn 指定模型"在本运行时无法落地），按 §三 兜底由
> 主代理亲自设计，如实标注。

## 一、目标与非目标

**目标**

1. yate 自有类型注解中所有 `Screen[object]` / `Screen[Any]` 收窄为 `Screen[None]`
   （yate 全部浮层屏均为 `ModalScreen[None]`，类型面如实反映领域事实）；
2. 顺带消除因此不再需要的 `typing.Any` 导入与 `# noqa: Any` 注释；
3. 新增 AST 守卫防回归（与既有 `test_app_annotations_are_precise` 同型）。

**非目标**

- 不改 Textual 上游类型（`App.screen -> Screen[object]` 是第三方声明，只能在其边界处
  `cast`，见 python-coding-style §4.4：cast 优于 ignore）；
- 不改 `SpawnFn = Callable[..., Worker[object]]`（Worker 结果类型与 Screen 无关，超范围）；
- 不改 `push_screen: Callable[..., object]` 注入注解（无 `Screen[...]` 下标，不属本次收窄面）；
- 零行为变更（`cast` 仅作用于类型检查，运行时为无操作）。

## 二、调研取证（文件:行号级事实，已在新 worktree 复核）

### 上游类型（不可改，cast 的唯一合法边界）

- `App.screen` 属性声明为 `-> Screen[object]`
  （`.venv\Lib\site-packages\textual\app.py:1627`）；
- `App.push_screen` 为泛型重载：`screen: Screen[ScreenResultType]` +
  `callback: ScreenResultCallbackType[ScreenResultType]`
  （`app.py:2876-2902`）——传 `Screen[None]` 时类型参数推断为 `None`，类型相容。

### yate 自有出现点（全仓 `Screen\[` 扫描复核完毕，无遗漏）

| # | 位置 | 现状 | 处置 |
|---|---|---|---|
| 1 | `yate/editor.py:534-536` | `def current_screen(self) -> Screen[object]: return self.app.screen` | 返回类型改 `Screen[None]`；实现处对上游宽型 `cast`（唯一合法边界，附英文理由注释）；需补 `cast` 导入 |
| 2 | `yate/flows/overlay_flows.py:44` | `current_screen: Callable[[], Screen[object]]` | 改 `Callable[[], Screen[None]]` |
| 3 | `yate/flows/overlay_flows.py:84-88` | `push(..., screen: Screen[Any], callback: Callable[[Any], None] \| None = None)  # noqa: Any` | 改 `screen: Screen[None]`、`callback: Callable[[None], object] \| None`；删除 `# noqa: Any`；`Any` 导入（`overlay_flows.py:15`）随之移除 |
| 4 | `yate/flows/__init__.py:36` | `type OverlayPusher = Callable[[Screen[Any]], None]  # noqa: Any` | 改 `Callable[[Screen[None]], None]`；删除 noqa 与 `Any` 导入（`flows/__init__.py:21`，文件内已无其它使用点）；注释补一句"every yate overlay is ModalScreen[None]" |
| 5 | `tests/test_changelog_view.py:68` | `current_screen=lambda: app.screen` | 改 `lambda: cast(Screen[None], app.screen)`；`cast` 已在 `test_changelog_view.py:12` 导入，需补 `from textual.screen import Screen` |

### 相容性核验

- `current_screen` 消费方仅做 isinstance 判断（`overlay_flows.py:119/143/231`：
  MarkdownDocScreen / DiffScreen / ScreensaverScreen），收窄零行为影响；
- `OverlayPusher` 消费方 `shell_flows.py` / `lsp_sync.py` 只 push
  `OutputScreen`（`ModalScreen[None]`），相容；
- `overlay_flows.push` 的 7 处调用方（同文件 `:102/:111/:121/:126/:131/:176/:192/:249`）
  传入屏均为 `ModalScreen[None]` 且均不传 callback，相容；
- 注入点 `editor.py:241`（`current_screen=ed.current_screen`）两侧同步收窄，相容；
- `tests/test_changelog_view.py:68` 的 lambda 是唯一测试面注入点。

## 三、备选方案与否决理由

**方案 A（采纳）：自有注解收窄 + 上游边界处 `cast`**

如 §二表。类型面如实、`Any` 清零、cast 仅出现在第三方宽型边界并有注释说明。

**方案 B（否决）：保持 `Screen[object]`，调用点逐个 isinstance 收窄**

把收窄负担转嫁给每个消费方，`current_screen` 的语义（"当前浮层屏"）在类型上失真；
用户明确要求收窄。否决。

**方案 C（否决）：`cast` 换成 `# type: ignore` / pyright ignore**

python-coding-style §4.2 / §4.4 明令禁止 ignore、要求 cast。否决。

## 四、分步实施

### 步骤 1：四文件注解收窄

- **输入**：§二表 5 处（4 个源文件 + 1 个测试文件）
- **输出**：pyright 对 `Screen` 相关注解零宽型；运行时零变更；
- **验收命令**：
  
  ```powershell
d:\Programming\yate-screen-none-narrow\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
  d:\Programming\yate-screen-none-narrow\.venv\Scripts\python.exe -m pytest tests/test_changelog_view.py tests/test_architecture.py -q --cov-fail-under=0

  ```

### 步骤 2：新增 AST 守卫用例

- **输入**：`tests/test_architecture.py`（仿既有 `test_app_annotations_are_precise` 的
  AST 扫描模式）
- **改动**：新增 `test_screen_annotations_are_precise`——AST 扫 `yate/**` 全部
  `AnnAssign` / 参数与返回值注解，禁止 `Screen[object]` 与 `Screen[Any]` 下标形态
  （`Screen[None]` 是唯一精确形态；负向演练：回填一处违规确认拦截后还原）；
- **输出**：回归守卫；
- **验收命令**：
  
  ```powershell
  d:\Programming\yate-screen-none-narrow\.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q --cov-fail-under=0
```

### 步骤 3：全量门禁（主代理亲自跑）

```powershell
d:\Programming\yate-screen-none-narrow\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
d:\Programming\yate-screen-none-narrow\.venv\Scripts\python.exe -m pytest tests/ -q --cov-fail-under=75
```

- **输出**：退出码 0；回填本档；分步提交（`ref(flows)` / `test(architecture)` / `docs(plans)`）。

## 五、风险清单与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| Textual 运行时可能推入内部屏（非 `Screen[None]`），cast 语义失真 | 低 | cast 仅影响静态检查；yate 不触发 Textual 内置屏；守卫注释与 cast 处注释已说明前提 |
| Textual 升级重载 `App.screen` 返回类型 | 低 | cast 处注释标注前提；升级审查流程（`keyproto/textual_internals.py` 先例）会扫到 |
| 泛型 `push_screen` 对 `Callable[[None], object]` 回调不兼容 | 低 | 全部调用方均不传 callback；`_push_screen` 注入注解为 `Callable[..., object]` 宽接，pyright 实测为准 |

**回滚路径**：单 commit revert，无数据/配置迁移。

## 六、执行记录（回填）

- [x] 步骤 1：实施 + 验收
  - `yate/editor.py`：补 `from typing import cast`；`current_screen` 返回类型
    `Screen[object]` → `Screen[None]`（:535），实现处 `cast("Screen[None]", self.app.screen)`（:540），
    附英文注释说明"yate 推入的屏均为 `ModalScreen[None]`，`App.screen` 上游声明为
    `Screen[object]`，故在此第三方边界断言（cast 优于 ignore）"。
  - `yate/flows/overlay_flows.py`：删除 `from typing import Any`（原 :15）；
    `current_screen` 注入注解 → `Callable[[], Screen[None]]`（:43）；
    `push` 签名 → `screen: Screen[None]` / `callback: Callable[[None], object] | None = None`
    并删去 `# noqa: Any`（:83-87）。
  - `yate/flows/__init__.py`：删除 `from typing import Any`（原 :21）；
    `OverlayPusher` → `Callable[[Screen[None]], None]` 并删去 `# noqa: Any`，
    注释补"every yate overlay is a `ModalScreen[None]`"（:34-37）。
  - `tests/test_changelog_view.py`：补 `from textual.screen import Screen`（:16）；
    注入点 `current_screen=lambda: cast(Screen[None], app.screen)`（:70）。
  - 实测验收：
    - `python -m pyright yate/ tests/ tools/` → 退出码 0，`0 errors, 0 warnings, 0 informations`；
    - `python -m pytest tests/test_changelog_view.py tests/test_architecture.py -q --cov-fail-under=0`
      → 退出码 0，46 passed。
- [x] 步骤 2：守卫测试 + 负向演练
  - `tests/test_architecture.py` 新增 `_stringified_imprecise_screen` /
    `_imprecise_screen_annotations` / `test_screen_annotations_are_precise`
    （仿 `_imprecise_app_annotations` / `test_app_annotations_are_precise` 的 AST 扫描：
    `Subscript` 的 `Screen` 名/属性 + `AnnAssign` + `ast.arg` + 函数 `returns` 位置，
    并覆盖字符串化前向引用；仅允许 `Screen[None]`）。
  - 负向演练：临时把 `yate/flows/overlay_flows.py:43` 回填为
    `Callable[[], Screen[object]]` → 守卫用例 FAILED，
    `AssertionError: (WindowsPath('.../yate/flows/overlay_flows.py'), [43])`；随后还原。
  - 实测验收：`python -m pytest tests/test_architecture.py -q --cov-fail-under=0`
    → 还原前 1 failed（演练预期），还原后退出码 0，36 passed。
- [x] 步骤 3：全量门禁（pyright / pytest 退出码）
  - `python -m pyright yate/ tests/ tools/` → 退出码 0，`0 errors, 0 warnings, 0 informations`；
  - `python -m pytest tests/ -q --cov-fail-under=75` → 退出码 0（后台运行 + 退出码落盘
    `.full_pytest.exit` 核实为 `EXIT=0`，日志跑到 `[100%]` 无 F/E 标记；
    该套件在本机极慢，约 75 分钟量级，中途多次出现单用例长时间无进度但 `UserModeTime`
    持续增长，非死锁）。
  - 备注：本次不为取摘要行而重启全量（首跑已给出权威退出码 0）；
    通过数/覆盖率百分比未取得（`-q` 摘要未落盘），如需精确数字由主代理收尾时复跑或看 `coverage.xml`。
- [x] 提交记录（按要求未执行任何 git commit，由主代理收尾统一处理：`ref(flows)` /
  `test(architecture)` / `docs(plans)`）
- [x] 【审核】`code-review-expert` 评审 —— **PASS（无 blocker / major / minor）**。
  评审员实测：pyright 全仓 0 诊断 exit 0；`pytest test_architecture + test_changelog_view`
  → 47 passed exit 0；冒烟 `python -m tools.smoke_test run` → **112/112 scenarios,
  1354/1354 checks, exit 0**；守卫负向有效性另以内存 AST 模拟复核（6 种违规形态全命中、
  `Screen[None]` 与 docstring 零误报）。评审 skill（python-code-review / TRAE-code-review）
  本运行时未注册，按角色定义内置 7 维度框架完成并附自我批判，如实标注。
- [x] 【收尾】主代理独立复核（不引用成员自述数字）—— pyright 全仓 **0 errors, exit 0**；
  全量 `pytest tests/ -q --cov-fail-under=75` **一次通过 exit 0**（本次无 timing 偶发；
  成员沙箱中约 75 分钟属其环境慢，非代码问题）。
- [x] 提交记录 —— 主代理分三笔提交（只提交不推送）。
