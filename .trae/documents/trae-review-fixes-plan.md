# trae-review-fixes 主计划（2026-10-20 全仓审核 39 条修复）

- 任务来源：[`../reviews/2026-10-20-full-repo-trae-code-review.md`](../reviews/2026-10-20-full-repo-trae-code-review.md)
  （`TRAE-code-review` 技能全仓审核：3 BLOCKER / 9 MAJOR / 27 MINOR，20 条经 2 个验证子代理 2/2 确认）
- 分支 / worktree：`enh/full-repo-trae-review` @ `../yate-full-repo-trae-review`（基线 `d8c1dee`）
- 用户决策：**全修 39 条**（2026-10-20 会话内批准范围；本方案为实施前的细化计划）
- 子计划目录：[`trae-review-fixes-plans/overview.md`](trae-review-fixes-plans/overview.md)
  （总纲 + `trae-review-fixes-plan-a…e.md` 五个波次子计划，**实施细节以子计划为准**）

## 一、目标与非目标

**目标**：消除 39 条已确认缺陷，使下列门禁全部 exit 0 且无行为回归：

- `pyright yate/ tests/ tools/` 零诊断；
- `pytest tests/ -q --cov=yate --cov-branch` 全绿、覆盖率 ≥ 75（当前 92.06%）；
- `pytest tests/test_architecture.py -q` 36 passed。

**非目标**（明确排除，避免顺手重构）：

- 不重排模块 / 不拆 `editor.py` / 不改分层边界（R1–R14 与 `_LAYER_RANKS` 不动）；
- 不为"更优雅"改写工作正常的逻辑；性能条目必须先测后改（见 overview §四）；
- 不新增 `Protocol` / `TYPE_CHECKING` / `Any` / `# type: ignore`（现有 10 处带码 ignore 不在本轮清理范围，
  仅 m-4 的 `engine.py:83` 因规则冲突改 `cast`）；
- 不触碰 `tests/` 之外的文档改写（除本节计划文档与本轮评审记录的状态回填）。

## 二、波次与验收

| 波次 | 子计划 | 独占文件面 | 条目 |
|---|---|---|---|
| W-A | [plan-a](trae-review-fixes-plans/trae-review-fixes-plan-a.md) | `yate/editor_core/*`、`yate/editor_lsp/*` | B-1、M-1、M-2、M-3、m-9、m-10、m-11、m-19（8） |
| W-B | [plan-b](trae-review-fixes-plans/trae-review-fixes-plan-b.md) | `yate/editor_view/*`、`yate/editor_term/*` | M-4、m-1、m-2、m-5、m-12、m-13、m-20（7） |
| W-C | [plan-c](trae-review-fixes-plans/trae-review-fixes-plan-c.md) | `yate/*.py` 顶层、`yate/flows/*`、`yate/keymaps/*` | B-2、M-5、M-6、m-7、m-16、m-21、m-22（7） |
| W-D | [plan-d](trae-review-fixes-plans/trae-review-fixes-plan-d.md) | `yate/services/*`、`yate/editor_syntax/*`、`yate/extensions/*` | M-7、M-8、m-3、m-4、m-6、m-8、m-14、m-15、m-17、m-18（10） |
| W-E | [plan-e](trae-review-fixes-plans/trae-review-fixes-plan-e.md) | `tools/*`、`yate/logs.py` | B-3、M-9、m-23、m-24、m-25、m-26、m-27、m-28（8） |

**波次纪律**：波内文件互不重叠 → 可并行（2~3 个一批）；波间串行，上一波验收命令全部 exit 0
才进入下一波。测试文件按波次归属独占：`tests/test_editor_core_diff.py` / `test_editor_core.py`
/ `test_lsp_parsing.py` / `test_lsp.py`（W-A）、`tests/test_terminal*.py` / `test_diffview.py` /
`test_app_find_replace.py` / `test_chrome.py` / `test_theme_files.py` / `test_panes.py`（W-B）、
`tests/test_vim_keymap.py` / `test_session.py` / `test_yaterc_options.py` / `test_app_textual.py` /
`test_keymap_set.py` / `tests/test_architecture.py`（W-C）、`tests/test_fonts.py` / `test_yxp.py` /
`test_tools_yxp.py` / `test_extension_api.py` / `test_extension_bridges.py` /
`test_extension_examples.py` / `test_syntax_engine.py` / `test_tracing.py` / `test_shell.py` /
`test_extensions.py`（W-D）、`tests/test_pack_wiki*.py` / `test_changelog_tool.py` /
`test_smoke_cli.py`（W-E）。

## 三、收尾门禁（主代理亲跑）

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.\.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-branch
```

判定：三条命令 exit 0；覆盖率 ≥ 75%；架构守卫 36 passed（若新增守卫则 ≥ 36）。

## 四、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| M-1 光标重算改变 `3p` 块序，可能撞既有 pin 用例 | 先读 `tests/test_editor_core.py` 相关用例，行为变化写入偏离记录 | 单条 `git revert` |
| B-1 零长区间映射选错侧，导致合并区域标错 | 只补 `start == end` 早退分支，不动既有 equal/replace 路径；新增首/中/尾三组用例 | 同上 |
| M-5 `:saveas` 改走 `resolve_input_path` 改变相对路径基准 | 用例覆盖 `~`、相对路径、绝对路径三态 | 同上 |
| M-6 yaterc 兜底过宽吞掉真 bug | 只包 `_extract_*` 调用点，`except Exception` 必须 `log.debug` + 写 `config.errors` | 同上 |
| m-8 扩展注册 undo 需要新增 `_record_undo` 注入口 | 只改 `services/extensions/` 内部（R14 门面 14 名不变） | 同上 |
| M-9 `--check` 由 0 变 1，可能让本地历史缺数据时 CI 变红 | 区分"非 git 仓库"（SKIP,0）与"git 调用失败"（1）；CI 环境本身有 git | 同上 |

## 五、批准与执行记录

- 2026-10-20：用户在会话内选择"全修（39 条）"；方案批准后按 W-A → W-B/C/D → W-E 串行执行。
- W-A `148fa4a`（8 条）、W-B `29a79d2`（7 条）、W-C `b32bd5d`（6 条 + m-21 登记不修）、
  W-D `41ae9fc`（10 条，含跨波补齐的 LSP / tree-sitter 回滚）、W-E（8 条，含执行期登记的 m-28）。
- W-E 经 `code-review-expert` 两轮复核：首轮 2 BLOCKER（B-3 护栏可被 manifest 绕过、`<root>/.wiki`
  被误拒）+ 6 MAJOR（`is_git_repo` 判据、用例打桩、worker 写终端、URL 裸子串、env 空串语义、
  `is_git_repo` 被测对象被 mock）→ 全部修复后第二轮 **APPROVE**，无新增 BLOCKER/MAJOR。
- 收尾门禁（主代理亲跑，2026-10-20）：

  | 门禁 | 命令 | 结果 |
  |---|---|---|
  | pyright strict | `python -m pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations |
  | 架构守卫 | `python -m pytest tests/test_architecture.py -q` | 36 passed |
  | 全量回归 + 覆盖率 | `python -m pytest tests/ -q --cov=yate --cov-branch` | **exit 0**，覆盖率 **91.99% ≥ 75** |

- 偏离与实测依据（逐条）见 [`trae-review-fixes-plans/overview.md`](trae-review-fixes-plans/overview.md) §5.2；
  处置状态汇总见评审记录 §十。
