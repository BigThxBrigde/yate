# plan-b：yaterc 加载侧消费统一表（wave-2）

> 唯一规范来源：[总纲](overview.md) 的 D2 / D3 / D7；依赖 wave-1 的 [plan-a](option-spec-unify-spec-table-plan-a.md) 已验收通过。
> 波次：wave-2（串行，依赖 a），独占文件 `yate/yaterc_options.py`、`tests/test_yaterc_options.py`。

## 一、输入与范围

- 输入：`yate/yaterc_options.py` 现状（742 行），`_extract_options`（L467-599）内联校验 13 个标量选项；dict/list extractor（L61-465、L602-741）保持不变。
- 依赖输入：`config.py::OPTION_SPECS` 及各 `OptionSpec.validate_native`（wave-1 产物）。
- 改动文件（独占）：`yate/yaterc_options.py`、`tests/test_yaterc_options.py`。
- 输出：`_extract_options` 改为遍历所有 `spec.rc_visible` 的标量 spec（表中全部为标量；dict/list 选项不在表中）；所有现有断言零放宽通过。
- 不做：不改 dict/list extractor；不改 `yaterc.py`；不改 `:set` 侧。

## 二、具体修改（定位到行号）

### 2.1 导入调整（`yaterc_options.py`，L32-42）

从 `yate.config` 的 import 列表新增 `OPTION_SPECS`，保留其余（KNOWN_OPTIONS 若不再使用则移除，避免未使用导入）：

```python
from yate.config import (
    OPTION_SPECS,
    VALID_KEYMAPS,
    VALID_KEY_PROTOCOLS,
    VALID_TRACE_LEVELS,
    FilePreviewConfig,
    LanguageServerSpec,
    LargeFileConfig,
    ScreenSaverConfig,
    YateConfig,
)
```

> `VALID_KEYMAPS` / `VALID_KEY_PROTOCOLS` / `VALID_TRACE_LEVELS` 仍被哪些函数用，由执行者实测：若全部校验都已迁入 spec，则从本模块 import 中移除（保留 `config.py` 公共名供别处 import）。`KNOWN_OPTIONS` 不再被 `_extract_options` 直接使用时，从本模块 import 移除。

### 2.2 删除内联校验，改为通用遍历（`yaterc_options.py`，L467-599）

将 `_extract_options` 的整个函数体替换为：

```python
def _extract_options(namespace: dict[str, Any], config: YateConfig) -> None:
    """Fold recognized scalar options from *namespace* into *config*.

    Legal values come from the shared spec table: each visible scalar spec
    validates the native rc value and writes it to the matching config field.
    Invalid values are reported on ``config.errors`` and keep their default;
    other options still apply.  Dict/list options are handled by dedicated
    extractors below and are not touched here.
    """
    for spec in OPTION_SPECS:
        if not spec.rc_visible or spec.name not in namespace:
            continue
        raw = namespace[spec.name]
        value = spec.validate_native(raw)
        if value is None:
            config.errors.append(spec.invalid_message_fmt.format(value=raw))
            continue
        # yate_trace_level needs upper() normalization before validation;
        # the spec already handles it, so the stored value is canonical.
        setattr(config, spec.name, value)
    _extract_language_servers(namespace, config)
    _extract_screen_saver(namespace, config)
    _extract_file_preview(namespace, config)
    _extract_large_file(namespace, config)
```

**关键约束**：

- `spec.invalid_message_fmt` 是 plan-a 中 `OptionSpec` 需提供的 yaterc 报错模板字段（形如 `"tab_width must be an integer between 1 and 16, got {value!r}"`，`str.format` 语法）。plan-a 的 `invalid_message` 字段存 `:set` 文案，二者不同，故本波要求 plan-a 补 `invalid_message_fmt` 字段；plan-a 执行时若已预见到此需求，应一次补齐（总纲 D3 兼容策略已登记该字段的必要性）。
- `setattr` 的字段名来自 `spec.name`，而 yaterc 可见标量选项的 name 恰为 `YateConfig` 字段名（`keymap` / `theme` / `tab_width` / `use_spaces` / `shell` / `terminal_height` / `show_hidden` / `support_mouse` / `which_key` / `which_key_auto` / `key_protocol` / `yate_trace` / `yate_trace_level`），共 13 项，与现状 `_extract_options` 处理的集合完全一致。`filetype` / `readonly` 的 `rc_visible=False`，不会被遍历到。
- `setattr` 是动态写属性，pyright strict 下**必须验证零诊断**。若 pyright 报错，改用显式写回表：`_CONFIG_SETTERS: dict[str, Callable[[YateConfig, object], None]]`，逐项 lambda 赋值（13 项）。该 fallback 只在本波实测需要时启用，并回填本计划。
- `yate_trace_level` 的 upper() 归一化在 `validate_native` 内部完成（plan-a 已实现），此处直接存返回值。
- 顺序：先标量遍历，再 4 个 dict/list extractor，与现状 `L596-599` 一致。

### 2.3 删除的旧代码清单（`yaterc_options.py`）

- L469：`options = {name: namespace[name] ...}` — 删除。
- L471-594：13 个标量的逐项 `if isinstance(...)` 校验与报错 — 全部删除。
- 保留：`_extract_path_list` / `_extract_extensions` / `_extract_disabled_extensions` / `_extract_theme_dirs`（L61-171）、`_parse_journey_fraction` / `_extract_screen_saver`（L174-323）、`_extract_file_preview`（L326-421）、`_extract_large_file`（L424-464）、`_extract_language_servers` / `_parse_language_server` / `_require_str_list` / `_require_str_map`（L602-741）。

