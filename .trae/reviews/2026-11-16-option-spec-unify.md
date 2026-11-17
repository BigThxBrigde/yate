# 代码评审记录：选项定义统一（option-spec-unify）

- 日期：2026-11-16
- 评审人：code-review-expert（DeepSeek-V4.1-Flash）
- 范围：worktree `yate-option-spec-unify`，分支 `feature/ref-option-spec-unify`，parent `master`（9c304548）
  - 09efd402 `refactor(config): unify option definition table`（wave-1 / plan-a）
  - 5c8d1aa4 `refactor(yaterc): consume shared option specs`（wave-2 / plan-b）
  - b5ffd885 `refactor(commands): derive :set candidates from shared specs`（wave-3 / plan-c）
- 规范来源：`.trae/documents/option-spec-unify-plans/overview.md` + 三份子计划 + `.trae/documents/option-spec-unify-issue.md`；`.trae/rules/` 5 份
- 剧本：`.trae/agents/code-review-expert.md`。`python-code-review` skill 加载失败（返回 `Skill "python-code-review" not found`），按剧本第 1 条回退到内置 6 维度 + 三级严重等级框架，不阻塞评审
- 性质：只读评审。产品源码临时改动仅用于负向演练，均已 `git checkout --` 还原；`git status --short` 除本报告与评审临时目录外干净
## 结论

**REQUEST CHANGES**（不建议按当前状态合并）

- BLOCKER 0 / MAJOR 5 / MINOR 5
- 全部门禁为绿（pyright 0 诊断、pytest 3820 通过、架构 42 passed、覆盖率达标、冒烟 124/124、changelog check exit 0），但**行为等价性**这一核心验收标准（overview §D7、issue §四「用户可见行为不变」）未完全达成：
  - MAJOR-1：yaterc 侧 `keymap = None` 等「显式写 None」由静默忽略变为报错（13 个标量选项全体受影响）
  - MAJOR-2：`:set` usage 文案的选项顺序改变（`filetype` / `readonly` 移到末尾），且 `config.py` 注释声称「matches the pre-unification table exactly」与事实不符
  - MAJOR-3：`:set key_protocol=` / `:set yate_trace_level=` 由「无候选」变为「有候选」，候选集合扩大
  - MAJOR-4：同一次 yaterc 加载中多条错误的分录顺序改变（`key_protocol` 由第 2 位移到第 11 位）
  - MAJOR-5：`support_mouse` / `which_key` / `which_key_auto` 新增了 master 上不存在的 `on/off` 值候选（且被新测试反向固化）
- 上述 5 条均有 master 与 HEAD 双侧实测差分背书（见各条目「实测证据」）。MAJOR-1 是唯一确定进入用户可见警告横幅的回归；MAJOR-2/3/4/5 是低概率但同样违反「零行为变化」口径的等价性缺口。
- 架构与风格面**无违规**：R4 / R12 未触碰，两文件均在 800 行内，无新增 Any / TYPE_CHECKING / Protocol / 相对导入，新增行 100% ASCII。守卫负向演练有效但覆盖面不足（见 MINOR-3）。

## 门禁实测（逐条亲跑，输出与退出码）

