# plan-c：命令层候选与防漂移守卫（wave-3）

> 唯一规范来源：[总纲](overview.md) 的 D5 / D6 / D7；依赖 wave-1 [plan-a](option-spec-unify-spec-table-plan-a.md) 与 wave-2 [plan-b](option-spec-unify-rc-consumer-plan-b.md) 均验收通过。
> 波次：wave-3（串行，依赖 a、b），独占文件 `yate/commands.py`、`tests/test_set_options.py`、`tests/test_architecture.py`。

## 一、输入与范围

- 输入：`yate/commands.py` 的 `_make_set_completer`（L216-237）含 value 候选硬编码；`SET_APPLY`（L47-152）与 `_set`（L429-460）已由 `SET_OPTION_SPECS` 驱动，无需改。
- 依赖输入：`config.py::set_option_value_candidates`（wave-1）、`yaterc_options.py` 已消费表（wave-2）。
- 改动文件（独占）：`yate/commands.py`、`tests/test_set_options.py`、`tests/test_architecture.py`。
- 输出：补全候选与合法值同源；新增架构守卫钉住「单一来源」；反例演练留痕。
- 不做：不改 `SET_APPLY` 内容与归属；不改 `_set` 分派逻辑；不改 L3 → L0 依赖方向。

## 二、具体修改（定位到行号）

### 2.1 `commands.py` 导入与 completer（`commands.py`，L15 与 L216-237）

L15 的 import 增加 `set_option_value_candidates`：

```python
from yate.config import (
    SET_OPTION_SPECS,
    SetOption,
    set_option_names,
    set_option_value_candidates,
)
```

`_make_set_completer`（L216-237）的 value 候选部分改为：

```python
def _make_set_completer(editor: Editor) -> ArgCompleter:
    """Completer for ``:set``: option names, or ``key=`` value candidates."""
    options: tuple[str, ...] = set_option_names()
    def _complete(prefix: str) -> list[str]:
        if "=" in prefix:
            key, _, value = prefix.partition("=")
            key = key.strip()
            candidates = set_option_value_candidates(key)
            if candidates:
                vals: tuple[str, ...] = candidates
            elif key == "theme":
                vals = tuple(editor.theme_names())
            elif key in _FILETYPE_KEYS:
                vals = ("auto", *available_filetypes())
            elif key in ("show_hidden", "readonly", "support_mouse",
                         "which_key", "which_key_auto"):
                vals = ("on", "off")
            else:
                return []
            return [f"{key}={v}" for v in vals if v.startswith(value) and v != value]
        return [opt for opt in options if opt.startswith(prefix) and opt != prefix]
    return _complete
```

**行为等价核对**（逐项，取自现状 L223-233）：

| key | 现状候选 | 统一后来源 | 是否一致 |
|---|---|---|---|
| `keymap` | `("vsc","vim")` | `set_option_value_candidates("keymap")` → domain `VALID_KEYMAPS` = `("vsc","vim")` | ✅ |
| `theme` | `tuple(editor.theme_names())` | candidates 为空 → 保留动态分支 | ✅ |
| filetype 四拼写 | `("auto", *available_filetypes())` | candidates 为空 → 保留 `_FILETYPE_KEYS` 分支 | ✅ |
| `show_hidden` | `("on","off")` | candidates 为空（bool 非 enum）→ 新增 bool 键集合分支 | ✅ |
| `readonly` | `("true","false")` | **注意**：现状 readonly 用 `true/false`，上面写成 `on/off` 会改变行为！ | ❌ 须修正 |

**修正**：`readonly` 单独保留 `("true","false")`，其余 bool 用 `("on","off")`。落地时写成：

```python
            elif key == "readonly":
                vals = ("true", "false")
            elif key in ("show_hidden", "support_mouse", "which_key",
                         "which_key_auto"):
                vals = ("on", "off")
```

> 这是本波最大的行为陷阱：`:set` 的 value 候选中 bool spellings 按选项而不同（`readonly` 是历史遗留的 `true/false`，其余是 `on/off`），统一表只提供 enum 的静态候选，bool 候选仍按选项形态保留在 completer 中，避免误归一。plan-a 的 `set_option_value_candidates` 对非 enum 返回空 tuple 正是为此设计。

### 2.2 `tests/test_set_options.py` 追加用例

1. `test_set_completer_static_candidate_comes_from_spec_domain`
   - 前置：`_set_driver()`（现有 helper，L120-125）；entry = registry.get("set")。
   - 操作：`completer("keymap=")` 与 `completer("keymap=v")`。
   - 断言：前者返回 `["keymap=vsc", "keymap=vim"]`（顺序同 domain）；后者返回 `["keymap=vsc"]`。
   - 行为点：静态候选来自 `OPTION_SPECS` 的 domain；若 domain 与硬编码脱钩则失败。

2. `test_set_completer_preserves_distinct_bool_spellings`
   - 前置：同上。
   - 操作：`completer("readonly=")` / `completer("show_hidden=")`。
   - 断言：依次 `["readonly=true","readonly=false"]` 与 `["show_hidden=on","show_hidden=off"]`。
   - 行为点：pin 住 `readonly` 的 `true/false` 与其余 bool 的 `on/off` 差异，防止统一误伤。

3. `test_set_completer_dynamic_candidates_unchanged`
   - 前置：`_ConfigEditor` 现有 stub（L97-118），`theme_names` / `available_filetypes` 按现有 monkeypatch 方式准备。
   - 操作：`completer("theme=")` / `completer("ft=")`。
   - 断言：分别等于 stub 提供的主题名过滤结果与 `("auto", *available_filetypes())` 过滤结果。
   - 行为点：动态分支未被静态化。

