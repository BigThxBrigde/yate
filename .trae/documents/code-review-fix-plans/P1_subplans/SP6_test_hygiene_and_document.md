# SP6 — 测试卫生与文档内核（S20 + S21 + S29 + S41）

> 来源：[P1 批次四（S20/S21/S29）](../P1_suggestions_plan.md)、
> [批次七（S41）](../P1_suggestions_plan.md)。统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S20 | [test_lsp.py:847](../../../../tests/test_lsp.py) | 30 秒 sleep 子进程拖慢清理路径测试 | S |
| S21 | [test_theme_palettes.py:271](../../../../tests/test_theme_palettes.py) | 硬编码版本 `"0.2.4"` 与发版耦合 | S |
| S29 | [test_editor_core.py:394-406](../../../../tests/test_editor_core.py) | `_FakeApp` 未实现全部 hooks，新 action 即 AttributeError | M |
| S41 | [document.py:86-88](../../../../yate/editor_core/document.py) | dirty 态下每次 `modified` 查询 O(N) tuple 分配 | M |

## 独占文件清单（只许改这些）

- `tests/test_lsp.py`（仅 S20 目标处）
- `tests/test_theme_palettes.py`
- `tests/test_editor_core.py`
- `yate/editor_core/document.py`

## 实施步骤

1. **第 0 步 复核**：四条锚点逐一确认（重点 S41：现状是否仍走回退路径的行元组比较）。
2. **S20**：`time.sleep(30)` 改自终止脚本 `time.sleep(2)`，测试断言上限收窄。
   验收：该用例耗时显著下降且仍覆盖清理失败路径。
3. **S21**：改 semver 解析断言 `re.fullmatch(r"\d+\.\d+\.\d+", ...)` + 非空校验；
   保留 `test_pyproject_keeps_the_single_dynamic_version_source`。
4. **S29**：`_FakeApp` 加 `__getattr__` 返回记录调用的 no-op，docstring 注明
   「新 action 默认 no-op」。验收：新增 action 不再 AttributeError，且测试可断言被调。
5. **S41**：按 `content_edits` 计数缓存上次判定（计数不变直接返回缓存布尔，变化才重算
   并刷新缓存）。验收：现有 modified / undo / redo 用例全绿；新增跨 undo 判定正确性断言。
6. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright tests/test_lsp.py tests/test_theme_palettes.py tests/test_editor_core.py yate/editor_core/document.py
   .venv\Scripts\python.exe -m pytest tests/test_editor_core.py tests/test_theme_palettes.py tests/test_lsp.py -q
   ```

## 注意

- S20 只动目标用例，`test_lsp.py` 其余 900+ 行不改（该文件是 P0 守卫所在地）。
- S41 是唯一产品源码改动（`document.py`，L0 叶子），任务书显式授权。