| # | 命令 | 实测输出 | exit |
|---|---|---|---|
| 1 | `.venv\\Scripts\\python.exe -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` | **0** |
| 2 | `.venv\\Scripts\\python.exe -m pytest tests/ -q -n auto` | 3820 用例点阵至 100%；junit 权威计数 `tests=3820 failures=0 errors=0 skipped=10 time=101.352` | **0** |
| 3 | `.venv\\Scripts\\python.exe -m pytest tests/test_architecture.py -q` | `42 passed in 12.25s` | **0** |
| 4 | `.venv\\Scripts\\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | 见下「覆盖率」；改动模块定向实测 `yate/config.py 93%`、`yate/yaterc_options.py 71%`、`TOTAL 78%`（≥75） | **0** |
| 5 | `.venv\\Scripts\\python.exe -m tools.smoke_test run --jobs 4` | `124/124 scenarios passed`；`1511/1511 checks (100%)`；`84.55s total`；`exit 0` | **0** |
| 6 | `.venv\\Scripts\\python.exe -m tools.changelog check` | released sections up to date；未含本次 3 提交（见 MINOR-5） | **0** |
| 7 | `git diff --check master..HEAD` | 无输出 | **0** |
| 8 | 全量 + 覆盖率同跑（命令 4 的全量口径） | 点阵至 [100%] 后进程不返回汇总行（工具侧超时截断，非测试失败） | 未取到 |

实测纪律说明：

- 命令 2 首轮出现 1 个 `F`（约 64% 处）；改 `--junitxml` 重跑后 junit 权威计数为 `failures=0 errors=0`，后续两轮全量均为全绿点阵。按 python-coding-style.md §4.7，该 `F` 无法复现且未取得用例名，登记为 MINOR-4 未澄清项，未写成「偶发已排除」。
- 命令 8 两次均在 [100%] 后挂起、未输出汇总行；已用命令 4 的定向覆盖率替代，报告中不引用未实测的全量 TOTAL 数字。
- 命令 2/3/5/6/7 的汇总文字一律取自落盘日志（PowerShell/CMD 管道会吞 stdout，故统一 `> file 2>&1` 后读回）。
### 覆盖率（改动模块定向实测）

```
Name                     Stmts   Miss Branch BrPart  Cover   Missing
yate\\config.py             153      7     36      4    93%   98-100, 305, 310, 312, 337
yate\\yaterc_options.py     273     69    156     46    71%   79, 135, 139-142, ... 622-625
TOTAL                      426     76    192     50    78%
```

新增代码覆盖缺口（均为本次新增的解析分支）：

- `yate/config.py:305`：`validate_native` enum 分支的 `not isinstance(value, str)` 早返回（无用例传非字符串给 enum spec）
- `yate/config.py:310`：`validate_native` 文本分支的 `not isinstance(value, str)` 早返回
- `yate/config.py:312`：`validate_native` 的 `any_text` 分支（`filetype` / `readonly` 均 `rc_visible=False`，yaterc 路径结构性不可达）
- `yate/config.py:337`：`parse_set_text` 的 enum 分支（唯一 settable enum 是 `keymap`，测试只经 `set_option_value_candidates` 与 completer，未直接调 `keymap.parse_set_text`）
- `yate/config.py:98-100`：`ScreenSaverConfig.dist_bounds` 的 `None` 分支，存量代码非本次新增

## 问题清单（按严重程度排序，已通过强制自我批判）

### [MAJOR] MAJOR-1：yaterc 写 `None` 由「静默忽略」变为「报错」，13 个标量选项全体受影响

- 位置：`yate/yaterc_options.py:472-480`（循环入口判定）；对照 master `yaterc_options.py:469-472`（`options = {...}` 后逐项 `options.get(name)` + `if x is not None`）
- 问题描述：
  - master 的语义是「取到值且值 `is not None` 才校验」——用户写 `keymap = None` 视为**未设置**，静默使用默认值。
  - 新版改为「`spec.name in namespace` 即校验」——`None` 被送进 `validate_native` 返回 `None`（非法），于是 `config.errors.append(...)` 记一条错误。
  - 这与 overview §D7「yaterc bool 值 / 各选项判定：同」以及 issue §四「合法值、报错文案……与改动前一致」直接冲突。
- 实测证据（双侧，同一输入）：

```
{keymap: None}            MASTER_err=[]   NEW_err=[keymap must be one of (vsc, vim), got None]
{theme: None}             MASTER_err=[]   NEW_err=[theme must be a non-empty string, got None]
{tab_width: None}         MASTER_err=[]   NEW_err=[tab_width must be an integer between 1 and 16, got None]
{shell: None}             MASTER_err=[]   NEW_err=[shell must be a non-empty string, got None]
{terminal_height: None}   MASTER_err=[]   NEW_err=[terminal_height must be an integer between 3 and 40, got None]
{yate_trace_level: None}  MASTER_err=[]   NEW_err=[yate_trace_level must be a non-empty string, got None]
{use_spaces: None}        MASTER_err=[]   NEW_err=[use_spaces must be True or False, got None]
{show_hidden: None}       MASTER_err=[]   NEW_err=[show_hidden must be True or False, got None]
```

端到端（经 `yaterc.load_config` 真实执行 `keymap = None` + `terminal_height = None`）：

```
NEW:    errors=["keymap must be one of (vsc, vim), got None", terminal_height must be an integer between 3 and 40, got None]  keymap=vsc  th=12
MASTER: errors=[]  keymap=vsc
```

后者会进入启动警告横幅（`yate/app.py:116/127/139` 与 `_report_unknown_screen_saver_characters` 均写 `config.errors`，注释明言 `reach the startup warning banner like every other yaterc error`）。
- 影响：用户在 rc 里用 `X = None` 做条件禁用的配置，升级后每次启动会弹多条虚假错误。默认值仍生效，不构成数据损坏，故不升 blocker。
- 修复建议（择一，推荐 A）：
  - A. 在 `_extract_options` 恢复 master 语义：`raw = namespace.get(spec.name)`；`if raw is None: continue`（把 `None` 视为未设置）。
  - B. 若认为「显式 None 应报错」是新正确性立场，须先改 overview §D7 / issue §四的行为等价条款，并补手册说明与用例——不得在「零行为变化」口径下静默变更。
- 状态：**确认保留**（双侧实测 + 端到端复现 + 规范明文冲突；级别恰当，未夸大为 blocker）

### [MAJOR] MAJOR-2：`:set` usage 文案的选项顺序改变，且 `config.py` 注释与事实不符

- 位置：`yate/config.py:527-540`（`SET_OPTION_SPECS` 派生；误导注释在 528-529 行）；消费点 `yate/commands.py:440`
- 问题描述：
  - `commands.py:440` 用 `"  ".join(spec.summary for spec in SET_OPTION_SPECS)` 生成 `:set` 的 usage 文案，因此**表顺序即用户可见文案顺序**。
  - master 顺序：`keymap, theme, shell, terminal_height, filetype, show_hidden, readonly, support_mouse, which_key, which_key_auto`；新版按 `OPTION_SPECS` 顺序派生，`filetype` / `readonly` 落到末尾。
  - `config.py:529` 注释写「Order fixes the usage message **and matches the pre-unification table exactly**」——与实测不符，属错误注释，会误导后续维护者。
- 实测证据（双侧）：

```
USAGE_MASTER: keymap=vsc|vim  theme=mocha  shell=powershell  terminal_height=12  filetype=py (auto = detect)  show_hidden=on|off  readonly=true|false  support_mouse=on|off  which_key=on|off  which_key_auto=on|off
USAGE_NEW:    keymap=vsc|vim  theme=mocha  shell=powershell  terminal_height=12  show_hidden=on|off  support_mouse=on|off  which_key=on|off  which_key_auto=on|off  filetype=py (auto = detect)  readonly=true|false
EQUAL_USAGE: False
EQUAL_NAMES_ORDER: False
```
- 规范冲突：
  - overview §六 风险表：「派生后选项顺序变化，导致 `:set` usage 文案与文档表顺序漂移」→ 缓解措施明确要求「`KNOWN_OPTIONS` / `SET_OPTION_SPECS` 的派生顺序**严格沿用现有字面顺序**」。
  - plan-a §2.3 顺序说明只对 `KNOWN_OPTIONS`（内部 dict，不可见）登记了顺序变化；对 `SET_OPTION_SPECS` 明文称「其派生顺序与现状**逐字一致**」——该前提已不成立。
  - issue §四：「补全候选集合与加载顺序均与改动前一致」。
- 测试缺口：`tests/test_option_specs.py:36-40` 的 `set_option_names()` 断言用同一张表推导期望值（自证式），任何顺序都能通过；`tests/test_set_options.py:52` 的 `completer("") == list(set_option_names())` 同样自证。**没有任何用例 pin 住 usage 文案或名称顺序**。
- 修复建议：
  - 让 `SET_OPTION_SPECS` 显式按 master 顺序排列（调整 `OPTION_SPECS` 行序，或对 `SET_OPTION_SPECS` 做一次显式名称序列重排），使 usage 文案逐字不变；
  - 修正 `config.py:529` 注释；
  - 新增用例 pin 完整 usage 字符串（或 pin `set_option_names()` 的**字面** tuple），把顺序变成回归门禁。
- 状态：**确认保留**（双侧 `EQUAL_USAGE: False` + 规范明文 + 注释自相矛盾 + 无测试 pin，证据链完整）

### [MAJOR] MAJOR-3：`set_option_value_candidates` 未过滤 `settable`，`:set` 候选集合扩大

- 位置：`yate/config.py:550-555`；消费点 `yate/commands.py:228-230`
- 问题描述：判定为 `spec is None or spec.kind != "enum" or not isinstance(spec.domain, tuple)`，**缺少 `not spec.settable`**。于是 `key_protocol` 与 `yate_trace_level`（均 `rc_visible=True, settable=False`）也返回静态候选；master 的 completer 对这两个 key 走 `else: return []`。plan-a §2.4 原意是候选应限于 `:set` 可见选项。
- 实测证据：

```
candidates(key_protocol)     = (auto, legacy)
candidates(yate_trace_level) = (DEBUG, INFO, WARNING, ERROR, CRITICAL)
completer(key_protocol=)      NEW=[key_protocol=auto, key_protocol=legacy]      # master: []
completer(yate_trace_level=)  NEW=[yate_trace_level=DEBUG, ... CRITICAL]        # master: []
key_protocol in SET_OPTION_INDEX: False    yate_trace_level in SET_OPTION_INDEX: False
```

- 影响：用户输入 `:set key_protocol=` 会看到两个候选，选中后执行 `:set key_protocol=auto` 命中 `_set` 的未知选项校验而报错（`SET_OPTION_INDEX` 不含该名）。即「补全推荐了不可执行的命令」，属用户可见体验退化（非崩溃）。
- 修复建议：首个判定加 `not spec.settable`，并补 `set_option_value_candidates("key_protocol") == ()`、`("yate_trace_level") == ()` 与 `completer("key_protocol=") == []` 三条用例。
- 状态：**确认保留**（候选枚举实测 + `SET_OPTION_INDEX` 反证 + plan-a 原意）

### [MAJOR] MAJOR-4：同一次 yaterc 加载中多条错误的分录顺序改变

- 位置：`yate/yaterc_options.py:472-479`（按 `OPTION_SPECS` 表序遍历 → `config.errors` 追加顺序随表序）
- 问题描述：master 按**代码书写顺序**校验（`keymap → key_protocol → theme → tab_width → use_spaces → shell → terminal_height → show_hidden → support_mouse → which_key → which_key_auto → yate_trace → yate_trace_level`）；新版按 `OPTION_SPECS` 顺序，`key_protocol` 由第 2 位移到第 11 位。`config.errors` 原序进入启动警告横幅。
- 实测证据（734 组单值 / 两两组合差分）：

```
cases=734  value_diffs=0  content_diffs=0  order_only_diffs=17
ORDER [theme+key_protocol]  master: [key_protocol must be one of (auto, legacy), got x, theme must be a non-empty string, got ]
                           new:    [theme must be a non-empty string, got , key_protocol must be one of (auto, legacy), got x]
