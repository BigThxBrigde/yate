# plan-a：统一选项表与 `config.py` 派生（wave-1）

> 唯一规范来源：[总纲](overview.md) 的 D1 / D2 / D3 / D4 / D7。
> 波次：wave-1，独占文件 `yate/config.py`、新增 `tests/test_option_specs.py`。

## 一、输入与范围

- 输入：`yate/config.py` 现状（378 行），含 `KNOWN_OPTIONS`（L34-39）、`VALID_KEYMAPS`（L41）、`VALID_KEY_PROTOCOLS`（L45）、`VALID_TRACE_LEVELS`（L49）、dataclass（L52-213）、`:set` 表（L216-377）。
- 改动文件（独占）：`yate/config.py`、`tests/test_option_specs.py`（新增）。
- 输出：`OPTION_SPECS` 统一表 + 全部公共名派生；静态 parser 仍可用。
- 不做：不改 dataclass 字段/默认值/类型；不改 `commands.py` / `yaterc_options.py`；不改加载器。

## 二、具体修改（定位到行号）

### 2.1 新增类型别名与表结构（`config.py`，在 L49 之后、dataclass 之前）

保留现有 `OptionParser`（L244）不动，新增一个原生值解析器别名，均用 PEP 695 `type` 语句：

```python
#: Validate a native yaterc value; ``None`` means invalid.
type NativeValidator = Callable[[object], object | None]
```

在 `known options` 常量区（L32-49）之后新增一个内部构造块，把「合法值/范围」定义集中到 `_DOMAINS` 私有表（唯一声明处）：

```python
#: Single source of option domains.  Each name maps to its legal-value
#: predicate shared by both native (yaterc) and text (:set) parsing.
#: Kept private; consumers go through OPTION_SPECS.
type Domain = tuple[str, ...] | tuple[int, int] | None
```

`Domain` 三种形态约定（写进 docstring，英文 ASCII）：

| 形态 | 含义 | `parse_native` | `parse_text` |
|---|---|---|---|
| `tuple[str, ...]` | 枚举合法值（大小写敏感或按选项规则） | `isinstance(v, str) and v in values` | 字符串查表（布尔另行处理） |
| `tuple[int, int]` | 闭区间整数，拒绝 bool | `isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi` | `_parse_int_in_range(text, lo, hi)` |
| `None` | 任意非空字符串（theme / filetype / shell） | 按选项特例（见 2.3） | 按选项特例（见 2.3） |

> 布尔不进 `Domain`：布尔的原生判定是 `isinstance(v, bool)`，字符串解析走 `parse_bool` 的 `_TRUTHY` / `_FALSY`，两者无共享「合法值集合」，用 spec 的 `kind="bool"` 标记即可（见 2.2）。

### 2.2 `OptionSpec` 数据类（`config.py`，在 L244 `OptionParser` 之后）

```python
@dataclass(frozen=True)
class OptionSpec:
    """One option definition shared by yaterc loading and the ``:set`` command.

    ``name`` is the canonical spelling and the yaterc variable name.
    ``rc_visible`` marks options that yaterc recognizes; ``settable`` marks
    options exposed on ``:set``.  ``domain`` is the one place where legal
    values live.  ``kind`` selects the native/parse strategies; ``bool``
    uses the shared ``parse_bool`` spellings.  ``invalid_message`` and
    ``summary`` are the user-visible strings reused at both call sites.
    """

    name: str
    aliases: tuple[str, ...]
    rc_visible: bool
    settable: bool
    kind: str  # "enum" | "int" | "bool" | "text" | "any_text"
    domain: Domain
    invalid_message: str          # ``:set`` warning, reused at the command site
    invalid_message_fmt: str      # yaterc error template, .format(value=raw)
    summary: str
    set_text_any: bool = False    # shell-only: keep the legacy empty-string accept
```

附两个方法（**纯函数，无副作用**）：

```python
    def validate_native(self, value: object) -> object | None:
        """Return *value* when legal for yaterc, else ``None``."""
        ...  # enum/int/bool/text 分支，见 2.3

    def parse_set_text(self, text: str) -> object | None:
        """Parse a ``:set`` command-line string; ``None`` when invalid."""
        ...  # enum/int/bool/text 分支，见 2.3
```

两种解析的具体分支：

