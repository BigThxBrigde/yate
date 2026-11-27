# B2：屏保分数中的 Unicode 数字（计划 c）

> **实施状态**：✅ 已实施 —— 2026-11-20（`ac4eda02`，负向用例先红后绿）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/yaterc_options.py:171-202` 中，`_parse_journey_fraction` 在 `:190-191` 使用 `isdigit()`（`'²'.isdigit()` 为 `True`），并在 `:194-195` 直接使用裸 `int()`；由此产生的 `ValueError` 经 `../../../yate/yaterc.py:213-216` 冒泡，并在 `:484-487` 处中断 `_extract_options`，跳过 file_preview 和 large_file。

## 独占文件

- `../../../yate/yaterc_options.py`
- `../../../tests/test_yaterc_options.py`

## 设计

1. 将两处 `isdigit()` 调用都替换为 `isdecimal()`，使非十进制 Unicode 数字在校验阶段即失败，而不会到达 `int()`。
2. 将 `int(numerator) / bottom` 转换包裹在局部 `try/except ValueError` 中，追加与其他无效值相同的友好消息（`screen_saver {key} must be a float in (0, 1) or a fraction like "1/8", got {value!r}`）并返回 `None`。这样任何未来的解析边界都会显式处理，并让 `_extract_options` 继续运行。
3. 不改动可接受的十进制语法、`(0, 1)` 范围检查或提取顺序。不要添加宽泛的 `except Exception`。

## 测试（在 `../../../tests/test_yaterc_options.py` 中先写负向用例）

- `test_parse_journey_fraction_rejects_superscript_digit_with_friendly_error`：调用 `_parse_journey_fraction("²/8", "dist", config)`；断言返回值为 `None`，`config.errors` 恰好有一条记录，包含 `must be a float in (0, 1)` 和 `"²/8"`，且没有异常逸出。
- `test_extract_options_keeps_tail_extractors_after_unicode_fraction_error`：构造一个 rc 命名空间，包含 `screen_saver = {"dist": "²/8"}` 以及有效的 `file_preview` 和 `large_file` 设置；调用 `_extract_options`；断言友好错误已被记录，**并且**后面两个部分的配置都已填充（使用与 `:253` 处 `test_extract_options_still_calls_dict_extractors_at_its_tail` 相同的断言风格）。
- 保持 `:384` 处现有的分数接受用例不变（`"1/8"` 仍能解析为 `0.125`）。

顺序：先添加这两个新测试，运行该文件，观察到两个 `ValueError` 失败，然后打补丁并重新运行。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaterc_options.py -q
.venv\Scripts\python.exe -m pyright yate/yaterc_options.py tests/test_yaterc_options.py
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k option_definitions_have_single_source
```

## 风险 / 回滚

风险：拒绝那些 `int()` 在其他脚本中会接受的 Unicode 十进制数字；`isdecimal()` 对所有十进制数字都与 `int()` 一致，这正是预期的收窄。回滚：恢复 `isdigit()` 并移除局部 `try/except`。
