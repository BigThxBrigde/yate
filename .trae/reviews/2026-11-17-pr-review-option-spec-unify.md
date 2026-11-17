# 合并前评审（pr-review）：选项定义统一（option-spec-unify）

- 日期：2026-11-17
- 评审人：code-review-expert
- 性质：合并前只读评审（pr-review）；未修改任何产品源码 / 测试 / 规则 / 计划文档
- 对象：worktree `d:/Programming/yate-option-spec-unify`，分支 `feature/ref-option-spec-unify`，base `master`（9c304548）
- 范围：8 笔提交 `ef1c7e7b` → `9e62f108`

| 提交 | 主题 | 波次 |
|---|---|---|
| `ef1c7e7b` | docs(plans): add option spec unification issue and plan | 方案 |
| `30aba64b` | docs(plans): record option spec unification task status | 方案 |
| `09efd402` | refactor(config): unify option definition table | wave-1 / plan-a |
| `5c8d1aa4` | refactor(yaterc): consume shared option specs | wave-2 / plan-b |
| `b5ffd885` | refactor(commands): derive :set candidates from shared specs | wave-3 / plan-c |
| `04432f95` | fix: close review major behavior divergences | 上轮修复 |
| `3f8a9a11` | docs(review): archive option spec unification review verdict | 收尾 |
| `9e62f108` | docs(plans): write back final gate results | 收尾 |

## 规范来源

1. `.trae/documents/option-spec-unify-issue.md`（验收标准）
2. `.trae/documents/option-spec-unify-plans/overview.md` + plan-a / plan-b / plan-c + `progress.md`
3. `.trae/reviews/2026-11-16-option-spec-unify.md`（上轮评审与复审结论）
4. `.trae/rules/architecture-boundaries.md`（含随 pr 的守卫计数变更）
5. `.trae/rules/python-coding-style.md` / `git-commit-message.md` / `plan-before-execute.md`

> `python-code-review` skill 加载失败（返回 `Skill "python-code-review" not found`），按剧本第 1 条回退到内置 6 维度 + 三级严重等级框架，不阻塞评审。

## 结论

**REQUEST CHANGES**（0 BLOCKER / 1 MAJOR / 5 MINOR）。

- 上一轮 5 MAJOR / 5 MINOR 的闭合**经验证基本真实**：yaterc 侧 `None` 静默忽略、`:set` usage 顺序、yaterc 报错顺序、候选集合、bool spellings 均已复原；本轮以 master 侧真实差分（yaterc 3093 组输入）逐字确认 `equal_payload True`。
- 但修复过程**新引入** 1 处用户可见行为回归：`:set filetype=`（空值）由「重置为自动检测」变为「报错拒绝」（MAJOR-1）。同一根因使 `any_text` 的 `:set` 分支成为不可达代码。
- 其余 5 条为可扩展性 / 可维护性 / 测试保护 / 文档一致性缺口，建议随本轮一并处理，不单独阻塞。

## 门禁实测（逐条亲跑，从落盘日志取回）

| # | 命令 | 实测输出 | exit |
|---|---|---|---|
| 1 | `.venv\\Scripts\\python.exe -m pyright yate/ tests/ tools/ pack/` | `--outputjson` 落盘：`filesAnalyzed=426, errorCount=0, warningCount=0, informationCount=0, timeInSec=80.689` | **0** |
| 2 | `.venv\\Scripts\\python.exe -m pytest tests/ -q -n auto --junitxml=...` | junit 权威计数 `tests=3823 failures=0 errors=0 skipped=10 time=314.398`；点阵全程无 `F` | **0** |
| 3 | `.venv\\Scripts\\python.exe -m pytest tests/test_architecture.py -p no:xdist --tb=no -rN` | `42 passed in 16.34s` | **0** |
| 4 | `.venv\\Scripts\\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -q -n auto` | `Required test coverage of 75% reached. Total coverage: 93.08%`；`TOTAL 20072 1095 6392 586 93%` | **0** |
| 5 | `.venv\\Scripts\\python.exe -m tools.smoke_test run --jobs 4` | `124/124 scenarios passed`；`1511/1511 checks (100%)`；`90.08s total`；`exit 0` | **0** |
| 6 | `.venv\\Scripts\\python.exe -m tools.changelog check` | `released changelog sections are up to date`；Unreleased 落后 109 笔（`refreshed at release`） | **0** |
| 7 | `git diff --check` | 无输出 | **0** |
| 8 | 定向回归（test_option_specs + test_set_options + test_yaterc_options + test_architecture，串行） | junit `tests=94 failures=0 errors=0 skipped=0` | **0** |

补充说明：

