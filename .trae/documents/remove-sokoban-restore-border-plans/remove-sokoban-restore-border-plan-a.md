# plan-a：移除推箱子代码与测试

> 隶属 [总纲 overview.md](overview.md)，wave-1。执行者：主代理（理由见总纲 §三）。

## 一、输入

- 总纲 §一目标 1；本文件 §二 的定位清单。
- 前置调研事实：`sokoban.lua` 约 1034 行，经 `G.*`（`engine.glyph`）与
  字面量消费共享字形；派发/发现链动态，删文件即生效。

## 二、独占文件清单（只许改这些）

| 文件 | 动作 |
|---|---|
| `yate/extensions/sokoban.lua` | 删除 |
| `yate/extensions/lib/engine_layout.lua` | 删 4 个推箱子专属字形条目 |
| `tests/test_lua_game_sokoban.py` | 删除 |
| `tests/test_lua_games_visual.py` | 删 `_GEOMETRY` 与 `_NO_ASCII_PLACEHOLDERS` 中的 sokoban 项 |
| `tests/test_lua_games_app.py` | 删 `_CANVAS_SIZES` 中的 sokoban 项；docstring five→four |
| `tests/test_lua_engine.py` | `_GAME_NAMES` 去 sokoban；两处期望串去 sokoban；注释 Five→Four |

## 三、具体修改（定位到行）

1. **`yate/extensions/sokoban.lua`**：整文件删除（git `rm`）。
2. **`yate/extensions/lib/engine_layout.lua`** `layout.glyph` 表（37-64 行）：
   删除且仅删除以下 4 个条目（`git log -S` 实证均由推箱子提交 `ceaaabb`
   引入，全仓扫描无任何在用方——`engine.glyph.*` 与字面量双口径）：
   - 47 行 `light = "░",`
   - 48 行 `box = "▣",`
   - 49 行 `box_on_goal = "▩",`
   - 50 行 `goal = "◎",`
   其余条目（`block`/`shade`/`mid`/`dot`/`big_dot`/`star`/`tri` 等在用）
   一律保留。
3. **`tests/test_lua_game_sokoban.py`**：整文件删除（git `rm`）。
4. **`tests/test_lua_games_visual.py`**：
   - 18 行 `"sokoban": (41, 22),` 删除；
   - 23 行 `_NO_ASCII_PLACEHOLDERS = ("snake", "tetris", "pacman", "sokoban")`
     改为 `("snake", "tetris", "pacman")`。
5. **`tests/test_lua_games_app.py`**：
   - 32 行 `("sokoban", 41, 22),` 删除；
   - 第 5 行 docstring "the five ``game-*`` actions" 改 "the four"。
6. **`tests/test_lua_engine.py`**：
   - 30 行注释 "Five registered game actions" 改 "Four registered game actions"；
   - 31 行 `_GAME_NAMES` 改 `("nethack", "pacman", "snake", "tetris")`；
   - 87 行期望串改
     `"usage: :game <name> (games: nethack pacman snake tetris)"`；
   - 101 行期望串改
     `"unknown game: chess (available: nethack pacman snake tetris)"`。

## 四、测试用例

无新增测试。理由：本子计划是纯移除（删文件 + 删字典项 + 删期望串中的
一个名字），被删行为原本由 `tests/test_lua_game_sokoban.py` 覆盖，随代码
同源消亡；回归面由下列既有测试承担，不引入任何新行为，无新断言可写。

## 五、验收命令（wave-1 内执行，均退出码 0）

```powershell
Set-Location D:/Programming/yate-games
.venv/Scripts/python.exe -m pytest tests/test_lua_engine.py tests/test_lua_games_visual.py tests/test_lua_games_app.py tests/test_canvas_screen.py -q
.venv/Scripts/python.exe -m tools.lint_lua
git grep -n -i sokoban -- yate tests
```

`git grep` 判定：`yate/` 与 `tests/` 下仅允许 `yate/resources/changelog.en.md`
与 `yate/resources/changelog.zh.md` 两个生成文件命中（历史提交记录，
总纲 R1）；其余任何命中即失败。

## 六、风险与回滚

- 动态派发期望串漏改 → 测试红，按 §三第 6 条补改；
- 字形误删 → 全量 lua 测试红（snake/pacman 的字形均在保留清单），按文件
  revert 本笔提交。

## 七、执行记录（回填区）

- 2026-10-21 实测：`pytest tests/test_lua_engine.py tests/test_lua_games_visual.py
  tests/test_lua_games_app.py tests/test_canvas_screen.py -q` → 全过，退出码 0；
  `tools.lint_lua` → `0 issue(s)`，退出码 0；残留扫描仅命中 4 个 changelog
  生成文件与历史计划文档（裁定见总纲执行记录第 5 条）。
- 偏离：`git add` 因已删除文件的 pathspec 报错整体未暂存，本子计划产物拆为
  两笔提交——`14c31d5`（两个整删文件）+ `5a24001`（字形清理与测试期望），
  合计构成 plan-a，不 amend（git 安全协议）。