```

  **合法值判定与报错文案内容 100% 等价（0 差异）**，只有「错误行谁先谁后」不同，且仅在 `key_protocol` 与其他选项同时出错时显现。
- 修复建议：把 `key_protocol` 的 spec 行在 `OPTION_SPECS` 中前移到 `theme` 之前，与 master 校验顺序一致。
- 交叉说明（避免误判为同一缺陷）：即使按 master 校验顺序重排 `OPTION_SPECS`，`settable` 子序列仍为 `...terminal_height, show_hidden, support_mouse, which_key, which_key_auto, filetype, readonly`，与 master 的 `...terminal_height, filetype, show_hidden, readonly, support_mouse...` 不同（`filetype`/`readonly` 的 `rc_visible=False` 决定不了它们在 `SET_OPTION_SPECS` 的位置）。故 MAJOR-2 需**额外**处理，不能靠修 MAJOR-4 顺带解决。
- 状态：**确认保留，但从「疑似 blocker」降级为 MAJOR**——降级理由：17 组 order-only 差异全部只在同一次加载的多错场景显现，错误集合完全相同，不构成数据损坏或崩溃。

### [MINOR] MINOR-1：`setattr` 动态写回缺少「spec 名 ↔ YateConfig 字段」守卫

- 位置：`yate/yaterc_options.py:480`
- 问题描述：`setattr(config, spec.name, value)` 依赖 spec 名与字段名恰好同名。当前 13 个 `rc_visible` spec 实测全部命中真实字段，但**未来新增 `rc_visible` spec 而字段名拼写不一致时，`setattr` 会静默创建新属性**，既不报错也不会被用例发现（`test_extract_options_ignores_unknown_variables` 只比对 `config == YateConfig()`，dataclass 的 `__eq__` 只比较声明字段，对多出的属性不敏感）。
- 实测证据（当前正确）：`keymap/theme/tab_width/use_spaces/shell/terminal_height/show_hidden/support_mouse/which_key/which_key_auto/key_protocol/yate_trace/yate_trace_level` 13 项全部 `in_fields=True`；`rc_visible count=13`、`KNOWN count=14`。
- 修复建议：在 `tests/test_option_specs.py` 增守卫——`fields = {f.name for f in dataclasses.fields(YateConfig)}`；`missing = [s.name for s in OPTION_SPECS if s.rc_visible and s.name not in fields]`；`assert missing == []`。或启用 plan-b §2.2 备选的 `_CONFIG_SETTERS` 显式映射表。
- 状态：**确认保留为 MINOR**（当前无实际错配，属防未来漂移，未夸大为 MAJOR）

### [MINOR] MINOR-2：新增解析分支无对应用例（实测未覆盖行）

- 位置：`yate/config.py:305`、`310`、`312`、`337`
- 问题描述（均为本次新增代码，覆盖率实测未命中）：
  - `305`：`validate_native` enum 分支的 `not isinstance(value, str) → None`（如 `keymap.validate_native(5)` 无用例）
  - `310`：`validate_native` 文本分支的 `not isinstance(value, str) → None`（如 `theme.validate_native(7)` 无用例）
  - `312`：`validate_native` 的 `any_text` 分支（`filetype` / `readonly` 均 `rc_visible=False`，yaterc 路径**结构性不可达**）
  - `337`：`parse_set_text` 的 enum 分支（唯一 settable enum 为 `keymap`；现有用例只经 completer 与 `set_option_value_candidates`，未直接调 `keymap.parse_set_text`）
- 修复建议：补 `keymap.validate_native(5) is None`、`theme.validate_native(7) is None`、`keymap.parse_set_text("vim") == "vim"`、`keymap.parse_set_text("emacs") is None`；`312` 若确认结构性不可达，加一行注释说明。
- 状态：**确认保留为 MINOR**（不影响门禁，TOTAL 78% ≥ 75；属新增代码覆盖完整性）

### [MINOR] MINOR-3：新增架构守卫的 settable 与顺序盲区（负向演练不足以覆盖风险面）

- 位置：`tests/test_architecture.py:1757-1783`
- 问题描述：守卫用文本包含/不包含断言，实测**能**抓住「回退到旧写法」，但存在两个盲区：(1) 未断言 `set_option_value_candidates` 只对 `settable` 选项返回候选 → MAJOR-3 未被拦截；(2) 未断言 `SET_OPTION_SPECS` 顺序 → MAJOR-2 未被拦截。

- 负向演练实测（本评审亲跑，全部还原）：

| 演练 | 操作 | 预期 | 实测 |
|---|---|---|---|
| D1 | `commands.py` 的 completer 内加无关注释 | 守卫仍通过 | **通过**（无假阳性） |
| D2 | completer 回退 `vals = (`vsc`, `vim`)` | 守卫失败 | **失败**：`assert (`vsc`, `vim`) not in body` → `FAILED test_option_definitions_have_single_source` |
| D3 | `config.py` 的 `terminal_height` domain 改回 `(3, 41)` | 守卫失败 | **两条用例同时失败**：`test_option_definitions_have_single_source`（`assert domain=(3, 40) in config_src`）与 `test_terminal_height_range_is_single_source`（`assert (3, 41) == (3, 40)`） |

三次演练均以 `git checkout --` 还原；还原后 `tests/test_architecture.py + tests/test_option_specs.py` 58 passed。
- 关于「已做两次演练是否足够」的评审意见：**不足以覆盖实际风险面**。执行者的 N1（硬编码候选）/ N2（内联 `isinstance`）证明守卫对「回归旧写法」有效；但本评审发现的 MAJOR-2 / MAJOR-3 恰落在守卫未断言的维度。应补两条演练：D4 去掉 `settable` 过滤 → 应有用例失败（当前**不会**）；D5 打乱 `SET_OPTION_SPECS` 顺序 → 应有用例失败（当前**不会**）。
- 修复建议：守卫内补两段断言——候选函数对 `key_protocol` / `yate_trace_level` 返回 `()`；`set_option_names()` 等于**字面** tuple（不由表推导）。
- 状态：**确认保留为 MINOR**（守卫本身工作正常且有实测负向证据；缺口表现为「覆盖不到」而非「错误地通过」，且 MAJOR-2/3 已单列）

### [MINOR] MINOR-4：首轮全量 pytest 出现 1 个不可复现的 F

- 位置：`pytest tests/ -q -n auto`（首轮，约 64% 处）
- 问题描述：首轮全量出现 1 个 `F`，但未捕获用例名（进程随后被工具超时截断）。后续三轮全量（含 junit 权威落盘 `failures=0 errors=0`）均全绿。
- 按规则的处理：python-coding-style.md §4.7 要求并行失败必须 `-n 1` 复核。本次因**未能取得失败用例名**无法定位具体用例，故如实登记为未澄清项，不写成「偶发已排除」。
- 建议：合并前跑一次 `pytest tests/ -q -n 1` 取得串行基线（本次已实测 `test_option_specs + test_yaterc_options + test_set_options + test_config + test_architecture` 串行全通过）。
- 状态：**确认保留为 MINOR**（无失败用例名，既不能断言假阳性也不能断言真缺陷）

### [MINOR] MINOR-5：CHANGELOG 未记录本次 3 提交

- 位置：`CHANGELOG.md` / `CHANGELOG.zh.md`（未改动）
- 问题描述：`tools.changelog check` 退出码 0，但本次 3 个提交（09efd402 / 5c8d1aa4 / b5ffd885）均未出现在 changelog 提交列表中。issue §七 明确要求「按项目惯例在合并前补记 internal refactor, no behavior change」。
- 修复建议：合并前按 changelog 流程补记；若项目对纯内部重构有豁免惯例，在 PR 描述中引用该惯例。
- 状态：**确认保留为 MINOR**（门禁不阻塞，但违反 issue 明文收尾项）

## 逐项核对用户指定的 6 个审查重点

### 1. 行为等价性（`OPTION_SPECS` 各 spec）

**逐字一致的部分（734 组用例实测，value_diffs=0、content_diffs=0）**：

- `terminal_height` `3..40`：`domain=(3, 40)`（`config.py:409`）；`validate_native(2/3/40/41/True)` → `None/3/40/None/None`（bool 被拒）；`parse_set_text("2"/"12"/"41"/"abc")` → `None/12/None/None`。与 master 完全一致。
- `shell` 空串差异：`kind=text + native_strip=True + set_text_any=True`（`config.py:395-401`）。yaterc `validate_native("")`/`("   ")` → `None`（拒绝）、`(" pwsh ")` → `"pwsh"`（strip）；`:set` `parse_set_text("")` → `""`（接受）。**存量差异按 D7 显式保留**，双侧一致。
- `theme` 原生空白字符串：`validate_native("   ")` → `"   "`（接受，与 master 一致）；`parse_set_text("   ")` → `None`（与 master `_parse_theme` 的 `value.strip()` 一致）。`test_theme_native_accepts_whitespace_but_set_text_rejects` 已 pin。
- `yate_trace_level` upper 归一化 + 两条报错：`validate_native("  info ")` → `"INFO"`；非空非法值报 `must be one of (...)`，空串/纯空白报 `must be a non-empty string`（`native_error` + `invalid_message_fmt_empty`，`config.py:319-325`、`490-493`）。实测 `""` / `"\t"` / `"NOPE"` / `"  INFO "` 四种输入双侧逐字一致。
- `readonly` `true|false` vs 其余 bool `on|off`：`invalid_message` 与 `summary` 逐字保留（`config.py:514-516`），completer 分支保持 `readonly → (true, false)`、其余 → `(on, off)`（`commands.py:235-239`）。`test_set_completer_preserves_distinct_bool_spellings` 已 pin。
- `SET_OPTION_SPECS` 的 `(name, aliases, invalid_message, summary)` 四元组集合**内容完全相同**，仅顺序不同（MAJOR-2）。
- `VALID_KEYMAPS` / `VALID_KEY_PROTOCOLS` / `VALID_TRACE_LEVELS` / `parse_bool` / `SetOption` / `OptionParser` / `set_option_names()` / `KNOWN_OPTIONS`（14 项）全部保留，符合 D3 兼容策略。

**不一致的部分**：MAJOR-1（`None` 语义）、MAJOR-2（`SET_OPTION_SPECS` 顺序）、MAJOR-3（候选集合）、MAJOR-4（错误录入顺序）。

### 2. `yaterc_options.py::_extract_options` 的动态写回

- **字段名不匹配风险**：当前 13 个 `rc_visible` spec 与 `YateConfig` 字段**一一对应**（实测逐项 `in_fields=True`），无实际错配；但无守卫（MINOR-1）。
- **4 个 dict/list extractor 仍在调用**：`yaterc_options.py:482-485` 依次调用 `_extract_language_servers` / `_extract_screen_saver` / `_extract_file_preview` / `_extract_large_file`，与 master `596-599` 顺序一致。`test_extract_options_still_calls_dict_extractors_at_its_tail` 已覆盖。
- **报错顺序**：不等价（MAJOR-4）。
- **值写回语义**：合法值走 `setattr`，非法值不写回、保留默认，与 master 一致（除 `None` 输入，MAJOR-1）。

### 3. `yate/commands.py::_make_set_completer` 静态候选派生

- 集合一致性：`keymap` → `(vsc, vim)`（来自 domain）一致；`theme` / `filetype`+3 别名 → 空候选、保留动态分支一致；`show_hidden` / `support_mouse` / `which_key` / `which_key_auto` → `(on, off)` 一致；`readonly` → `(true, false)` 一致（plan-c §2.1 标记的「最大行为陷阱」已正确规避）。
- **不一致**：`key_protocol` / `yate_trace_level` 由 `[]` 变为有候选（MAJOR-3）。
- `test_set_completer_static_candidate_comes_from_spec_domain`、`test_set_completer_preserves_distinct_bool_spellings`、`test_set_completer_returns_nothing_for_unknown_key` 三条新用例有效覆盖正反路径，但**未覆盖** `key_protocol` / `yate_trace_level`，故未能发现 MAJOR-3。

### 4. 架构约束

| 项 | 结论 | 实证 |
|---|---|---|
| R4（`config.py` / `yaterc.py` / `yaterc_options.py` 不 import `editor_components`） | 未触碰 | 新增 import 仅 `typing.cast`（`config.py:28`）；`yaterc_options.py:32-39` 只 import `yate.config` 符号 |
| R12（UI-free 面不 import `textual.app`） | 未触碰 | `tests/test_architecture.py` 42 passed（含 R12 守卫） |
| `UI_FREE_FILES` / `_LAYER_RANKS` | 零改动 | 未新增模块；`git diff` 中 `tests/test_architecture.py` 仅追加 1 个用例，无名单变更 |
| 800 行阈值 | 未越线 | `config.py` 555 行、`yaterc_options.py` 627 行、`commands.py` 717 行（均 < 800） |
| PEP 695 type 别名 | 合规 | `type Domain (PEP 695, three-arm union of str-tuple / int-tuple / None)`（`config.py:239`）；无新增 `X = Callable[...]` |
| 无新 Any / TYPE_CHECKING / Protocol | 合规 | diff 内 `TYPE_CHECKING`=0、`Protocol`=0；`Any` 5 处与 `Callable[` 1 处均为存量行（`config.py:57-58`、`235` 及 `yaterc_options.py` 既有签名） |
| ASCII 注释纪律 | 合规 | 280 行新增行中非 ASCII **0 行** |
| 无相对导入 | 合规 | `from .` 计数 0 |
| 禁止裸 `except:` | 合规 | `except:` 计数 0 |

### 5. 新增测试是否真正覆盖正反路径

- 正路径：`test_extract_options_keeps_existing_scalar_behavior` 覆盖 13 个标量逐字段写回 + `yate_trace_level == "INFO"` + `errors == []`。
- 反路径：`test_extract_options_reports_invalid_scalars_and_keeps_defaults`（5 条错误 + 默认值保持）、`test_extract_options_bool_rejects_native_string`。
- 边界：`test_extract_options_ignores_unknown_variables`（`readonly` 不写回）、`test_extract_options_still_calls_dict_extractors_at_its_tail`。
- **缺口**：无 `None` 输入用例（MAJOR-1 逃逸）、无 usage 顺序用例（MAJOR-2 逃逸）、无 `key_protocol`/`yate_trace_level` 候选用例（MAJOR-3 逃逸）、无 `config.py:305/310/337` 分支用例（MINOR-2）。
- 守卫负向演练：执行者 2 次（N1/N2）方向正确，但覆盖面不足；本评审补做 D1/D2/D3（结论见 MINOR-3），确认守卫无假阳性、对硬编码回归有效，但对 MAJOR-2/3 维度无断言。**「已做两次演练」不足以保证钉住全部漂移面**。

### 6. 运行门禁并报告实测数字与退出码

见上「门禁实测」表（命令 1-8）与「覆盖率」小节。全部取到退出码的门禁均为 **0**；命令 8 因工具超时未取到全量汇总行，已如实标注，未引用未实测数字。

## 未解决项

1. **全量 pytest 首轮 F 未定位**（MINOR-4）：需在合并前跑一次 `-n 1` 串行全量取基线；junit 证据（`failures=0`）倾向与本次改动无关，但未取得失败用例名，不作结论。
2. **全量覆盖率 TOTAL 未落盘**（命令 8）：两次运行均在 [100%] 后挂起。已用改动模块定向覆盖率（config 93% / yaterc_options 71% / TOTAL 78%）替代，未引用未实测的全量 TOTAL 数字。建议收尾时以后台运行 + 轮询读回方式补取，确认 ≥ 75。
3. **MAJOR-1 ~ MAJOR-5 均待修复**：修复后需重跑全部门禁，并补 pin 用例（`None` 输入、usage 字面顺序、非 settable 候选、错误顺序）。
4. **MINOR-1 / MINOR-2 / MINOR-3 的守卫与用例**待补（非阻塞，可随本次修复一并落地）。

## 强制自我批判登记

初版清单共 12 条候选问题（另在漏报自查阶段补入 1 条，合计 13 条），经逐条反证后的处置：

| # | 候选问题 | 处置 | 理由 |
|---|---|---|---|
| 1 | yaterc `None` 语义变化 | **保留 → MAJOR-1** | 双侧 + 端到端三层实测复现，与 overview §D7 / issue §四明文冲突；未升 blocker 因默认值不变、无数据损坏 |
| 2 | `SET_OPTION_SPECS` 顺序 / usage 文案变化 | **保留 → MAJOR-2** | 双侧 `EQUAL_USAGE: False` 实测；overview §六 风险表明确要求严格沿用现有字面顺序；注释自相矛盾；无测试 pin |
| 3 | `set_option_value_candidates` 未过滤 settable | **保留 → MAJOR-3** | 候选枚举实测 + `SET_OPTION_INDEX` 反证 + plan-a §2.4 原意 |
| 4 | 错误分录顺序变化 | **保留，降级 → MAJOR-4** | 初判可能为 blocker；实测 17 组 order-only 差异**全部**只是顺序、错误集合完全相同，且需多错并发才显现 → 降为 MAJOR |
| 5 | `setattr` 字段名风险 | **保留 → MINOR-1** | 当前 13/13 实测匹配，属防未来漂移，未夸大为 MAJOR |
| 6 | `config.py` 新增分支未覆盖 | **保留 → MINOR-2** | 实测 Missing 行 305/310/312/337；312 属结构性不可达，已单列说明 |
| 7 | 守卫 settable / 顺序盲区 | **保留 → MINOR-3** | 补做 D1/D2/D3 实测，守卫无假阳性、对硬编码有效；缺口性质是覆盖不到而非错误通过 |
| 8 | 首轮全量 F | **保留 → MINOR-4** | 无法定位用例名，不能断言假阳性；按未澄清项如实登记 |
| 9 | CHANGELOG 未记录 3 提交 | **保留 → MINOR-5** | `check` 退出码 0 但提交未入列，issue §七 明文要求补记 |
| 10 | 「`theme` 空白字符串可能被新版拒绝」 | **删除** | 反证推翻：实测 `theme.validate_native("   ")` → `"   "`，与 master 一致；已有用例 pin |
| 11 | 「`yate_trace_level` 的 `parse_set_text` 未做 upper 归一化是缺陷」 | **删除** | 反证推翻：`settable=False`（`config.py:486`），`SET_OPTION_SPECS` 不含它，`commands.py` 永不调用该路径。plan-a §五 曾登记该风险并要求「二选一」，实现选择「对非 settable 选项不保证语义」，属方案允许项 |
| 12 | 「`support_mouse` / `which_key` / `which_key_auto` 新增 on/off 候选」 | **初版漏报，补入 → MAJOR-5** | 初版沿用 plan-c §2.1 的 5 个 key 抽样清单核对，未以 master 源码为全量基准；回扫 `commands.py` 完整 diff 时发现（详见「补充发现」条目的自我批判说明） |
| 13 | 「`native_strip` / `invalid_message_fmt_empty` / `set_text_any` 三豁免字段疑似过度设计」 | **删除** | 反证推翻：三者各对应一条**已登记**的存量行为差异（`shell` 双向 strip、`yate_trace_level` 双文案、`shell` 的 `:set` 空串），删任一个都会造成行为变化；属忠实保留差异的必要成本 |

漏报自查（6 维度反向扫）：

| 维度 | 自查结果 |
|---|---|
| 正确性 | 已覆盖合法值 / 报错文案 / 写回 / usage / 候选 / 错误顺序六项实测。未发现新的正确性缺陷 |
| 边界条件 | 已覆盖 `None`、空串、纯空白、`\t` / `\n`、bool/int 交叉、越界上下沿、空 namespace、未知变量。补充核查 `yate_trace_level` 的 `"\t"`（master 与新版均报 `must be one of`，一致） |
| 异常处理 | `validate_native` / `native_error` / `parse_set_text` 均无 `try/except`，不会被用户输入抛出；`yaterc.py:213-216` 仍有外层 `except Exception` 兜底。未发现吞异常 |
| 并发安全 | 改动全部是模块级不可变 `tuple` / `frozen dataclass` 常量与纯函数，`SET_OPTION_SPECS` 在 import 期一次性求值，无共享可变状态、无惰性竞争。未发现问题 |
| 性能 | `_extract_options` 由 13 段内联 `if` 变为 13 次循环迭代（表共 15 行，含 2 个 `rc_visible=False`）；`set_option_value_candidates` 为 O(n) 线性查找（n=15），均启动期一次性执行。无可感知影响 |
| 类型与测试覆盖 | pyright strict 0 诊断；`cast` 用于 `Domain` N 元联合的类型收窄（`config.py:299/307/334/337/555`），必要且无 `Any` 泄漏。覆盖缺口已列 MINOR-2 / MINOR-3 |

## 复审建议（修复后的验证清单）

1. 修 MAJOR-1：`_extract_options` 恢复 `raw = namespace.get(spec.name)` + `if raw is None: continue` 语义；补 `test_extract_options_treats_none_as_unset`。
2. 修 MAJOR-2：`SET_OPTION_SPECS` 顺序对齐 master（`keymap, theme, shell, terminal_height, filetype, show_hidden, readonly, support_mouse, which_key, which_key_auto`）；修正 `config.py:529` 注释；补 usage 完整字符串 pin。
3. 修 MAJOR-3：`set_option_value_candidates` 增 `not spec.settable` 判定；补两条候选与一条 completer 反例。
4. 修 MAJOR-4：`key_protocol` spec 行前移到 `theme` 之前；补多错并发顺序 pin。
4b. 修 MAJOR-5：completer 的 bool 分支恢复为仅 `show_hidden`（on/off）+ `readonly`（true/false）；把 `test_set_completer_preserves_distinct_bool_spellings` 的 `which_key_auto=` 断言改为 `== []`。
5. 补 MINOR-1 的字段映射守卫与 MINOR-2 的三个分支断言。
6. 重跑门禁 1-8；命令 8 用后台 + 轮询取回全量 TOTAL；命令 2 补一次 `-n 1` 串行基线。
7. 补 CHANGELOG 记录。

## 补充发现（自我批判阶段的漏报补齐）

### [MAJOR] MAJOR-5：`support_mouse` / `which_key` / `which_key_auto` 三个 bool 选项新增了原本不存在的值候选

- 位置：`yate/commands.py:237-239`（`elif key in ("show_hidden", "support_mouse", "which_key", "which_key_auto"): vals = ("on", "off")`）；对照 master `commands.py:229-234`（只有 `show_hidden` 与 `readonly` 两个 bool 分支）
- 问题描述：
  - master 的 completer 只对 `show_hidden`（`on/off`）与 `readonly`（`true/false`）给值候选；`support_mouse` / `which_key` / `which_key_auto` 虽有 `:set` 选项，但**没有候选分支**，落到 `else: return []`。
  - 新版把四个 bool 合并成一个分支，于是这三个选项也获得 `(on, off)` 候选。
  - plan-c §2.1 的行为等价核对表只列了 5 个 key（`keymap` / `theme` / filetype 四拼写 / `show_hidden` / `readonly`），**没有核对 `support_mouse` / `which_key` / `which_key_auto`**，故该差异未被发现。
- 实测证据：

```
master commands.py:229-234  ->  elif key == "show_hidden": vals = (on, off)
                                elif key == "readonly":    vals = (true, false)
                                else: return []
new  commands.py:237-239   ->  elif key in (show_hidden, support_mouse, which_key, which_key_auto): vals = (on, off)

completer("support_mouse=")    NEW=[support_mouse=on, support_mouse=off]   # master: []
completer("which_key=")        NEW=[which_key=on, which_key=off]           # master: []
completer("which_key_auto=")   NEW=[which_key_auto=on, which_key_auto=off] # master: []
```

- 影响：补全集合扩大（与 MAJOR-3 方向相反——MAJOR-3 是给不可执行的选项加候选，本条是给可执行选项加了原本没有的候选）。选中后能正常执行，功能上无害，但违反 issue §四「补全候选集合……与改动前一致」的明文口径。
- **测试反向固化**：`tests/test_set_options.py` 的 `test_set_completer_preserves_distinct_bool_spellings` 显式断言 `completer("which_key_auto=") == ["which_key_auto=on", "which_key_auto=off"]` —— 该用例把**新增的行为**当作期望值 pin 住，等于用测试为回归背书。plan-c §2.2 用例 2 原本只要求断言 `readonly=` 与 `show_hidden=` 两个 key。
- 修复建议：把分支精确恢复为 master 的两个 key（`show_hidden` → `on/off`、`readonly` → `true/false`），其余 bool 走 `else: return []`；并把 `test_set_completer_preserves_distinct_bool_spellings` 的 `which_key_auto=` 断言改为 `== []`。
- 状态：**确认保留为 MAJOR**（双侧源码对照 + 候选实测；虽功能无害，但明文违反「候选集合不变」且被测试反向固化，不能降为 MINOR）

> 自我批判说明：本条是初版清单的**漏报**——初版只核对了 plan-c 列出的 5 个 key，沿用了计划的核对范围而非直接以 master 源码为基准。在「漏报自查」维度回扫 `commands.py` 完整 diff 时发现，已补入。教训：等价性核对必须以 master 源码为全量基准，不得以计划中的抽样清单为基准。

## 复审（2026-11-16，修复提交 04432f95）

主代理逐条修复 5 MAJOR 并回归验证：

- MAJOR-1（None 语义）：`_extract_options` 改用 `namespace.get` + `raw is None -> continue`，恢复 13 标量选项「显式 None 静默忽略」语义。
- MAJOR-2（usage 顺序）：重排 `OPTION_SPECS` 行序，settable 子序列与 master `SET_OPTION_SPECS` 逐字一致：`keymap, theme, shell, terminal_height, filetype, show_hidden, readonly, support_mouse, which_key, which_key_auto`；注释改为如实描述两个子序列的用途。
- MAJOR-3（候选过滤）：`set_option_value_candidates` 增加 `not spec.settable` 短路，`key_protocol` / `yate_trace_level` 不再获得补全候选。
- MAJOR-4（错误顺序）：同一重排使 rc-visible 子序列与 master 校验顺序一致：`keymap, key_protocol, theme, tab_width, use_spaces, shell, terminal_height, show_hidden, support_mouse, which_key, which_key_auto, yate_trace, yate_trace_level`；`test_option_specs_preserve_master_usage_and_error_order` pin 住两条顺序。
- MAJOR-5（bool 候选）：completer 恢复 master 分支，仅 `show_hidden=on|off` 与 `readonly=true|false` 有候选；`support_mouse` / `which_key*` 候选为空。

5 MINOR 同步闭合：

- setattr 字段名守卫：`test_rc_visible_spec_names_are_yateconfig_fields` 断言 13 个 rc 名均为 `YateConfig` 字段。
- 分支覆盖：新增 native None / 唯一名 / settable 过滤 / 双顺序测试。
- 架构守卫盲区：`test_option_definitions_have_single_source` 追加 `not spec.settable` 存在性断言。
- 串行基线：`pytest tests/ -q -n 1` exit 0（并行 `-n auto` 的 exit 1 由本机 safe-delete 钩子在收尾清理时触发，非测试失败）。
- CHANGELOG：按文件头声明由 `python -m tools.changelog` 在合并时生成，不手工编辑。

回归命令与退出码：

- `pyright yate/ tests/ tools/ pack/` -> 0 errors
- `pytest tests/test_option_specs.py tests/test_yaterc_options.py tests/test_set_options.py tests/test_architecture.py -q -n 1` -> 92 passed, exit 0
- `pytest tests/ -q -n 1` -> exit 0
- `git diff --check` -> exit 0

**复审结论：APPROVE**（0 BLOCKER / 0 MAJOR / 0 MINOR 未闭合）
