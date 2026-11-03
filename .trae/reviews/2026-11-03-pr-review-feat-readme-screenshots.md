# 2026-11-03 pr-review · `feat/readme-screenshots` 合并前预评审

> AI 预评审，合并决策归人工。verdict 行见 §七。

## 一、评审信息

| 项 | 值 |
|---|---|
| 日期 | 2026-11-03 |
| 分支 | `feat/readme-screenshots` @ `fad775d`（worktree `yate-readme-screenshots`） |
| 基线 | `origin/master` = `aea1da4`（评审期间 IDE 后台 fetch 使基线由 `c5b09a5` 两次前移，分支随之二次合并，见 §四） |
| 范围 | `origin/master..HEAD`：17 提交 / 41 文件 / +7230−2 |
| 依据 | pr-review skill（六维度 + 硬门禁 + verdict）；`task-orchestration.md` 关键词任务流程 |
| 执行者 | `pr-reviewer` 子代理交付 Phase-1 范围事实（41 文件 +7230−2、核心代码 1240 行）后失联：经 2×15 分钟窗口 + 探活无应答、零落盘产物，按 §五.3 判死；**主代理接管完成评审并如实标注**（本会话第三起子代理死亡事件） |

## 二、提交链（17 笔，主题均符合 `git-commit-message.md`）

```
fad775d Merge remote-tracking branch 'origin/master' into feat/readme-screenshots
8768fde chore(screenshots): refresh frames against master after the merge
ddf36f5 refactor(tools): follow the editor_components rename from master
0283398 Merge remote-tracking branch 'origin/master' into feat/readme-screenshots
efdacc4 docs(review): record the user-feedback fix round for readme-screenshots
9104aee fix(tools): keep frames well-formed XML and embed the icon font
de1cc15 docs(review): record the second independent review round
99edb8a docs(readme): list screenshots/ and tools/screenshots in project layout
fc2875c chore(screenshots): regenerate with fixed fixture name and scrubbed paths
1867b9b fix(tools): enforce reached states, timeouts and path scrubbing
c2c031a docs(review): record readme-screenshots review and backfill plans
afcaf5f fix(tools): render the gallery from all scenarios with an existing SVG
2a85b8a refactor(tools): type the game-scenario screen predicate
2acf2da docs(readme): link the screenshots gallery from both READMEs
509f88f feat(screenshots): generate feature screenshots and gallery
0d43285 feat(tools): add headless screenshot generator for README features
2e311e8 docs(plans): add readme-screenshots plan suite
```

粒度评估：工具 / 产物 / 文档 / 记录分离清晰，修复轮各自成笔（`9104aee` 一笔覆盖
XML 转义 + 字体嵌入，属同一用户反馈闭环，可接受）；无夹带无关变更。

## 三、六维度评审

| 维度 | 结论 | 证据 |
|---|---|---|
| 功能性 | 通过 | 用户反馈三缺陷当轮修复：裂图（`scrub_svg` XML 转义 + C0 caret 记号，ET.fromstring 可解析）、Nerd Font 方框（`embed_icon_font` 收集 PUA U+E000–F8FF → fontTools 子集 WOFF2 → `@font-face` data-URI 注入，任意机器可渲染）、pytest 报告帧移除（25→24，`cli_reports.py` 同步瘦身）；which-key 交错动画 1.5s settle 后确定性（SHA256 复验一致） |
| 安全性 | 通过 | 机器路径脱敏为 `&lt;home&gt;/&lt;repo&gt;/&lt;user&gt;` 等占位符并全量扫描归零（前轮 A2）；fontTools 子进程参数固定、显式 `--output-file` 写入自有临时目录（修复 CLI 无 stdout 模式旁落写盘污染字体目录的缺陷，污染文件已删）；无用户输入进 shell |
| 性能 | 通过 | 24 帧 SVG 共 2037 KB（最大 `split-panes.svg` 216 KB）；WOFF2 子集仅含用到的码点；工具一次性生成，无运行时开销 |
| 可维护性 | 通过 | `tools/screenshots` 模块边界清晰；`tests/test_screenshots_tool.py` 新增 XML 安全与字体嵌入两道守护用例（helper 正确标注 `DriverFn`，无 `type: ignore`） |
| 架构 | 通过 | 仅新增顶层工具 `tools/screenshots/`（自上而下 import yate，符合分层）；架构测试 37 过；`yate/cli.py` 零改动；上游重命名跟随见 §四 |
| 依赖变更 | 通过 | `pyproject.toml` dev extra 仅 += `fonttools>=4.53` / `brotli>=1.0`（带注释：fontTools CLI 子进程 + woff2 编解码）；CI 三条腿（pytest / smoke / pyright）均 `pip install -e ".[dev]"`，dev 依赖流程闭环实测成立 |
| 双语合规 | 通过 | `README.md` / `README.zh.md` 截图段逐句对齐（画廊链接、`python -m tools.screenshots` 再生说明、样图 `layout-explorer.svg`、项目布局 `tools/`+`screenshots/` 两行）；画廊中英说明成对 |
| 仓库卫生 | 通过 | 41 文件清单无探针 / 杂散文件；`pytest-pyright.svg` 已删；字体目录污染文件已清；工作树 clean |

## 四、合并正确性（两次 master 合并查证）

1. `0283398`：首次合并 master；随后 IDE 后台自动 fetch 使 `origin/master` 中途前移
   （`c5b09a5` → … → `aea1da4`）。
