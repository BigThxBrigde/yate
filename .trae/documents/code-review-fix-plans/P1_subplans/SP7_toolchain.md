# SP7 — 工具链（S22 + S23 + S25 + S27）

> 来源：[P1 批次五（S22/S27）](../P1_suggestions_plan.md)、
> [批次四（S23）](../P1_suggestions_plan.md)、[批次二（S25）](../P1_suggestions_plan.md)。
> 仅涉及 `tools/` 与 `tests/`，无需产品源码授权，可直接下发子代理。
> 统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S22 | [changelog/cli.py:92](../../../../tools/changelog/cli.py) | `generate()` 用 `date.today()`，输出不可复现 | S |
| S23 | tests/test_changelog_tool.py | `--limit` 无测试 | S |
| S25 | [segments.py:102、:122](../../../../tools/changelog/segments.py) | `position` 一名两义（段序号 vs commit 位置） | S |
| S27 | [release/cli.py:63-75](../../../../tools/release/cli.py) | `files_dirty` 对带空格/引号路径的 porcelain 解析粗糙 | M |

## 独占文件清单（只许改这些）

- `tools/changelog/cli.py`
- `tools/changelog/segments.py`
- `tools/release/cli.py`
- `tests/test_changelog_tool.py`、`tests/test_release_tool.py`（新增用例）

## 实施步骤

1. **第 0 步 复核**：四条锚点逐一确认（重点 S27：当前解析是否仍为
   `line[3:].strip().strip('"')`；注意 release/cli.py 已含 C6 修复
   `_default_branch` / `--branch`，不得回退）。
2. **S22**：`generate(..., date: Optional[str] = None)`；CLI 加 `--date YYYY-MM-DD`；
   未给时保持 `today()`。验收：传 `--date` 断言输出段头日期；不传回退 today。
3. **S23**：`tests/test_changelog_tool.py` 补两条——`--limit 1` 只出最新 1 条；
   `--limit 0` / 负数按实现固化为断言（报错或空输出，以实测为准并注明）。
4. **S25**：循环变量改名 `seg_index`（segments.py:102-110），:122 的 `position` 保持；
   纯重命名零行为变化。
5. **S27**：`files_dirty` 改 `git status --porcelain -z`（NUL 分隔，无引号歧义）解析；
   返回签名不变。验收：临时仓库建带空格 / 引号文件名的 dirty 文件，断言返回准确路径
   （用例放 `tests/test_release_tool.py`，沿用既有真实临时 git 仓库 + skip 模式）。
6. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright tools/changelog/cli.py tools/changelog/segments.py tools/release/cli.py tests/test_changelog_tool.py tests/test_release_tool.py
   .venv\Scripts\python.exe -m pytest tests/test_changelog_tool.py tests/test_release_tool.py -q
   ```

## 注意

- `tools/release/cli.py` 与 `tools/changelog/cli.py` 刚完成 P0 C6/C7 修复：
  改动必须叠加在其上，动手前先读当前文件确认 P0 产物在位。
- S27 与 C6 的 `--branch` 无冲突，但同文件改动建议一次提交内完成以便回滚。
