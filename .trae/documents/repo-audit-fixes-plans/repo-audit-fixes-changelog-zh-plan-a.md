# 子计划 plan-c：CHANGELOG 中文翻译清偿（A5-①）

> 所属波次：**wave-1**（与 rules-docstring / tests-guard / assets 文件不重叠，可并行）。
> 执行者：**子代理**（仅 `tools/changelog/zh_overrides.json` 与根级 `CHANGELOG.zh.md` 刷新）。
> 来源：评审 A5；调研事实 F1（`--require-zh` 已存在但语义需修正——语义修正属 wave-5 plan-e，本计划只清偿存量）。

## 一、输入

- `CHANGELOG.zh.md` 未发布 + v0.2.9 区段 40+ 条 `[缺中文]` 占位（实测 36+ 处 grep 命中且输出截断）；
- `tools/changelog/zh_overrides.json`（34.89 KB）未跟上新增提交；
- 机制：`python -m tools.changelog zh-commit <hash> <summary> [<detail>]` 逐条 upsert（`tools/changelog/translations.py`）；`python -m tools.changelog generate` 用 overrides 重渲双语文件；`python -m tools.changelog check` 校验已发布区段新鲜度并打印 `missing zh` 统计。

## 二、独占文件清单

1. `tools/changelog/zh_overrides.json`
2. `CHANGELOG.zh.md`（仅经 `generate` 命令刷新，不手工编辑）

## 三、执行步骤

1. 列出缺失清单：
   ```powershell
   .venv\Scripts\python.exe -m tools.changelog check
   ```
   记录输出 `missing zh: <hash, ...>` 与 `stats` 行的 missing 计数（执行前基线）。
2. 对每个缺失 short_sha，从 `CHANGELOG.md` 对应条目取英文 summary，翻译为简体中文后 upsert：
   ```powershell
   .venv\Scripts\python.exe -m tools.changelog zh-commit <short_sha> "<中文 summary>"
   ```
   术语以 `tools/changelog/zh_overrides.json` 存量条目为准（扩展/键映射/工作区/屏保精灵/语法高亮等）；`docs:` 类提交的 summary 保持简洁动宾式，与相邻已译条目风格一致。
3. 全部 upsert 后刷新双语文件并复核：
   ```powershell
   .venv\Scripts\python.exe -m tools.changelog generate
   .venv\Scripts\python.exe -m tools.changelog check
   ```
   `check` 输出 `missing zh translation(s)` 必须为 **0**；`CHANGELOG.zh.md` 中 `[缺中文]` 零命中。
4. git diff 自查：`CHANGELOG.md`（英文侧）不得有任何变化（overrides 只影响 zh 渲染）；若 en 侧出现 diff，说明 generate 引入了意外行为，停止并上报。

## 四、验证方案

- 验证目标：zh 覆盖断档清零，为 wave-5 plan-e 启用 `--require-zh` 门禁建立基线。
- 命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m tools.changelog check
.venv\Scripts\python.exe -m pytest tests/test_changelog_tool.py -q
```

- 附加断言：`Select-String -Path CHANGELOG.zh.md -Pattern "缺中文"` 零命中。
- 手工验证：抽读 v0.2.9 区段 10 条译文，确认无机翻痕迹、术语与旧条目一致。

## 五、风险与回滚

- 风险 R4（主计划）：翻译质量/术语不一致 → 以存量 overrides 术语表为准，逐条人工可读性检查；`generate` 可能重排未发布区段（属工具预期行为，check 的 released-only staleness 门禁兜底）。
- 注意：清偿后若主分支有新提交进入未发布区段，missing 计数会重新上涨——本计划验收以**执行时点的 git 历史**为准；wave-5 启用门禁前需再跑一次清偿增量。
- 回滚：`git checkout -- tools/changelog/zh_overrides.json CHANGELOG.zh.md` 单命令还原。
