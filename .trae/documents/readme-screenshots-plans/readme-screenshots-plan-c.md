# readme-screenshots plan-c：README 双语链接画廊（wave-3）

> 前置：plan-b 产物落盘。总纲：`readme-screenshots-plans/overview.md`。
> 双语硬约束：README.md 与 README.zh.md 同步新增、同构排版（doc-conventions §三/§四）。

## 独占文件清单（只改这两个）

- `README.md`
- `README.zh.md`

## 修改设计

在两份 README 的 `## Features` 节**之前**插入同构小节（节名与文案对齐双语习惯）：

English（README.md）：

```markdown
## Screenshots

Every feature has a generated screenshot with a scenario walkthrough in the
[screenshots gallery](screenshots/README.md) (`python -m tools.screenshots`
regenerates all of them headlessly via Textual's pilot).

![yate — layout with explorer, tabs and syntax highlighting](screenshots/layout-explorer.svg)
```

中文（README.zh.md）：同位置同构，说明文案为中文，图片路径与 alt 一致
（alt 用英文场景名保证两侧指向同一资产）。

硬性要求：

- 不改动两文件其余任何内容（最小 diff）；
- 相对路径引用（doc-conventions §五）：`screenshots/README.md`、
  `screenshots/layout-explorer.svg`；
- 根级文件名不动（doc-conventions §四）。

## 验收命令

```powershell
git diff --stat -- README.md README.zh.md    # 仅 +<小节> 行数
Select-String -Path README.md -Pattern 'screenshots/README.md'
Select-String -Path README.zh.md -Pattern 'screenshots/README.md'
```

通过判定：两文件各含画廊链接与 hero 图；diff stat 显示仅插入无删除；其余内容
零改动。

## 风险与回滚

- Gitee/GitHub 对 SVG 的渲染差异：hero 图若不显示，画廊页仍可读（已登记已知
  限制，不阻塞）；回滚：revert 本步提交（与 plan-a/b 分开提交，见提交纪律）。
