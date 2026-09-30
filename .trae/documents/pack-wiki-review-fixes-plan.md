# pack-wiki 评审修复计划（PR #39 AI 队友审查项）

> 任务来源：Gitee PR #39 评论 `note_51410631`（2026-09-30，2 阻断 + 5 改进）。
> 改动范围：`tools/pack/wiki.py` 单文件（评审指令明确，按 plan-before-execute §一直接执行），
> 配套测试 `tests/test_pack_wiki.py`。

## 一、目标与非目标

**目标**：修复 2 个阻断项与 5 个改进项，行为以评审建议为准；每项配测试。
**非目标**：不改 CLI 规格、不改页面收集/导航逻辑的既有行为、不动 wiki 仓库。

## 二、修复清单（评审项 → 处置）

| # | 级别 | 问题 | 处置 |
|---|---|---|---|
| 1 | 阻断 | `--force` 且无 `--translate-cmd` 时 stale 页被静默丢弃，`--check` 误报 0 | `translate_cmd is None` 分支补 `else: stale.append(...)` |
| 2 | 阻断 | `translate_via_cmd` 未捕获 `subprocess.TimeoutExpired`，超时致全流程崩溃、仓库状态不一致 | try/except 捕获，stderr 报告并返回 `None` |
| 3 | 改进 | `load_manifest` 对损坏 JSON / 非 dict 零容错 | try/except + `isinstance` 校验，损坏时告警并重置为空 |
| 4 | 改进 | `run()` 内 `zh_bytes.decode("utf-8")` 严格解码与读取侧不一致 | 改为 `errors="replace"` |
| 5 | 改进 | `_page_title` 全量读入内存 | `itertools.islice` 逐行迭代，读满 30 行短路 |
| 6 | 改进 | `_nav_documents` 的 `groups` 取自全量 pages 而非 sets bucket | 改为从 `by_section[SECTION_SETS]` 提取 |
| 7 | 改进 | `push_wiki` 忽略 `git add -A` 返回值 | 检查返回码，失败时 stderr 报告并返回 1 |

被放弃的路线：为 #1 让 `--force` 无钩子时静默保持现状（否决：违背 `--check` 门禁契约）；为 #3 直接删除损坏 manifest 文件（否决：超出必要副作用，重置为空即可恢复）。

## 三、实施与验收

改动文件：`tools/pack/wiki.py`、`tests/test_pack_wiki.py`（新增 4 个用例：
force-无钩子报 stale、translate 超时返回 None、manifest 损坏容错、git add 失败中止 push）。

验收命令（全绿为通过）：

```
.venv\Scripts\python -m pytest tests/test_pack_wiki.py -q
.venv\Scripts\python -m pyright yate/ tests/ tools/
.venv\Scripts\python -m pytest tests -q
```

## 四、执行记录（收尾回填，2026-09-30 实测）

- 提交：`f7e0a1e` `fix(tools): harden wiki generator per review`（代码 + 测试，2 文件 +111/-20）。
- 门禁实测：`pytest tests/test_pack_wiki.py -q` 18 用例全绿（原 14 + 新增 4）；
  `pyright yate/ tests/ tools/` 0 errors / 0 warnings；全量 `pytest tests -q` 退出码 0。
- 偏离记录：无选型偏离。测试 `test_force_without_translator_reports_stale`
  首版直接在无译本基线上跑 `--force`，因无 stale 可报而失败——修正为
  先经翻译器产出 v1 译本再变异源文档（测试自身缺陷，非实现问题）。

## 五、第二轮评审修复（Gitee PR #39 note_51410673，2026-09-30）

评审针对第一轮修复后的代码，给出 2 阻断 + 2 改进：

| # | 级别 | 问题 | 处置 |
|---|---|---|---|
| 1 | 阻断 | `push_wiki` 无差别容忍 commit 失败，可能推送非预期状态 | 区分 "nothing to commit" 与真实错误；真实错误 stderr 报告并返回 1、不再 push |
| 2 | 阻断 | `load_manifest` 捕获 `OSError` 后重置为空，`store_manifest` 随后覆盖文件，静默丢失全部 sha256 记录 | 仅容错 `JSONDecodeError`；`OSError` stderr 报告后 `sys.exit(1)` 中止 |
| 3 | 改进 | `translate_via_cmd` `shell=True` 的命令注入面 | **偏离评审建议**：保留 `shell=True`（Windows 下 `shlex.split` 会破坏反斜杠路径，且用户可能依赖管道/重定向），改为在模块 docstring 与 `--translate-cmd` help 中显式声明"必须来自可信来源" |
| 4 | 改进 | `--force` 重译失败且页面已存在时误报为 missing | `has_en` 时归入 `stale`，否则 `missing` |

新增回归测试 4 个：commit 真实失败中止 push、空提交继续 push、manifest 读取错误
`SystemExit`、force 重译失败报 stale（capsys 断言）。

### 第二轮实测

- 提交：`92c2e49` `fix(tools): address second-round wiki review findings`（3 文件 +88/-5）；
  回填笔 `88f452b` `docs(plans): backfill round-2 review fixes record`。
- 门禁实测：`pytest tests/test_pack_wiki.py -q` **22 用例全绿**（18 + 4）；
  `pyright yate/ tests/ tools/` 0 errors / 0 warnings；全量 `pytest tests -q` 退出码 0。
- 偏离记录：仅上表 #3（文档化替代 shlex），理由如上，实测依据为
  `shlex.split(r"C:\tools\trans.py")` 在 Windows 会把 `\t` 当转义序列拆坏路径。