### 2.3 `tests/test_architecture.py` 新增守卫（`test_source_files_within_size_threshold` 之后）

新增一条守卫 `test_option_definitions_have_single_source`，**AST + 文本双重取证**：

```python
def test_option_definitions_have_single_source() -> None:
    """Legal ranges/candidate sets are declared once in config.OPTION_SPECS.

    Both the yaterc loader and the ``:set`` completer must derive their
    values from the shared table; a reintroduced literal range or candidate
    tuple in either consumer fails here.
    """
```

断言内容（英文 docstring、英文注释，正文说明写进计划）：

1. 读 `yate/config.py` 源码 AST，找到 `OPTION_SPECS` 的赋值节点，断言它是 tuple literal / 由 tuple 构造，且其中 `terminal_height` spec 的 `domain` 常量为 `(3, 40)`。实现可用文本锚点：`assert "name=\"terminal_height\"" in cfg_src`，并在其附近 `40` 行窗口内 `assert "(3, 40)" in window`。
2. 读 `yate/yaterc_options.py` 源码，断言**不含**以下任何硬编码形态（防止回到内联校验）：
   - `3 <= terminal_height <= 40`
   - `if isinstance(use_spaces, bool)`（其余 12 项同形态正则，统一用 `re.search(r"if isinstance\(\w+, \(?bool|str|int\)?", body)` 在 `_extract_options` 函数体文本上匹配，命中数须为 0）
   - `config.errors.append(f"... must be ...")` 形式的逐项文案（用函数体文本比对：除通用模板调用外，不含 ≥3 处 `must be` 字面量）
3. 读 `yate/commands.py` 源码，断言 `_make_set_completer` 函数体文本中**不含** `("vsc", "vim")` 字面量、`vals = tuple(` 的硬编码赋值不超过 1 处（`theme` 动态分支保留）。
4. 断言公共派生关系（运行时）：`set_option_names()` 与 `tuple(spelling for spec in SET_OPTION_SPECS for spelling in (spec.name, *spec.aliases))` 相等；`KNOWN_OPTIONS` 与 `tuple(s.name for s in OPTION_SPECS if s.rc_visible)` 排序后相等（考虑 `large_file` 的附加）。

**守卫总数更新**：`tests/test_architecture.py` 的 docstring 头部（L1-30 附近的用例计数说明）与 `architecture-boundaries.md` §六「41 个用例」表格需同步为 42（若本守卫作为单条新增）。同时更新两处计数：规则文档 §六标题下「已落地 41 个用例」与文末对照表新增第 42 行。

### 2.4 负向演练（人工，留痕不入库）

| 演练 | 操作 | 预期 | 还原 |
|---|---|---|---|
| N1 | 在 `yate/commands.py` 的 `_make_set_completer` 临时写回 `vals = ("vsc","vim")` 到 `key == "keymap"` 分支 | `test_option_definitions_have_single_source` 失败 | `git checkout -- yate/commands.py` 后重跑通过 |
| N2 | 在 `yate/yaterc_options.py::_extract_options` 临时加回 `if isinstance(tab_width, int)...` 一行 | 守卫第 2 组断言失败 | 还原后重跑通过 |

演练结论（含具体断言失败信息）回填本计划「六、执行回填」。

## 三、详细测试用例汇总

本波新增用例已在 2.2（3 条）与 2.3（1 条守卫）列全。回归范围：

- `tests/test_set_options.py` 全文（现有 10+ 用例，零放宽）。
- `tests/test_yaterc_options.py` 全文（wave-2 产物）。
- `tests/test_option_specs.py` 全文（wave-1 产物）。
- `tests/test_architecture.py` 全文（41 → 42 passed）。

## 四、验证方案

| 目标 | 命令 | 通过标准 |
|---|---|---|
| 类型与全仓静态 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | 退出码 0，零诊断 |
| 命令层与守卫 | `.venv\Scripts\python.exe -m pytest tests/test_set_options.py tests/test_option_specs.py tests/test_yaterc_options.py tests/test_architecture.py -q -n 1` | 退出码 0 |
| 架构测试计数 | 上述命令输出中的用例数 | 42 passed（原 41 + 新 1） |
| 负向演练 | 按 2.4 人工执行 | 两次演练均令守卫失败，还原后通过 |

## 五、风险与回滚

- **风险**：`readonly` 的 bool 候选被误写成 `on/off` → 用户可见补全过程改变。缓解：2.1 显式修正 + 用例 2 pin 住。
- **风险**：AST 守卫用文本窗口匹配 `domain` 常量，位置变动导致假阳性/假阴性。缓解：断言基于语义锚点（spec name 所在行 + 固定窗口），并在 docstring 写明守卫意图；若实现中表结构重构，须同步更新守卫而非绕过它。
- **风险**：架构用例计数与规则文档不同步。缓解：2.3 已列入同步项；执行者改完后跑 `tests/test_architecture.py` 确认 42 passed。
- **风险**：`commands.py` 的 import 顺序违反「标准库 → 第三方 → 项目内部，组内字母序」`.venv` 缓解：按 L15 现有块内字母序插入 `set_option_value_candidates`。
- 回滚：本波单独提交 `refactor(commands): derive :set candidates from shared specs`；若含架构守卫与文档计数，则同提交内一并回滚（它们是同一逻辑单元）。

## 六、执行回填

> 本节由执行者在实际执行后填写；规划阶段留空。

- 实际用例数：（待回填）
- 负向演练 N1 / N2 的失败断言原文：（待回填）
- `setattr` fallback 是否启用（见 plan-b 2.2）：（待回填）
- 与方案的偏离及实测依据：（待回填）