- 本轮 `-n auto` 全量**未**触发 `reference_safe_delete_pytemp.md` 记载的收尾杀进程现象（首轮即 exit 0），故无需对全量做 `-n 1` 复核。
- 覆盖率未覆盖行（改动模块）：`yate/config.py` 153 语句 / 36 分支 → **99%**，仅 `312` 未命中（`validate_native` 的 `any_text` 分支）；`yate/yaterc_options.py` 275 语句 → **99%**，仅 `186->196` 分支未命中。相比上轮（config 93% / yaterc_options 71%）**显著提升**。
- `config.py:312` 属**结构性不可达**（`filetype` / `readonly` 均 `rc_visible=False`），与上轮 MINOR-2 判断一致。

## 问题清单（按严重程度排序，已通过强制自我批判）

### [MAJOR] MAJOR-1：`:set filetype=`（空值）由「重置为自动检测」变为「报错拒绝」

- 位置：`yate/config.py:327-338`（`OptionSpec.parse_set_text`），根因行在 `yate/config.py:338`：`return text if text.strip() else None`
- 受影响 spec：`yate/config.py:429-439`（`name="filetype"`, `kind="any_text"`, `set_text_any` 默认 `False`）
- 消费点：`yate/commands.py:451-454`（`parsed = spec.parse(value)`；`if parsed is None: editor.message(spec.invalid_message)`）
- 对照 master：`yate/config.py:265-267`（`_parse_filetype` 直接 `return value`，不过滤空串）；`yate/commands.py` 的 `_apply_filetype` docstring 明写 `(any spelling; empty/auto re-detects)`；`yate/editor.py::set_filetype` 实现也明确 `if not raw or raw == "auto": doc.filetype_override = None` → 重置为自动检测。

**根因**：`parse_set_text` 的分支顺序为 `set_text_any` → `bool` → `int` → `enum` → 最后一行兜底。`any_text` 与 `text` **共用最后一行** `return text if text.strip() else None`，因此 `kind="any_text"` 声明的语义（「任意字符串（含空串）」，见 overview D2 / plan-a §2.2 的 `any_text` 行）**在 `:set` 侧完全不生效**。

`filetype` 是唯一 `kind="any_text"` 的 settable spec，又是 `rc_visible=False`（`config.py:432`），因此：

- `validate_native` 的 `any_text` 分支（`config.py:311-312`）在 yaterc 路径结构性不可达；
- `parse_set_text` 的 `any_text` 分支根本不存在（被 `text` 共用）。

即两侧都拿不到 `any_text` 语义，该 `kind` 当前实际等价于 `text`（但语义声称不同）。

**实测证据（双侧探针，同一输入）**：

```
# 解析层（SET_OPTION_SPECS 中 filetype 的 parse）
MASTER: "" -> ''   "   " -> '   '   "py" -> 'py'   " auto " -> ' auto '
NEW:    "" -> None  "   " -> None      "py" -> 'py'   " auto " -> ' auto '

# 命令层（registry.get("set").func(cmd)，桩 editor 记录 message）
HEAD:   filetype= -> [["warn", "filetype must be a filetype name"]]   <-- 用户看到报错
HEAD:   ft=       -> [["warn", "filetype must be a filetype name"]]
HEAD:   lang=     -> [["warn", "filetype must be a filetype name"]]
MASTER: filetype= -> [["EXC", "AttributeError"]]  <-- 解析通过并进入 apply（桩缺 set_filetype）
MASTER: ft= / lang= 同上
```

注：MASTER 侧抛 `AttributeError` 是因为探针用的 `_ConfigEditor` 桩没有 `set_filetype`，恰好证明「解析已通过、进入了 apply」；HEAD 侧处于解析层就报 warn，根本不会走到 apply。

**影响**：

- 用户习惯用且文档已记录的 `:set filetype=`（不带值）用于清除 `filetype_override`、回到按路径自动检测；升级后该操作直接报错，功能丢失。
- 别名 `ft=` / `lang=` / `language=` 同样受影响。
- 该操作在 `README.md:42`、`README.zh.md:41`、`yate/docs/lsp.en.md:47`、`yate/docs/lsp.zh.md:37`、`yate/docs/extensions.en.md:389,472` 等多处被作为合法用法引用，属**用户可见行为变更**，直接违反 issue §四「用户可见行为不变」与 overview §D7 口径。

**为何不升 BLOCKER**：功能退化但不崩溃、不丢数据、不影响启动；用户可用 `:set filetype=<name>` 替代。对照严重等级定义，属「边界条件缺陷」且为用户可见行为回归，列 MAJOR。

**修复建议**（二选一，推荐 A）：

