# plan-b：移除推箱子设计信息（双语文档）

> 隶属 [总纲 overview.md](overview.md)，wave-1。执行者：主代理（理由见总纲 §三）。
> 硬约束：`yate/docs/` 双语手册必须同时新增、同时更新（doc-conventions §三）。

## 一、输入

- 总纲 §一目标 1；`yate/docs/games.en.md` / `games.zh.md` /
  `extensions.en.md` / `extensions.zh.md` 现状。

## 二、独占文件清单（只许改这些）

| 文件 | 动作 |
|---|---|
| `yate/docs/games.en.md` | 删推箱子条目 + §3.3 整节 + 重编号 |
| `yate/docs/games.zh.md` | 镜像同改 |
| `yate/docs/extensions.en.md` | 游戏包清单去 sokoban |
| `yate/docs/extensions.zh.md` | 镜像同改 |

## 三、具体修改（定位到行）

1. **`yate/docs/games.en.md`**：
   - 30 行表格行 `| Sokoban | :game sokoban | push every crate onto a goal |` 删除；
   - 38 行 usage 串 `(games: nethack pacman snake sokoban tetris)` 改
     `(games: nethack pacman snake tetris)`；
   - 112-147 行 `### 3.3 Sokoban` 整节（含 ASCII 画、按键表、规则段、
     存档段）删除；
   - 149 行 `### 3.4 NetHack` 改 `### 3.3 NetHack`；
   - 176 行 `### 3.5 Tetris` 改 `### 3.4 Tetris`；
   - 215 行 `| sokoban.json | ... |` 存档表行删除；
   - 279 行 `engine.glyph` 示例词表 `` (`block`, `shade`, `box`, `dot`, …) ``
     改 `` (`block`, `shade`, `mid`, `dot`, …) ``（`box` 字形随 plan-a 删除，
     换成仍在词表中的 `mid`）。
2. **`yate/docs/games.zh.md`**（镜像）：
   - 27 行表格行 `| 推箱子 | :game sokoban | 把所有木箱推上目标点 |` 删除；
   - 35 行 usage 串同步去 sokoban；
   - 45 行 「五款游戏共用同一套版式」 改 「四款游戏共用同一套版式」；
   - 105-136 行 `### 3.3 推箱子` 整节删除；
   - 138 行 `### 3.4 NetHack` 改 `### 3.3 NetHack`；
   - 163 行 `### 3.5 俄罗斯方块` 改 `### 3.4 俄罗斯方块`；
   - 200 行 `| sokoban.json | ... |` 行删除；
   - 256 行字形词表 ``（`block`、`shade`、`box`、`dot` …）`` 改
     ``（`block`、`shade`、`mid`、`dot` …）``。
3. **`yate/docs/extensions.en.md`**：51 行 `snake` / `pacman` / `sokoban` /
   `nethack` / `tetris` 清单删 `sokoban`。
4. **`yate/docs/extensions.zh.md`**：45 行同镜像。

不改动四个 changelog 生成文件（否决理由见总纲 R1）。

## 四、测试用例

无新增测试（文档变更）。回归面：`tests/test_mdlint.py`（md lint 守卫）
与 `tests/test_pack_wiki.py`（wiki 从文档生成，无 sokoban 硬编码，已扫描
确认）。两文段落重编号后全文无交叉引用依赖 `### 3.3/3.4/3.5` 锚点
（已扫描 games.*.md 全文，仅标题行本身）。

## 五、验收命令（wave-1 内执行，均退出码 0）

```powershell
Set-Location D:/Programming/yate-games
git grep -n -i sokoban -- yate/docs
.venv/Scripts/python.exe -m pytest tests/test_mdlint.py tests/test_pack_wiki.py tests/test_manual.py -q
```

`git grep` 必须零命中；pytest 退出码 0。

## 六、风险与回滚

- 双语漏改一侧 → grep 断言红 + 人工 diff 复查，补齐；
- wiki / 手册测试对文档结构有隐藏依赖 → 由 §五 pytest 暴露，按需修正措辞
  （不改结构语义）；
- 回滚：按文件 revert 本笔提交。

## 七、执行记录（回填区）

- 待回填：实测命令结果与退出码。
