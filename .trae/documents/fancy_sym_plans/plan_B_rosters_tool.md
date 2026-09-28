# plan_B：`python -m tools.pack rosters` 预览生成器 + 临时预览退役

- **状态：已完成（2026-09-27，提交 `c019f22`）**
- 上级：[README](README.md) / 主方案 §2.3
- 工作量：**小**｜依赖：plan_A（读产品位图）

## 目标

1. `tools/pack` 新增 `rosters` 子命令：从 **产品位图**（`yate/
   editor_sprites`）+ 产品渲染器一键重生成放大像素网格全阵容图
   （单一事实源；规划期设计稿退役）。
2. 临时预览目录 `.trae/documents/fancy_sym_preview/` 整体删除。

## 改动文件清单（只改这些）

| 文件 | 动作 | 内容 |
|---|---|---|
| `tools/pack/rosters.py` | 新 | `render_roster_svg(output: Path) -> None`：遍历 `character_names()`，放大像素矩形 SVG（1 像素 = 方块）+ 标题/帧数标注；默认输出 `<repo>/roster.svg`，`--output` 可覆盖 |
| `tools/pack/cli.py` | 改 | 注册 `rosters` 子命令（`--output`，默认 `DEFAULT_OUTPUT`）；docstring 命令表补一行 |

## 实施步骤

1. `rosters.py`：SVG 组装逻辑从设计稿 `make_roster_preview.py` 的
   `sprite_rects`/`label` 移植，数据源换成 `yate.editor_sprites`
   （`get_character()` → `FRAMES`/`PALETTE`）。
2. `cli.py` 注册（对齐既有 `icon` 子命令风格）。
3. 跑通并与设计稿 `roster.svg` 目检比对（造型/颜色一致）。
4. **删除临时目录** `.trae/documents/fancy_sym_preview/`（含
   make_roster_preview.py、roster.svg 基线、__pycache__；位图数据已在
   plan_A 进入产品，基线由本命令随时重生成）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m tools.pack rosters          # 退出 0，重生成 roster.svg
.venv\Scripts\python.exe -m pyright tools/pack/
Test-Path .trae\documents\fancy_sym_preview             # 期望 False
```

## 回滚

新增命令 + cli 一处注册，revert 即除；删除的临时目录不需要恢复。
