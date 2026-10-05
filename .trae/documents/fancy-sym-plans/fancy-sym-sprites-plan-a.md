# plan_A：L0 精灵包（渲染 + 注册表 + 27 只角色位图）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
- 上级：[README](overview.md) / 主方案 §2.3 §4.4
- 工作量：**大**（位图绘制为主）｜依赖：无
- 产物：`yate/editor_sprites/` 包 + `tests/test_editor_sprites.py`

## 目标

1. L0 纯逻辑精灵包：半格块逐像素渲染（无 Textual 依赖）、角色注册表、
   shuffle 轮播、行走 x 坐标计算。
2. 27 只角色位图按主方案 §4.4 规格（全角色 ≥2 帧、帧同尺寸、调色板键
   齐全）落成数据模块。

## 非目标

- 不碰 Textual / Screen（plan_D）；不做 PNG 导入（后续增强）；
  不做配置解析（plan_C）。

## 改动文件清单（只改这些）

| 文件 | 动作 | 内容 |
|---|---|---|
| `yate/editor_sprites/__init__.py` | 新 | 惰性包 docstring，不 re-export（§三.5） |
| `yate/editor_sprites/render.py` | 新 | 类型 `Frame`/`Palette`/`Glyph`；`walk_x(tick, width, sprite_w, span_px)`；`render_cells(frame, palette, tick)` → 每列 `(glyph, color)` 纯函数 |
| `yate/editor_sprites/characters.py` | 新 | 注册表 `CHARACTERS: dict[str, Sprite]`；`character_names()`；`get_character(name)`；`shuffle_order(names, rng)` 不连续重复 |
| `yate/editor_sprites/chars/` | 新 | 27 个数据模块（mario.py、goomba.py、…、slime.py），每模块 `FRAMES + PALETTE` 常量 |
| `tests/test_editor_sprites.py` | 新 | 见验收 |
| `tests/test_architecture.py` | 改 | `UI_FREE_PACKAGES`（:84）增 `"editor_sprites"`——新 L0 包纳入 R12 UI-free 守卫（v6.1 复核新增项） |

## 实施步骤

1. **类型与渲染函数**：`render.py` —— 半格块四形态
   （同色`█`/异色`▀ fg on bg`/单边`▀`或`▄`/空格）、`walk_x` 溢出回绕。
   算法与设计稿 `make_roster_preview.py::halfblock_lines` 一致。
2. **数据模块**：从设计稿 `.trae/documents/fancy_sym_preview/
   make_roster_preview.py` 迁移 27 组位图（ASCII 行 → `tuple[str, ...]`，
   调色板键 → hex 色），每模块导入时断言帧同尺寸、键齐全。
   ghost×4 共用 `_ghost.py` 模板换色。
3. **注册表**：`characters.py` 汇总 + shuffle（`random.shuffle` 全排列、
   耗尽重洗、相邻不重复）。
4. **测试**。

## 验收命令（worktree 根目录）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_editor_sprites.py -q
.venv\Scripts\python.exe -m pyright yate/editor_sprites/
```

测试断言清单：半格块四形态各 1 例；`walk_x` 回绕；每只角色帧同尺寸；
调色板键齐全；**全角色 ≥2 帧**；`character_names() == 27`；
`shuffle_order` 500 次无相邻重复。

## 回滚

纯新增包，revert 即除。