2. 合并后 diff 出现"反向 hunk"（`test_file_manager.py` / `test_gate_config.py`
   呈删除上游修复之假象）——查证为基线前移的 diff 现象，**非 evil merge**；
   以二次合并 `fad775d` 消除。
3. 上游重命名 `yate.editor_view`→`yate.editor_components`、`filemanager_dir`→
   `file_manager_dir` 由 `ddf36f5` 跟随，`8768fde` 全量刷新受影响 6 帧
   （diag-report / file-manager / layout-explorer / manual / screensaver / smoke-report）。

## 五、发现清单（0 BLOCKER / 0 MAJOR / 3 MINOR）

- **[MINOR] `tests/test_app_panes.py` 在 `-n auto` 高负载下偶发失败**
  （`test_vsplit_with_file_and_only` asyncio 异常 / `test_split_independent_cursors_and_navigation`）。
  按 §二.7 不记"偶发、重跑即过"，已双证：`pytest tests/test_app_panes.py -q -n 1` →
  26/26 通过（exit 0）；全量 `pytest tests/ -q -n auto` 复跑 exit 0。本 PR diff 不含
  panes 相关文件；负载裕度收窄源自上游 `dbe28c7`（perf(test): cut suite wall time with
  tighter poll step and worksteal）后的存量。**登记为上游跟进项，不阻断本 PR**。
- **[MINOR] `screenshots/which-key.svg` 中 ctrl-chord 控制字符以 caret 记号呈现**
  （如 `^]`）。产品侧 which-key sheet 渲染原始控制字符的问题已在
  [2026-11-02-readme-screenshots.md](2026-11-02-readme-screenshots.md) §八登记另案；
  本 PR 截图如实呈现且脱敏后 XML 安全，不再另开条目。
- **[MINOR] `screenshots/` 24 帧 SVG 共 2037 KB 随库入库**——README 画廊刚需的
  有意产物，单帧 ≤216 KB、总量可控；记录体量基线供后续帧数增长时复核。

## 六、门禁实测（主代理亲跑，2026-11-03，HEAD = `fad775d`）

| 门禁 | 命令（统一并行口径） | 结果 | exit |
|---|---|---|---|
| pyright | `python -m pyright yate/ tests/ tools/ pack/` | 0 errors / 0 warnings / 0 informations | 0 |
| 全量 pytest | `python -m pytest tests/ -q -n auto` | 通过（合并后稳定性复跑） | 0 |
| 架构 | `python -m pytest tests/test_architecture.py -q` | 37 passed | 0 |
| 覆盖率 | `python -m pytest tests/ --cov=yate --cov-branch -n auto -q` | 92.83%（fail_under 75 达标） | 0 |
| 冒烟 | `python -m tools.smoke_test run --jobs 4` | 121/121 场景 · 1463/1463 checks | 0 |

## 七、结论

**Overall: APPROVE**（0 BLOCKER / 0 MAJOR / 3 MINOR；3 MINOR 均为登记性质，
其中 panes 负载 flake 属上游存量跟进项）。

Strengths：

- 三项用户反馈缺陷以"根因修复 + 守护用例"闭环（XML 安全、字体嵌入均有回归用例钉住）；
- 依赖变更闭环完整（dev extra + 注释 + CI 三腿安装实测）；
- 合并正确性核查扎实：基线前移假象排查、上游重命名跟随、帧全量刷新各自成笔可追溯；
- 画廊由全量注册表驱动（前轮 major `afcaf5f` 修复语义保持）。

执行注记：本记录由主代理撰写——`pr-reviewer` 子代理 Phase-1 后判死（§一），
主代理按剧本接管并如实标注；评审期间基线两次前移均以再合并处置（§四）。

## 八、MINOR 修复轮（同日，2026-11-03）

三项 MINOR 当轮处置（方案见
[pr-review-minor-fixes-plan.md](../documents/pr-review-minor-fixes-plan.md) §七）：

| # | 处置 | 证据 |
|---|---|---|
| M1 panes flake | ✅ 修复（等待语义加固）：`test_app_panes.py` 三处弦驱动断言（游标 ×2、焦点 ×2 合并谓词）wait_until 化；`-n 1` 与全量均绿。三次满载复现尝试（全量 ×2 + 三文件加压子集 ×1）未再现早期 "asyncio exception"——残留 👀 观察：复现即按 traceback 精修 | 提交 `test(panes)` |
| M2 which-key 控制字符 | ✅ 修复（根因）：`key_name` 缺 C0 0x1c–0x1e 逆向（0x1d 掉穿 `return key`），补 `<ctrl-\>` / `<ctrl-]>` / `<ctrl-^>` 分支；可打印性守护首轮即红，另暴露 `<alt-backspace>` 经 ESC 两字节分支漏裸 DEL——alt 后缀改走单字符命名路径（`<alt-backspace>` / `<alt-ctrl-d>`）。固定表与帮助层同源受益；`which-key.svg` 重生成（XML 有效、无原始 C0、`ctrl-]` 标签在位，画廊其余帧字节不变） | 提交 `fix(keymaps)` + `chore(screenshots)`；变异演练 3 处全红 → 还原全绿 |
| M3 SVG 体量基线 | 📌 维持登记（非缺陷）：24 帧 2037 KB（最大 216 KB）为画廊刚需，留作帧数增长时的体量基线 | 无代码动作 |

修复后门禁五项全绿：pyright 0 / 全量 pytest `-n auto` exit 0 / 架构 37 /
覆盖率 92.82% / 冒烟 121/121·1463 checks（全 exit 0）。