预计行数：742 - 约 130 = 约 610 行，仍低于 800。

### 2.4 `__all__` 调整（L44-58）

`_extract_options` 仍保留（被 `yaterc.py` import）；其余导出的 `_extract_*` 不变。若 2.1 中移除了 `KNOWN_OPTIONS` 的 import，`__all__` 无需变动（它只列本模块符号）。

## 三、详细测试用例（`tests/test_yaterc_options.py` 追加）

1. `test_extract_options_keeps_existing_scalar_behavior`
   - 前置：`config` fixture（`YateConfig()`）；沿用本文件现有 `config` fixture（L35-38）。
   - 操作：`ns = {"keymap": "vim", "theme": "latte", "tab_width": 8, "use_spaces": False, "shell": "pwsh", "terminal_height": 20, "show_hidden": True, "support_mouse": False, "which_key": False, "which_key_auto": False, "key_protocol": "legacy", "yate_trace": True, "yate_trace_level": "info"}`；`_extract_options(ns, config)`。
   - 断言：13 个字段逐项等于给定值，其中 `yate_trace_level == "INFO"`（upper 归一化）；`config.errors == []`。
   - 行为点：遍历表后所有标量仍正确写回且归一化不变。

2. `test_extract_options_reports_invalid_scalars_and_keeps_defaults`
   - 前置：同 fixture。
   - 操作：`ns = {"keymap": "emacs", "tab_width": 0, "terminal_height": 41, "use_spaces": "yes", "yate_trace_level": "NOPE"}`；`_extract_options(ns, config)`。
   - 断言：`config.errors` 长度 5 且逐条含 `keymap must be one of` / `tab_width must be an integer between 1 and 16` / `terminal_height must be an integer between 3 and 40` / `use_spaces must be True or False` / `yate_trace_level must be one of`；对应字段均为 `YateConfig()` 默认值。
   - 行为点：报错文案逐字不变、非法值不写回、其余选项仍生效。

3. `test_extract_options_ignores_unknown_variables`
   - 前置：同 fixture。
   - 操作：`_extract_options({"foobar": 42, "readonly": True}, config)`（两者均非 yaterc 可见）。
   - 断言：`config.errors == []`；`config` 与 `YateConfig()` 的全字段一致（dataclass 相等性可达）。
   - 行为点：`rc_visible=False` 的 spec 不被误写回；未知变量仍静默忽略。

4. `test_extract_options_leaves_dict_options_to_dedicated_extractors`
   - 前置：同 fixture。
   - 操作：`_extract_options({"screen_saver": {"interval": 30}, "large_file": {"threshold": 0}}, config)`。
   - 断言：`config.screen_saver == YateConfig().screen_saver` 且 `config.large_file == YateConfig().large_file`（本函数不处理它们）；随后显式调 `_extract_screen_saver` / `_extract_large_file` 才生效。
   - 行为点：遍历不越界处理 dict 选项，边界清楚。

5. `test_extract_options_bool_rejects_native_string`
   - 前置：同 fixture。
   - 操作：`_extract_options({"support_mouse": "on"}, config)`。
   - 断言：`config.errors` 有一条含 `support_mouse must be True or False`；`config.support_mouse is True`（默认值）。
   - 行为点：yaterc 侧只接原生 bool，字符串 `on` 仍被拒（D7 差异）。

6. **反例演练**（人工，不留测试）：在 `config.py` 的 `OPTION_SPECS` 临时把 `terminal_height` domain 改成 `(3, 41)`，跑本波用例 2 确认「41 不再报错」→ 用例失败；还原后重跑通过。记录到计划回填。

## 四、验证方案

| 目标 | 命令 | 通过标准 |
|---|---|---|
| 类型与全仓静态 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | 退出码 0，零诊断（特别关注 `setattr` 与 `getattr` 的推断） |
| 本波用例 | `.venv\Scripts\python.exe -m pytest tests/test_option_specs.py tests/test_yaterc_options.py -q -n 1` | 退出码 0 |
| 加载器集成 | `.venv\Scripts\python.exe -m pytest tests/test_yaterc.py tests/test_diagnostics.py -q -n 1`（若存在相应文件；否则以 `tests/test_yaterc_options.py` 中经 `load_config` 的用例为准） | 退出码 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 退出码 0，`yaterc_options.py` 仍 UI-free、行数 < 800 |

## 五、风险与回滚

- **风险**：`setattr` 字段名与 `YateConfig` 字段不匹配（拼写漂移）→ 运行期写到一个新属性而非配置字段，测试可能不覆盖。缓解：用例 1 逐字段断言 13 项 + dataclass 相等性用例 3；执行者须核对 `spec.name` 与 `YateConfig` 字段名一一对应。
- **风险**：`invalid_message_fmt` 字段在 plan-a 未落地 → 本波无法引用。缓解：plan-a 已登记该字段为必需；wave-1 验收前确认存在，否则本波停下来上报，不得自行在 `yaterc_options.py` 里再写文案。
- **风险**：报错文案的 `{value!r}` 格式化与现状 f-string 逐字不等（如引号形态）。缓解：用例 2 pin 住子串与关键数值；执行者用 `python -c` 对比改动前后同类输入的完整文案字符串并回填结果。
- **风险**：`yaterc_options.py` 的 `__all__` 中符号因 import 移除而失效。缓解：pyright 与 `tests/test_yaterc_options.py` 的 import 会立即暴露。
- 回滚：本波单独提交 `refactor(yaterc): consume shared option specs`；若 `setattr` fallback 启用，回滚时连同 `_CONFIG_SETTERS` 一并撤销。
