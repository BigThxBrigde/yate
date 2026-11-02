# readme-screenshots plan-b：生成截图与画廊（wave-2）

> 前置：plan-a 验收全绿。总纲：`readme-screenshots-plans/overview.md`。

## 输入

plan-a 交付的 `tools/screenshots` 包（含 25 场景注册表与画廊生成器）。

## 独占文件清单（只产出这些）

- `screenshots/*.svg`（25 个，注册表名称逐一对应）
- `screenshots/README.md`（工具生成，不手改；若需改文案→改注册表重生成）

## 操作

```powershell
.venv\Scripts\python.exe -m tools.screenshots
```

- 全量生成（含三个慢速子进程场景：smoke-report / diag-report / pytest-pyright）；
- 逐个检查生成日志：任何场景失败 → 重试一次（`--only <name>`）；仍失败 →
  该场景按总纲风险条款处理（登记非目标、画廊自动随之缺节），不得静默跳过；
- 人工抽查（无人值守下以可观测产物代替）：`Get-ChildItem screenshots` 数量 25、
  抽 3 个 SVG 头部含 `class="rich-terminal"`、画廊含 25 个 `### ` 节。

## 验收命令

```powershell
(Get-ChildItem screenshots -Filter *.svg).Count          # 期望 25
Select-String -Path screenshots/README.md -Pattern '^### ' | Measure-Object  # 期望 25
.venv\Scripts\python.exe -m tools.screenshots --only welcome-screen   # 再生确定性抽查
git -C . status --short -- screenshots                   # 再生后无意外 diff（确定性实证）
```

通过判定：数量断言通过；重复生成同一场景 SVG 字节级一致（调研结论 1 的落地验证）。

## 风险与回滚

- 慢速子进程场景（pytest 全量 ~2 分钟）失败不影响其余场景；
- 回滚：删除 `screenshots/` 目录（生成产物，无源码影响）。