| `kind` | `validate_native(value)` | `parse_set_text(text)` |
|---|---|---|
| `enum` | `isinstance(value, str) and value in domain`（domain 为 `tuple[str, ...]`） | `text if text in domain else None` |
| `int` | `_valid_int(value, lo, hi)`（复用 `_parse_int_in_range` 的判定：非 bool 的 int 且落在区间） | `_parse_int_in_range(text, lo, hi)` |
| `bool` | `value if isinstance(value, bool) else None` | `parse_bool(text)`（读 `_TRUTHY` / `_FALSY`） |
| `text` | `value if isinstance(value, str) and value.strip() else None`，返回 **原值**（保留 `shell` 两侧行为：yaterc 拒绝空串，`:set` 现状 `shell` 接受任意字符串——见 2.3 特例） | `text if text.strip() else None`（非空串；`shell` 特例除外） |
| `any_text` | `value if isinstance(value, str) else None` | `text`（任意字符串，含空串；仅 `shell` 使用，见 2.3） |

**`shell` 特例落地**：`shell` spec 用 `kind="text"` 供 yaterc（拒绝空串），但 `:set` 侧现状 `_parse_shell`（L280-282）对任意字符串返回原值、含空串。为逐字保持行为，用 dataclass 上的可选字段 `set_text_any`（2.2 已声明，默认 `False`，仅 `shell` 传 `True`）：`parse_set_text` 首行判断该字段，为 `True` 时直接返回 `text`（含空串）。docstring 注明这是存量差异、不得借统一之名归一。

### 2.3 `OPTION_SPECS` 表（`config.py`，替换 L216-370 的手写 parser 群 + SET_OPTION_SPECS）

按现有顺序逐行落表。每行字段取值严格照抄现状（合法值、报错文案、summary）：

| name | aliases | rc_visible | settable | kind | domain | `invalid_message`（`:set`）/ `invalid_message_fmt`（yaterc）/ `summary` 来源 |
|---|---|---|---|---|---|---|
| `keymap` | `()` | ✓ | ✓ | enum | `VALID_KEYMAPS` | 现状 L303-305：`keymap must be vsc or vim` / `keymap=vsc\|vim` |
| `theme` | `()` | ✓ | ✓ | text | `None` | L310-312：`theme must be a non-empty name` / `theme=mocha` |
| `tab_width` | `()` | ✓ | ✗ | int | `(1, 16)` | yaterc 现状 L502-504 文案 |
| `use_spaces` | `()` | ✓ | ✗ | bool | `None` | yaterc 现状 L511 |
| `shell` | `()` | ✓ | ✓ | text + `set_text_any=True` | `None` | L317-319 / yaterc L518 |
| `terminal_height` | `()` | ✓ | ✓ | int | `(3, 40)` | L324-326 / L529-532 —— **范围唯一来源** |
| `filetype` | `("ft","language","lang")` | ✗ | ✓ | any_text | `None` | L330-333 |
| `show_hidden` | `()` | ✓ | ✓ | bool | `None` | L338-341 / yaterc L539-541 |
| `readonly` | `()` | ✗ | ✓ | bool | `None` | L345-348 |
| `support_mouse` | `()` | ✓ | ✓ | bool | None | L351-354 / yaterc L548-550 |
| `which_key` | `()` | ✓ | ✓ | bool | None | L358-361 / yaterc L557-559 |
| `which_key_auto` | `()` | ✓ | ✓ | bool | None | L365-368 / yaterc L566-568 |
| `key_protocol` | `()` | ✓ | ✗ | enum | `VALID_KEY_PROTOCOLS` | yaterc L485-487 |
| `yate_trace` | `()` | ✓ | ✗ | bool | None | yaterc L575-577 |
| `yate_trace_level` | `()` | ✓ | ✗ | enum | `VALID_TRACE_LEVELS` | yaterc L586-594（含 upper() 归一化） |

> `yate_trace_level` 的 `validate_native` 需先 `value.strip().upper()` 再查 `VALID_TRACE_LEVELS`（现状行为）；其 `parse_set_text` 未被 `:set` 使用（settable=False），仍需实现以保持 spec 完整性，按 enum 查表即可。

删除或降为私有的旧符号（逐项）：

- `parse_bool`（L223）**保留公共名**，被 `bool` kind 的 `parse_set_text` 调用；`_TRUTHY` / `_FALSY` 保留。
- `_parse_int_in_range`（L233）保留，被 `int` kind 复用。
- `_parse_filetype`（L265）等 6 个 `_parse_*`（L265-292）**删除**，其逻辑已进 `OptionSpec.parse_set_text` 的 kind 分支。
- `SET_OPTION_SPECS`（L299-370）改为派生：
  ```python
  SET_OPTION_SPECS: tuple[SetOption, ...] = tuple(
      SetOption(
          name=spec.name,
          aliases=spec.aliases,
          parse=spec.parse_set_text,
          invalid_message=spec.invalid_message,
          summary=spec.summary,
      )
      for spec in OPTION_SPECS
      if spec.settable
  )
  ```
