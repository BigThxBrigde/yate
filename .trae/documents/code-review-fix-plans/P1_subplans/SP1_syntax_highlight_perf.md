# SP1 — 语法高亮内核性能（S1 + S2）

> 来源：[P1 批次一](../P1_suggestions_plan.md)。纯性能改造，零行为变化。
> 统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点                                                                         | 内容                                                                   | 规模 |
| -- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------- | -- |
| S1 | [regex\_backend.py:412-431](../../../../yate/editor_syntax/regex_backend.py) | `_code_line_pattern(spec)` 每次 tokenize 重新编译；`tokenize_document` 逐次调用 | M  |
| S2 | [regex\_backend.py:674-676](../../../../yate/editor_syntax/regex_backend.py) | 配置模式布尔词在行循环内编译 7 次/行                                                 | S  |

## 独占文件清单（只许改这些）

- `yate/editor_syntax/regex_backend.py`
- `tests/test_highlight.py`（仅新增用例）

## 实施步骤

1. **第 0 步 复核**：读上表锚点行，确认两处仍在。输入 = P1 证据行号；输出 = 复核结论。
2. **S1 缓存**：确认 `LangSpec` 可哈希（dataclass 冻结 / 字段无 list；若含可变字段，
   按 P1 备注改 `field(default=tuple)` 或按 `id(spec)` 缓存并注明）。然后
   `@lru_cache(maxsize=None)` 包装 `_code_line_pattern`。
   验收：tokenize 输出与改造前逐 token 一致。
3. **S2 预编译**：新增模块级 `_CONFIG_BOOL_RE = re.compile(r"(?<!\w)(?:true|false|null|yes|no|on|off)(?!\w)")`，
   循环内改用 `finditer`。验收：`on/off/yes/no` 命中、`only`（词内）不命中。
4. **守卫测试**（`tests/test_highlight.py` 新增）：
   - `_code_line_pattern(spec) is _code_line_pattern(spec)` 缓存命中断言；
   - S2 布尔词边界两断言。
5. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright yate/editor_syntax/regex_backend.py tests/test_highlight.py
   .venv\Scripts\python.exe -m pytest tests/test_highlight.py tests/test_syntax_engine.py -q
   ```

## 注意

- 若复核发现 `LangSpec` 不可哈希，采用 `id(spec)` 方案时必须同步考虑 spec 生命周期
  （缓存泄漏），并在报告中说明取舍。
- 本子计划不改 `test_syntax_engine.py`（只跑不改）。