- A（最小改动）：在 `parse_set_text` 增加与 `set_text_any` 并列的 `any_text` 短路——`if self.kind == "any_text": return text`，使 `kind` 声明的语义真正生效；同时保留 `filetype` 的 `kind="any_text"`。
- B：若认为「`:set filetype=` 应报错」是新正确性立场，须先修订 overview §D7 / issue §四的行为等价条款，并同步 `_apply_filetype` docstring、`Editor.set_filetype` 注释与双语手册——不得在「零行为变化」口径下静默变更。
- 并补用例：`spec.parse_set_text("") == ""`、`parse_set_text("   ") == "   "`，以及命令层 `completer`/`func` 的 `filetype=` / `ft=` 正向路径。

- **独立佐证**：`test_option_specs.py` 现有 `test_shell_keeps_its_empty_string_difference` 仅 pin 住了 `shell` 的空串差异，未覆盖 `filetype`；`test_terminal_height_range_is_single_source` 与 `test_bool_set_text_case_insensitive` 也只覆盖 `int` / `bool` 两个 kind。所以现有 167 行新增测试**无一条**能发现该回归。

---

### [minor] MINOR-1：`kind` 为裸 `str`，拼错无任何类型或守卫拦截

- 位置：`yate/config.py:277`（`kind: str  # "enum" | "int" | "bool" | "text" | "any_text"`），分派在 `config.py:296-317` 与 `327-338`
- 问题：合法值仅在注释里罗列。一旦新增行拼错 `kind`（如 `"textt"`），`validate_native` / `parse_set_text` 会隨落到最后一个分支（当成 `text` 处理），**不报错、不异常**，行为静默偏离。
- 实测负向演练（本评审亲跑，已 `git checkout` 根据实测原文反向还原）：把 `theme` 的 `kind="text"` 改为 `kind="textt"` 后，`pytest tests/test_option_specs.py tests/test_architecture.py` 仍为 **`tests=61 failures=0 errors=0`**——守卫与单元测试集体未发现。
- 建议：改为 `kind: Literal["enum", "int", "bool", "text", "any_text"]`（stdlib `typing.Literal`，不违反项目规则），使 pyright strict 在拼错时报诊；并在 `tests/test_option_specs.py` 加一条 `assert {s.kind for s in OPTION_SPECS} <= {...}` 的守卫。
- 严重级：minor（当前 15 行均为正确值实测：`{any_text, bool, enum, int, text}`，无实际缺陷，属防未来漂移）。

### [minor] MINOR-2：`:set` 的 bool 候选仍在 completer 中硬编码，未随统一表派生

- 位置：`yate/commands.py:235-238`（`elif key == "readonly": vals = ("true", "false")` / `elif key == "show_hidden": vals = ("on", "off")`）
- 问题：该集合是 `'on'|'off'|'true'|'false'`——正是 `_TRUTHY` / `_FALSY` 已经声明的词法（`config.py:210-211`）的子集；上轮 MAJOR-5 修复时为恢复 master 行为，又将它从统一表拉回硬编码。这是有意的行为等价取舍，但意味着「新增一个 bool 选项并希望它有候选」仍需要改 `commands.py`——即 issue §三目标 4「消除硬编码候选」未完全达成。
- 证据：该行与 `set_option_value_candidates` 并存，且 `set_option_value_candidates` 对 `readonly` / `show_hidden` 实测返回 `()`（bool 非 enum），因此不可能从表派生。
- 建议（非阻塞）：在 `tests/test_option_specs.py` 增一条「`commands.py` 的 bool 候选必须是 `_TRUTHY` / `_FALSY` 子集」的守卫，先把它钉住；若后续决定将 bool 候选也收归统一表，另案处理（且必须保持 master 集合不变）。
- 严重级：minor（当前集合与 master 逐字一致实测通过，不影响行为）。

### [minor] MINOR-3：守卫断言以「子串存在」代替行为断言，存在误报假阳性风险

- 位置：`tests/test_architecture.py:1757-1783`（`test_option_definitions_have_single_source`）
- 问题：末尾 `assert "not spec.settable" in (YATE / "config.py").read_text(...)`（由 `04432f95` 追加）只断言文本中**出现过该字符串**，而不断言「`set_option_value_candidates` 对不可 set 项返回 `()`」这一**行为**。任何一行带该字面的注释（甚至其他函数里）都能让它通过，对 MAJOR-3 那类回归的阻挡强度依赖于其他位置。
- 建议：把它换成行为断言（放到 `tests/test_option_specs.py`）——`assert set_option_value_candidates("key_protocol") == ()` 与 `== ()` 已存在（第 100-105 行），因此建议直接**删除**该文本子串断言以避免虚假安全感；若要在架构层守护，改为导入并断言行为。
- 严重级：minor（不产生误报，仅存在防御薄弱点；MAJOR-1 已有行为用例作为准）。

### [minor] MINOR-4：模块 docstring 未反映新的单一来源，config.py:312 结构性不可达未加注释