- `KNOWN_OPTIONS`（L34-39）改为派生：
  ```python
  KNOWN_OPTIONS: tuple[str, ...] = tuple(
      spec.name for spec in OPTION_SPECS if spec.rc_visible
  ) + ("large_file",)
  ```
  注意现状 `KNOWN_OPTIONS` 含 `large_file`（dict 选项，14 项），而 `OPTION_SPECS` 不含 dict/list 选项；故用 `+ ("large_file",)` 补上，并加英文注释说明 dict/list 选项由 `yaterc_options.py` 的专用 extractor 处理、此处仅保留名字以维持 `options` 字典的读取面。

  **顺序说明（必须如实登记，不得写成「与现状完全一致」）**：派生顺序为
  `keymap, theme, tab_width, use_spaces, shell, terminal_height, show_hidden,
  support_mouse, which_key, which_key_auto, key_protocol, yate_trace,
  yate_trace_level, large_file`，与现状字面量顺序
  `keymap, theme, tab_width, use_spaces, shell, terminal_height, show_hidden,
  yate_trace, yate_trace_level, key_protocol, support_mouse, which_key,
  which_key_auto, large_file` **不同**。实测唯一消费点是
  `yaterc_options.py:469` 的 `{name: namespace[name] for name in KNOWN_OPTIONS ...}`
  ——产物是 dict，顺序不影响任何行为，也不是用户可见文案（usage 文案来自
  `SET_OPTION_SPECS`，其派生顺序与现状逐字一致，见 2.3 表序）。因此顺序变化
  属内部实现细节，接受；测试 pin 派生后的实际 tuple，不 pin 旧字面顺序。

- `set_option_names()`（L373-377）保持不变（从 `SET_OPTION_SPECS` 派生），无需改代码。

### 2.4 新增静态 value 候选查询（供 plan-c 使用）

```python
def set_option_value_candidates(name: str) -> tuple[str, ...]:
    """Static value candidates for a ``:set`` option, empty when dynamic."""
    spec = next((s for s in OPTION_SPECS if s.name == name), None)
    if spec is None or spec.kind != "enum":
        return ()
    return spec.domain if isinstance(spec.domain, tuple) else ()
```

`keymap` 返回 `("vsc","vim")`；`theme` / `filetype` 等非枚举返回空 tuple，由 completer 保留动态分支。

### 2.5 行数与体量检查

- 现状 378 行；预计新增约 130-180 行（表 15 行 + 两个方法约 60 行 + 类型/常量约 20 行 + 注释约 30 行），删除约 30 行旧 parser → 约 480-530 行。
- 验收命令实测 `splitlines()`：若 > 750 行触发拆分评审（不得直接登记豁免）。

## 三、详细测试用例（新增 `tests/test_option_specs.py`）

> 文件头声明 `# pyright: reportPrivateUsage=false` 仅在需要访问私有域时使用（参照 `tests/test_yaterc_options.py:12-14` 惯例）；本轮测试只访问公共名则不需要。

1. `test_option_specs_cover_all_known_scalar_options`
   - 前置：无 fixture；导入 `OPTION_SPECS` / `KNOWN_OPTIONS` / `SET_OPTION_SPECS`。
   - 操作：取 `spec_names = tuple(s.name for s in OPTION_SPECS if s.rc_visible)`。
   - 断言：`spec_names + ("large_file",) == KNOWN_OPTIONS`（**完整 tuple 相等，含顺序**）；`len(set(KNOWN_OPTIONS)) == len(KNOWN_OPTIONS)`（无重复名）。
   - 行为点：表覆盖全部 yaterc 可见标量选项，派生顺序固定；不 pin 旧字面顺序（见 2.3 顺序说明）。

2. `test_option_specs_cover_all_settable_options`
   - 前置：同上。
   - 操作：`spec_settable = {s.name for s in OPTION_SPECS if s.settable}`。
   - 断言：`spec_settable == {spec.name for spec in SET_OPTION_SPECS}`，且 `set_option_names()` 等于 `(name + aliases)` 的展平 tuple（顺序一致）。
   - 行为点：`SET_OPTION_SPECS` 与补全候选均由统一表派生。

