# I 波：双语文档（`games.*.md` + 扩展手册 + CHANGELOG）

上级：[overview.md](overview.md) ｜ 依赖：C-G 行为定稿 ｜ 独占文件：
`yate/docs/games.en.md`（新）、`yate/docs/games.zh.md`（新）、`yate/docs/README.md`、
`yate/docs/extensions.en.md`、`yate/docs/extensions.zh.md`、`CHANGELOG.md`、`CHANGELOG.zh.md`

## 一、目标

1. 新增**游戏手册**（中英成对）：玩法、键位、计分、存档格式、可继续玩的语义、
   字形切换、玩家名，以及「用 `game_engine` 写自己的游戏」的模块契约与最小示例。
2. 扩展手册（中英成对）补：bundled 清单加入游戏包、`api.data` 小节（4.15）、
   §6 新增「共享 Lua 模块（`extensions/lib/`）」小节、附录函数表补 4 行。
3. `yate/docs/README.md` 的指南清单补 `games.*.md`（中英两半都要改）。
4. CHANGELOG **不手改**：由 `python -m tools.changelog generate` 从提交历史生成
   （文件头已声明 `do not edit by hand`）；本波只执行生成命令并提交产物。

## 二、`games.en.md` / `games.zh.md` 章节结构（两文件节号一一对应）

| 节 | 内容要点（英文版写作要点 / 中文版为对照译文） |
|---|---|
| 1. Quick start | `:game` 列出可用游戏；`:game snake` 启动；`escape` 退出；`r` 重开。画布是 modal，键盘不落到编辑器 |
| 2. The `:game` command | 参数语法 `:game <name>` / `:game player` / `:game player <name>`；三条错误文案（usage / unknown / already running）逐字列出 |
| 3. Games | 5 个子节：snake / pacman / sokoban / nethack / tetris，每节含：画面示意（代码块，等宽）、键位表、计分规则、胜负条件 |
| 4. Saved data | 路径 `~/.yate/data/games/`；每文件一个表格（字段 / 类型 / 含义）；`sokoban` 与 `nethack` 的「继续玩」语义；坏文件回退行为；如何手动清档（删文件 / `yate.data.remove`） |
| 5. Player name and score authors | 默认取 OS 用户名；`:game player <name>` 覆盖；最高分榜记录 `player` 与本地时间 |
| 6. Glyphs (NetHack) | nerd 默认、`v` 切换、ASCII 回退；字体前提（Nerd Font）；字形表 12 行（语义 / nerd 码位 / ascii） |
| 7. Writing your own game | 文件放哪（`yate/extensions/*.lua` 或用户目录）、`require("game_engine")` 契约表（§三 全表）、`setup/teardown/snapshot` 约定、**最小可运行示例**（约 30 行：红点上下移动 + 最高分）、如何用 `yate.data` 存 JSON |
| 8. Lua lint | `python tools/lint_lua.py`、九条规则表、退出码、如何跳过（不提供，说明是硬门禁） |

写作约束：

- 与 `yate/docs/README.md` 的定位一致：本目录是**站外权威**；不复制扩展手册的 API 细节，
  用相对链接 `[extensions.en.md](extensions.en.md)` 交叉引用。
- 文中**不得出现本机绝对路径**（`doc-conventions.md` §五）；家目录一律写 `~/.yate/data/games/`。
- 中文版用中文标点、代码标识符保持英文；两份文件节号与表格行数必须一致。

## 三、`extensions.en.md` / `extensions.zh.md` 增补

1. §2 清单（`extensions.en.md:49-55` 一带）：bundled 追加
   「`games`（the `:game` launcher for the bundled game pack）以及 `snake` / `pacman` / `sokoban` /
   `nethack` / `tetris`；共享 Lua 模块位于 `yate/extensions/lib/`（不会被当作扩展装载）」。
2. 新小节（放在 4.14 之后）：`### 4.15 Persistent data (api.data)`：

```markdown
`api.data` reads and writes small UTF-8 text documents under `~/.yate/data`.
It is the only file channel an extension gets: names are relative, absolute
paths and `..` are rejected (`ValueError`, surfaced to Lua as a Lua error or a
`false` return), and every write is atomic (temp file + replace).

| Lua | Returns |
|---|---|
| `yate.data.read(name)` | text, or `nil` when missing |
| `yate.data.write(name, text)` | `true` / `false` |
| `yate.data.remove(name)` | `true` / `false` (whether it existed) |
| `yate.data.list(prefix)` | Python list of names in a sub-directory (0-based) |

Bundled games keep one JSON document per game under `games/` -- see
[games.en.md](games.en.md) for the schemas.
```

   中文版同义对照。
3. §6「Lua extensions」新增子节 `### Shared Lua modules (extensions/lib/)`：
   - 目录约定、`require("<stem>")`、每个 runtime 各自一份副本（互不共享状态）、
     `lib/` 不会被 loader 当扩展、新增模块无须改 Python（loader 自动预载）、
     模块里**不得**定义 `setup`/`teardown`；
   - 示例：`local engine = require("game_engine")`。
4. 附录函数表（`extensions.en.md:919-927` 一带）补 4 行 `yate.data.*`。

## 四、`yate/docs/README.md`

英文清单补 `- games.*.md -- the bundled game pack and the shared game engine;`，
中文清单补 `- games.*.md -- 随身游戏包与共享游戏引擎；`。

## 五、CHANGELOG

```powershell
.venv\Scripts\python.exe -m tools.changelog generate
```

- 该命令从 git 历史重新生成 `CHANGELOG.md` / `CHANGELOG.zh.md`；新条目的中文译文可能缺失
  （`--require-zh` 只在发布流程里用），本波**不**追求 `--require-zh` 绿。
- 若工具在 worktree 下行为异常（例如需要主分支名），记录实测输出并改为主代理手工把
  「本任务提交条目」追加到 Unreleased 段落——但优先用工具。

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py tests/test_manual.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

文本自检（人工）：

```powershell
Select-String -Path yate\docs\games.*.md -Pattern 'C:\\Users|/home/|d:\\'
```

必须无命中（`doc-conventions.md` §五）。

## 七、风险

| 风险 | 缓解 |
|---|---|
| 中英两版漂移 | 按节号逐一对照；写完用同一份表格复制翻译 |
| 与扩展手册重复描述 API | 游戏手册只讲游戏与引擎契约，API 细节链接到扩展手册 |
| CHANGELOG 工具依赖 git 历史 | 只有在提交之后运行；失败则按第五节兜底并如实记录 |
| 文档引用绝对路径 | 第四节自检命令 + `doc-conventions.md` §五 |