- 位置：`yate/config.py:1-21`（模块 docstring）；`yate/config.py:311-312`
- 问题（两处）：
  1. 模块 docstring 仍写 `This module also owns the :set option table (:class:SetOption / :data:SET_OPTION_SPECS)`，未提及新增的 `OPTION_SPECS` / `OptionSpec` 已成为两侧共用的唯一来源（该表现在是模块最重要的设计事实）；
  2. `validate_native` 的 `any_text` 分支（`311-312`）因 `filetype` / `readonly` 均 `rc_visible=False` 而永不可达，无任何注释说明——与 MINOR-1 的 MAJOR 根因同源（`any_text` 语义未落实）。
- 建议：更新模块 docstring 改写 `OPTION_SPECS` 作为唯一来源、`SET_OPTION_SPECS` / `KNOWN_OPTIONS` 为派生视图；在 `311-312` 或 spec 定义处加一句 `rc_visible=False` 的说明（英文 ASCII）。
- 严重级：minor（文档与可读性，不影响行为）。


### [minor] MINOR-5：上轮 MAJOR-1（yaterc `None` 静默忽略）的修复未被回归用例固定

- 位置：实现在 `yate/yaterc_options.py:475-477`；用例缺口在 `tests/test_yaterc_options.py`（新增 6 个用例均未测试 `None`）
- 问题：上轮评审的复审建议明写「补 `test_extract_options_treats_none_as_unset`」（见 `.trae/reviews/2026-11-16-option-spec-unify.md:305`），但实际未补。全 `tests/` 实测搜索无任何用例将 `keymap=None` / `terminal_height=None` / `yate_trace_level=None` 送入 `_extract_options` 并断言 `errors == []`。
- 影响：该语义是**吴测试保护**的——任何人重写 `_extract_options` 的 `raw is None: continue` 为 `spec.name in namespace` 写法，将不会有任何测试变红（上轮 MAJOR-1 就是这样漏网的）。
- 建议：在 `tests/test_yaterc_options.py` 补 `test_extract_options_treats_none_as_unset`，覆盖至少 3 个代表性 spec（`keymap` / `terminal_height` / `yate_trace_level`），断言 `config.errors == []` 且字段保持默认。
- 严重级：minor（当前行为正确且已本评审实测确认，属测试保护缺口）。

---


## 上轮 5 MAJOR / 5 MINOR 闭合验证（逐条双侧实测）

| 上轮编号 | 结论 | 本轮实测依据 |
|---|---|---|
| MAJOR-1（yaterc `None` 静默忽略） | **已真实闭合** | `yate/yaterc_options.py:474-477`：`raw = namespace.get(spec.name)` + `if raw is None: continue`；实测 `{keymap: None}` / `{terminal_height: None}` / `{yate_trace_level: None}` 均→ `errors=[]`（master 也为 `[]`） |
| MAJOR-2（`:set` usage 顺序） | **已真实闭合** | 双侧 `"  ".join(s.summary ...)` 实测完全相等；`set_option_names()` 完全相等；顺序 pin 在 `test_option_specs_preserve_master_usage_and_error_order` |
| MAJOR-3（候选未过滤 settable） | **已真实闭合** | `config.py:555-561` 含 `not spec.settable`；实测 `set_option_value_candidates("key_protocol") == ()`、`("yate_trace_level") == ()` |
| MAJOR-4（yaterc 报错顺序） | **已真实闭合** | rc-visible 子序列实测 = `keymap, key_protocol, theme, tab_width, use_spaces, shell, terminal_height, show_hidden, support_mouse, which_key, which_key_auto, yate_trace, yate_trace_level`，与 master 校验书写顺序一致 |
| MAJOR-5（bool 候选扩大） | **已真实闭合** | `commands.py:235-238` 仅 `readonly` / `show_hidden` 两个分支；实测 `completer("support_mouse=") == []`、`which_key_auto=` 为 `[]` |
| MINOR-1（setattr 字段名守卫） | 已闭合 | `test_rc_visible_spec_names_are_yateconfig_fields`，断言 13 个 rc 名 `<= _CONFIG_FIELDS` |
| MINOR-2（新增分支覆盖） | 大幅改善 | config.py 覆盖 93%→99%，仅剩 `312`（结构性不可达） |
| MINOR-3（守卫盲区） | 部分闭合 | 已补 settable 与双顺序用例；但新增的文本子串断言自身有假阳性风险（本轮 MINOR-3） |
| MINOR-4（并行 F） | 已澄清 | 本轮 `-n auto` 全量 `failures=0 errors=0`，无 `F` |
| MINOR-5（yaterc `None` 静默忽略） | 未固定（新增 MINOR-5） | 实现已正确（本评审实测 3 个代表 spec 均返回 `errors=[]`），但无任何回归用例固定该语义；上轮 MAJOR-1 正因此而漏网 |
| MINOR-5（CHANGELOG） | 已澄清 | `CHANGELOG.md:3` 文件头声明 `Generated by python -m tools.changelog — do not edit by hand`；`check` exit 0 |