3. `test_terminal_height_range_is_single_source`
   - 前置：从 `OPTION_SPECS` 取 `terminal_height` spec。
   - 操作：断言 `spec.domain == (3, 40)`；对 `spec.validate_native(2)` / `(3)` / `(40)` / `(41)` / `(True)` 分别调用；对 `spec.parse_set_text("2")` / `"12"` / `"41"` / `"abc"` 分别调用。
   - 断言：`None, 3, 40, None, None` 与 `None, 12, None, None`（逐项 `==`）。
   - 行为点：范围只声明一次，两侧判定一致且拒绝 bool。

4. `test_bool_native_rejects_strings_but_set_text_accepts_spellings`
   - 前置：取 `support_mouse` spec。
   - 操作：`validate_native("on")` / `validate_native(True)` / `parse_set_text("on")` / `parse_set_text("yes")` / `parse_set_text("maybe")`。
   - 断言：依次 `None, True, True, True, None`。
   - 行为点：两侧语义分别保持（原生拒字符串、命令行接受 spellings）。

5. `test_shell_keeps_its_empty_string_difference`
   - 前置：取 `shell` spec。
   - 操作：`validate_native("")` 与 `parse_set_text("")`。
   - 断言：`validate_native("") is None`（yaterc 拒绝空串），`parse_set_text("") == ""`（`:set` 现状接受空串）。
   - 行为点：D7 登记的存量差异被 pin 住，防止「统一」误改行为。

6. `test_trace_level_domain_uses_logs_level_names`
   - 前置：无。
   - 操作：`spec = next(s for s in OPTION_SPECS if s.name == "yate_trace_level")`。
   - 断言：`spec.domain == VALID_TRACE_LEVELS` 且 `VALID_TRACE_LEVELS == LEVEL_NAMES`（从 `yate.logs` import）。
   - 行为点：等级集合单一来源仍指向 `yate.logs`。

7. `test_set_option_value_candidates_returns_static_enum_only`
   - 前置：无。
   - 操作：调 `set_option_value_candidates("keymap")` / `("theme")` / `("nope")`。
   - 断言：依次 `("vsc","vim")`、`()`、`()`。
   - 行为点：补全候选来自 domain，动态选项返回空。

8. `test_config_stays_within_size_threshold`（可并入现有 `test_source_files_within_size_threshold`，此处单列便于本波验收）
   - 前置：读 `yate/config.py` 文本。
   - 操作：`len(source.splitlines())`。
   - 断言：`<= 800`（并打印实测值供回填）。
   - 行为点：体量阈值不越线。

9. **反例演练**（仅人工执行，不留测试）：临时把 `terminal_height` 的 domain 改回 `(3, 41)`，跑用例 3 确认失败，还原后重跑确认通过；记录演练结论到计划回填，不把错误值留在仓库。

## 四、验证方案

| 目标 | 命令 | 通过标准 |
|---|---|---|
| 类型与全仓静态 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | 退出码 0，零诊断 |
| 本波用例 | `.venv\Scripts\python.exe -m pytest tests/test_option_specs.py tests/test_set_options.py -q -n 1` | 退出码 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 退出码 0（41 passed） |

> `tests/test_set_options.py` 必须零改动通过——它的断言是「公共名兼容」的活契约。

## 五、风险与回滚

- **风险（已接受并登记）**：`KNOWN_OPTIONS` 派生顺序与现状字面量不同 → 内部 dict 构建顺序变化，用户不可见、无行为影响（见 2.3 顺序说明）。缓解：用例 1 pin 住完整派生 tuple，防止后续无意识再变；usage 文案由 `SET_OPTION_SPECS` 决定，其顺序与现状一致，另有 `tests/test_set_options.py` 的 completer 用例 pin 住。
- **风险**：`parse_set_text` 对 `yate_trace_level` 未做 `upper()`，而 yaterc 侧做了；虽 settable=False 不影响运行，但 spec 方法语义不完整。缓解：在 `parse_set_text` 对 `name == "yate_trace_level"` 同样先 `upper()`，或明确注释该方法对非 settable 选项不保证语义；二选一，由执行者在 plan-b 前定稿并回填。
- **风险**：`Callable` alias 触发 `test_callable_aliases_use_type_statements`。缓解：用 `type NativeValidator = ...`，不用赋值式。
- 回滚：本波单独提交 `refactor(config): unify option definition table`；`git revert` 该提交即回滚，plan-b/c 尚未落盘故无级联。