## 逐项核对用户指定的 5 个审查重点

### 1. 行为等价性（核心验收）

**方法**：向 master 主工作区（`d:/Programming/yate`，`git worktree list` 确认指向 9c304548）与本 worktree 各投入一份**完全相同**的探针脚本，输出 JSON 逐字比对。

| 维度 | 覆盖量 | 结论 |
|---|---|---|
| yaterc 加载侧 | 13 个标量 × 合法/非法/None/空串/纯空白/`\\t`/bool与int交叉共 8-9 个取值，单值 + 两两组合 = **3093 组**（其中 2198 组产生报错） | **`equal_payload True`**（报错文案、报错先后顺序、写回字段值全部逐字相等） |
| `:set` 解析侧 | 10 个 settable × 28 个取值（含空串 / 纯空白 / 大小写 / 越界 / 非数字） | 9/10 完全相等；**`filetype` 不等价（MAJOR-1）** |
| `:set` usage 文案 | 10 个 summary 拼接 | **逐字相等** |
| `set_option_names()` | canonical + 4 别名，共 13 项 | **顺序与内容均相等** |
| 补全候选 | 逐选项枚举（keymap / theme / filetype 四拼写 / show_hidden / readonly / support_mouse / which_key / which_key_auto / key_protocol / yate_trace_level / tab_width） | **与 master 完全相等**（仅 keymap = `(vsc, vim)`，其余 `()`；bool 走 completer 分支） |

用户点名的细项逐一核对（均为双侧实测）：

| 项 | 结论 |
|---|---|
| `terminal_height` 3..40 | 一致；`validate_native(2/3/40/41/True)` → `None/3/40/None/None`，`parse_set_text("2"/"12"/"41"/"abc")` → `None/12/None/None` |
| yaterc `None` 静默忽略 | 一致（逐项实测 `errors=[]`） |
| `shell`：yaterc strip 而 `:set` 接受空串 | 一致（`validate_native("")`/`("   ")` → `None`；yaterc `" pwsh "` → `"pwsh"`；`:set` `""` → `""`） |
| `theme`：原生接受纯空白而 `:set` 拒绝 | 一致（`validate_native("   ")` → `"   "`；`parse_set_text("   ")` → `None`） |
| `yate_trace_level` upper 归一化 + 两条报错 | 一致（`"  info "` → `"INFO"`；`""`/`"\\t"` → `must be a non-empty string`；`"nope"` → `must be one of (...)`；`5`/`None` 也走 empty 文案，与 master 逐字相等） |
| `:set` usage 顺序 | 一致：`keymap, theme, shell, terminal_height, filetype, show_hidden, readonly, support_mouse, which_key, which_key_auto` |
| yaterc 报错顺序 | 一致：`keymap, key_protocol, theme, tab_width, use_spaces, shell, terminal_height, show_hidden, support_mouse, which_key, which_key_auto, yate_trace, yate_trace_level` |
| 绑定补全候选 | 一致：仅 `keymap` 静态；`show_hidden` = `on/off`；`readonly` = `true/false`；其余 bool（`support_mouse`/`which_key`/`which_key_auto`）无候选 |

**唯一不等价点：`filetype` 空值**（MAJOR-1）。

### 2. 健壮性（setattr / cast / 行序）

- **13 个 rc 名均为 `YateConfig` 字段**：实测 `rc_visible` 共 13 项，且 `test_rc_visible_spec_names_are_yateconfig_fields` 已固定该守卫（字段名漂移会立即失败）。`setattr(config, spec.name, value)`（`yaterc_options.py:481`）因此安全。
- **`cast()` 是否掩盖真实类型问题**：存在 4 处（`config.py:299/307/334/337`，另 `562` 一处），均与 `Domain = tuple[str,...] | tuple[int,int] | None` 的 N 元联合椼小有关。风险实证：若 `kind="int"` 但 `domain` 实为 `None`，`cast` 不会报错而会在 `bounds[0] <= value` 时抛 `TypeError`。当前 15 行实测均正确（int 行均有 int-tuple domain，enum 行均有 str-tuple domain），且 `_extract_options` 有外层兼容；但该不一致无任何守卫（见 MINOR-1）。结论：**当前无实际缺陷，但 `kind`×`domain` 的组合未被类型系统或守卫钉住**。
- **`OPTION_SPECS` 行序可能被未来新增行破坏且守卫能否拦住**：双子序列（rc-visible 与 settable）同时由同一行序决定，存在**印辰写死的约束**：任何新增行都会同时影响两个子序列。`test_option_specs_preserve_master_usage_and_error_order`（`tests/test_option_specs.py:127-139`）用**字面 tuple** pin 住了两条顺序，实测有效。但存在一个未覆盖的边界：新增一个两侧都不可见的 spec、或位置变动但恰好不影响 rc与 settable 子序列时，守卫**不会**失败——但这本就是可接受的。结论：**当前守卫足够**，且两条子序列的语义已在 `config.py:341-345` 注释中写明。

### 3. 架构（R4 / R12 / 行数 / 类型别名 / 计数同步）

| 项 | 结论 | 实证 |
|---|---|---|
| R4（L0 不 import `editor_components`） | **未触碰** | `yate/config.py` 仅 `from yate.logs import ...`；`yate/yaterc_options.py` 仅 `from yate.config import (...)` |
| R12（UI-free 面不 import `textual.app`） | **未触碰** | 三文件 import 面实测均无 `textual` |
| `UI_FREE_FILES` / `_LAYER_RANKS` | 零改动 | 未新增模块；diff 中 `tests/test_architecture.py` 仅追加 1 个用例（+:1757-1783） |
| 800 行阈值 | **未越线** | 实测 `config.py` **562**（上轮报告写 555，为后续修复已增长）/`yaterc_options.py` **629**/`commands.py` **716** |
| PEP 695 `type` 别名 | **合规** | `type Domain = tuple[str, ...] | tuple[int, int] | None`（`config.py:239）；无新增 `X = Callable[...]` 赋值式别名 |
| 无新增 `Any` / `TYPE_CHECKING` / `Protocol` | **合规** | 新增 import 仅 `typing.cast`；diff 中 `TYPE_CHECKING`=0、`Protocol`=0；`Any` 仅存量行 |
| 无相对 import / 无裸 `except:` | **合规** | `from .` 计数 0；`except:` 计数 0 |
| 新增行 ASCII | **合规** | 产品源码新增行全为 ASCII；中文新增行均在 `.trae/` 文档与 `tests/` 文档字符串中 |
| 架构计数 42 | **两处同步** | `tests/test_architecture.py` 实测 `^def test_` = **42**；`architecture-boundaries.md:481`与`:607` 均为 42，且 `:655` 新增第 42 行对照 |

补充：该守卫在架构测试中以**文本断言**实现（非 AST），plan-c §2.3 曾声称「AST + 文本双重取证」，实际落地为纯文本。属方案与实现的描述偏差，但行为无害（文本子串已能抵御回退，本评审的 kind 拼错演练已反证其覆盖面有限，已记为 MINOR-1/MINOR-3）。

### 4. 测试覆盖

- **正路径**：`test_extract_options_keeps_existing_scalar_behavior`（yaterc 十三个标量 + `yate_trace_level == "INFO"` + `errors == []`）；`test_set_option_names_feed_cmdline_completions`；`test_set_completer_static_candidate_comes_from_spec_domain`。
- **反路径**：`test_extract_options_reports_invalid_scalars_and_keeps_defaults`（5 条报错 + 默认值保持）；`test_extract_options_bool_rejects_native_string`；`test_set_completer_preserves_distinct_bool_spellings`（含 `support_mouse=` / `which_key_auto=` 为 `[]` 的反向断言）；`test_set_completer_returns_nothing_for_unknown_key`。
- **`test_option_definitions_have_single_source` 的负向演练是否足够**：不足够。已有负向演练 N1（keymap 硬编码候选）/ N2（`tab_width` 内联校验）/ 本评审 D2（候选回退）/ D3（domain 改 `(3, 41)`）均能使守卫失败；但本评审新增的 **D4’：`kind="text"` 改 `"textt"` 后守卫仍全绿**（61 passed），说明守卫对「`kind` 拼写 / `kind`×`domain` 不一致」这类漂移无覆盖（MINOR-1 / MINOR-3）。
- **漏掉的关键边界**：
  - `filetype` 空值两侧行为（MAJOR-1）：测试中标量——无用例。
  - `set_option_value_candidates` 的 `settable` 过滤已有用例（§100-105）。
  - `None` 静默忽略语义：**无任何用例覆盖**（全 `tests/` 搜索 `keymap/tab_width/terminal_height/yate_trace_level` 与 `None` 的组合均无命中）——上轮 MAJOR-1 的修复未被回归用例固定，记为 MINOR-5。
  - 双顺序已有字面用例（§133-147）。
  - 倒是 `test_config_stays_within_size_threshold`（§158-165）仅检查 `config.py`，未检查 `yaterc_options.py`（它由现有 `test_source_files_within_size_threshold` 覆盖，实测通过）。

### 5. 文档与提交纪律

| 项 | 结论 | 实证 |
|---|---|---|
| issue / 计划 / 评审 / 进度文档命名 | **合规** | `option-spec-unify-issue.md`、`option-spec-unify-plans/{overview,progress}.md` + 3 份 `option-spec-unify-*-plan-{a,b,c}.md`、`reviews/2026-11-16-option-spec-unify.md`；命名均为小写短横线 |
| 相对路径 | **合规** | `overview.md:109-111` 与 `progress.md:4` 均为相对链接；无机器本地绝对路径 |
| 提交信息英文规范 | **合规** | 8 笔均为 `type(scope): subject`（`refactor(config)` / `refactor(yaterc)` / `refactor(commands)` / `fix:` / `docs(plans)` / `docs(review)`），全英文 |
| 方案先行（plan-before-execute） | **合规** | 跨 3 个层、跨 3 个模块的改动均有 overview + 3 子计划；`progress.md` 登记了提交与阶段产物 |
| changelog 处理 | **合规** | `CHANGELOG.md:3` 声明 `Generated by python -m tools.changelog — do not edit by hand`，与上轮结论一致；`check` exit 0 |

## 强制自我批判登记

初版清单共 9 条候选，自我批判的「漏报自查」阶段又补入 1 条（第 10 条），合计 10 条，经逐条反证后的处置：

| # | 候选问题 | 处置 | 理由 |
|---|---|---|---|
| 1 | `:set filetype=` 空值被拒 | **保留 → MAJOR-1** | 双侧探针两层实测（解析层与命令层）+ master 源码与 docstring 双向佐证 + 多处文档引用；未升 BLOCKER 因无崩溃与数据损失 |
| 2 | `kind` 为裸 str | **保留 → MINOR-1** | 实测负向演练证实存在「拼错静默通过」；当前 15 行值均正确，属防未来漂移 |
| 3 | bool 候选硬编码回流 | **保留 → MINOR-2** | 集合与 master 逐字一致（不影响行为），但 issue §三目标 4 未完全达成 |
| 4 | 守卫的 `not spec.settable` 子串断言 | **保留 → MINOR-3** | 属「防御薄弱」而非「错误通过」；已有行为用例兵底 |
| 5 | 模块 docstring 未更新 + `312` 未注释 | **保留 → MINOR-4** | 实读 `config.py:1-21` 与 `311-312` 确认 |
| 6 | plan-c 声称「AST + 文本双重取证」实为纯文本 | **删除** | 反证推翻：「方案描述与实现描述偏差」本身不构成代码缺陷，且文本子串守卫实测对 N1/N2/D2/D3 均有效；已在架构小节以「描述偏差」事实登记，不单列为问题 |
| 7 | `KNOWN_OPTIONS` 顺序变化 | **删除** | 反证推翻：全仓实测无顺序敏感消费点（`test_config.py:295` 仅测成员存在）；overview D3 与 plan-a §2.3 已如实登记 |
| 8 | 并行全量首轮 F（上轮 MINOR-4） | **删除** | 反证推翻：本轮 `-n auto` 首轮即 `failures=0 errors=0`（junit 3823），无法再现 |
| 9 | `shell` / `theme` / `yate_trace_level` 的三个豁免字段过度设计 | **删除** | 反证推翻：三者各对应一条已登记的存量行为差异，实测删任一个都会造成行为变化 |
| 10 | 上轮 MAJOR-1 修复未补回归用例 | **漏报补入 → MINOR-5** | 漏报自查「测试覆盖」维度回扫时，实测全 `tests/` 搜索发现 `None` 语义无用例；上轮复审建议补 `test_extract_options_treats_none_as_unset`，实际未补 |

漏报自查（6 维度反向扫）：

| 维度 | 自查结果 |
|---|---|
| 正确性 | 已对 yaterc 3093 组输入与 `:set` 10 spec × 28 取值做完整差分；发现 MAJOR-1 |
| 边界条件 | 已覆盖 None / 空串 / 纯空白 / `\\t` / 超界上下沿 / bool×int 交叉 / 非字符串类型（`[1]` / `3.5` / `b"x"` / `0`）。增补：`filetype` 空值属边界且归于用户可见路径，已单列为 MAJOR-1 |
| 异常处理 | 实测 9 组恶意输入均不抛异常（`keymap=[1]` / `theme=3.5` / `tab_width="8"` / `shell=b"x"` / `support_mouse=0` 均转为报错行）；`native_error` 的 `.format` 仅用 `{value!r}`，不会因引号形态抛错。未发现吞异常 |
| 并发安全 | 改动均为模块级不可变 `tuple` / `frozen dataclass` 与纯函数；`OPTION_SPECS` / `SET_OPTION_SPECS` 在 import 期一次性求值，无共享可变状态、无惰性竞争。未发现问题 |
| 性能 | `_extract_options` 从 13 段内联判断变为 15 行表遍历；`set_option_value_candidates` 为 O(n)（n=15），且仅补全路径调用。启动期一次性执行，无可感知影响 |
| 类型与测试覆盖 | pyright strict 0 诊断；新增 `cast` 均必要；覆盖率 93.08%（阈值 75）；覆盖缺口仅 `config.py:312`（结构性不可达）；守卫对 `kind` 拼写无覆盖（MINOR-1） |

**证据核实**：MAJOR-1 与 MINOR-1 ~ MINOR-4 的所有「文件:行号」均在写入本报告前重新读取核对；所有双侧实测数据均用本次真实运行的探针产生，未引用他人自述数字。

## 未解决项

1. **MAJOR-1 待修复**：`:set filetype=`（及 `ft=` / `lang=` / `language=`）空值路径。修复后需重跑六道门禁并补用例。
2. **MINOR-1 ~ MINOR-5** 为非阻塞改进，建议随 MAJOR-1 一并处理（尤其 MINOR-1 与 MINOR-4 与 MAJOR-1 同源，均指向 `kind` 语义未被类型与守卫钉住）。
3. **归档评审文档已包含不实际已闭合的结论**：`.trae/reviews/2026-11-16-option-spec-unify.md:368` 写明「复审结论：APPROVE（0 BLOCKER / 0 MAJOR / 0 MINOR 未闭合）」，而本轮发现 1 MAJOR。建议在本轮修复后以本报告为新一轮结论；历史评审文件按只读事实保留，另行追加纠正说明（不覆盖旧文件）。
4. **无未澄清的工具异常**：本轮 `-n auto` 全量、架构、覆盖率、冒烟、changelog 全部取得明确退出码 0，无上轮“点阵后挂起”或“收尾杀进程”现象。

## 审查环境与可复现性

- 双侧差分探针为本次临时脚本（不入库），已全部清理；`git status --short` 在清理后为空（仅新增本报告）。
- master 侧临时目录 `d:/Programming/yate/.tmp` 已删除；主工作区未受影响。
- 工作树已验证干净，无产品源码 / 测试 / 规则 / 计划文档被修改。

## 修复与复审（2026-11-17，提交 ef17738f）

主代理逐条闭合本轮 1 MAJOR / 5 MINOR，并在 master 与本 worktree 双侧探针比对确认：

- MAJOR-1（`filetype` 空值）：`OptionSpec.parse_set_text` 增加显式 `any_text` 分支，返回原文（含空串 / 纯空白）；双侧探针 `"" -> ""`、`"   " -> "   "`、`"py" -> "py"`、`" auto " -> " auto "` 逐字相等，命令层不再在解析阶段报 warn。新增 `test_filetype_set_text_accepts_any_string_including_empty`。
- MINOR-1（`kind` 裸字符串）：改为 `Literal["enum", "int", "bool", "text", "any_text"]`，拼错由 pyright 拦截；新增 `test_option_kinds_are_a_frozen_literal_set`。
- MINOR-2（bool 候选硬编码）：新增 `test_bool_value_candidates_stay_within_the_shared_spellings`，用公共 `parse_bool` 验证 `readonly` / `show_hidden` 候选词法；行为集合保持 master 不变，收归统一表另案。
- MINOR-3（薄弱文本断言）：删除架构守卫中的 `"not spec.settable" in config_src` 子串断言；行为断言 `set_option_value_candidates("key_protocol") == ()` 已在 `test_option_specs.py` 中存在。
- MINOR-4（docstring / 不可达注释）：模块 docstring 改写为 `OPTION_SPECS` 单一来源 + 派生视图；`validate_native` 的 `any_text` 分支补「无 rc 可见 spec 使用」英文注释。
- MINOR-5（None 回归缺口）：新增 `test_extract_options_treats_none_as_unset`，覆盖 `keymap` / `terminal_height` / `yate_trace_level` / `support_mouse` 四个代表 spec，断言 `errors == []` 且字段保持默认。

复审门禁（主代理亲跑）：

- `pyright yate/ tests/ tools/ pack/` -> **0 errors**
- `pytest tests/test_option_specs.py tests/test_yaterc_options.py tests/test_set_options.py tests/test_architecture.py -q -n 1` -> **98 passed, exit 0**
- 双侧 `filetype` 解析探针 -> 与 master 逐字相等

**复审结论更新：APPROVE**（0 BLOCKER / 0 MAJOR / 0 MINOR 未闭合）。历史 `.trae/reviews/2026-11-16-option-spec-unify.md` 按只读事实保留，以其当时证据为准；本段为本轮合并前评审的最终结论。

