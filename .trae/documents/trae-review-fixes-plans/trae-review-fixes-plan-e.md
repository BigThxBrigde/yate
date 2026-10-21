# plan-e（W-E）：`tools/` 支撑面 — 8 条（含执行期登记 m-28）

- 波次：W-E（排在 W-B/C/D 之后统一收尾；`tools/` 与 `yate/` 文件不重叠）
- 独占文件（**只改这些**）：`tools/pack/wiki.py`、`tools/pack/cli.py`、`tools/pack/rosters.py`、
  `tools/changelog/cli.py`、`tools/changelog/gitdata.py`；
  测试：`tests/test_pack_wiki.py`、`tests/test_pack_wiki_errors.py`、`tests/test_pack_wiki_parallel.py`、
  `tests/test_changelog_tool.py`、`tests/test_smoke_cli.py`
- 输入：评审记录 §四 B-3、§五 M-9、§六 m-23/m-24/m-25/m-26/m-27

## 1. B-3（BLOCKER）`tools/pack/wiki.py:458-481` prune 误删源文档

**修法**：新增前置护栏 `_assert_prune_safe(target: Path, root: Path) -> None`，在 `run()` 的
`prune_orphan_pages(...)`（:1467）之前调用：

```python
def _assert_prune_safe(target: Path, root: Path) -> None:
    """Refuse to prune anything that is not a disposable wiki checkout."""
    resolved = target.resolve()
    if resolved.is_relative_to(root.resolve()):
        raise WikiError(
            f"refusing to prune {target}: target is inside the source repository",
            code=Code.WIKI_PRUNE_FAILED,
            hint="pass --target pointing at the <repo>.wiki checkout",
        )
    if any(target.iterdir()) and not (target / ".git").exists():
        raise WikiError(
            f"refusing to prune {target}: not a wiki repository (no .git)",
            code=Code.WIKI_PRUNE_FAILED,
        )
```

- 空目录（含 `.translation-manifest.json` 但无 `.git` 的首次生成目录）不拦——只拦"非空且无 `.git`"；
- `prune_orphan_pages` 本身再收窄一层：只删 `keep` 的**补集里由 manifest 记录过的页面**
  （`manifest` 已在 `run()` 中加载，把旧 manifest 的键集传给 prune），未知文件一律保留。

**回归测试**（`tests/test_pack_wiki.py`，修复前必须红）：
- `test_prune_refuses_a_target_inside_the_source_repository`（`--target repo_root` → `WikiError`，源 `*.md` 仍在）
- `test_prune_refuses_a_non_empty_target_without_git`（临时目录放一个 `foo.md` → `WikiError`，文件仍在）
- `test_prune_removes_only_pages_recorded_in_the_manifest`（manifest 记过的孤儿页被删，未记过的用户文件保留）

## 2. M-9（MAJOR）`tools/changelog/cli.py:133-142` `--check` 静默放行

**修法**：
1. `gitdata.py` 新增 `is_git_repo(repo: Path) -> bool`（`run_git(["rev-parse", "--git-dir"])`，
   `GitError` → `False`；返回码非 0 也 `False`）；
2. `generate()` 的 `except gitdata.GitError` 分支改为：

```python
    except gitdata.GitError as exc:
        if check and not gitdata.is_git_repo(repo):
            # sdist unpack / source archive: nothing to gate against
            print(f"SKIP: no git history ({exc})")
            return 0
        print(f"error: {exc}")
        return 1
```

**回归测试**（`tests/test_changelog_tool.py`）：
- `test_check_skips_when_the_directory_is_not_a_git_repository`（临时目录 → 0 + SKIP 输出）
- `test_check_fails_when_git_history_is_unreadable`（`monkeypatch` 让 `run_git(["log", ...])` 抛
  `GitError("git timed out")`，且 `is_git_repo` 为真 → 返回 1）

## 3. m-23（MINOR）`tools/pack/wiki.py:571-577`（及 :599-600）静默 `except OSError: pass`

**修法**：改为 `print(f"wiki: cannot feed the translator: {exc}", file=sys.stderr)` 后 `return`。
**回归测试**：`tests/test_pack_wiki_errors.py` 既有用例全绿（stderr 内容变更不参与断言时无需改）。

## 4. m-24（MINOR）`tools/pack/wiki.py:78,844-847` 写死上游 GitHub wiki

**修法**：新增 `_github_wiki_url(repo_root: Path) -> str`：
- 环境变量 `YATE_WIKI_GITHUB_URL` 非空 → 用它；
- 否则读 `origin`（`run_git(repo_root, "remote", "get-url", "origin")`），若 URL 主机是 `github.com`
  → 同 owner 的 `<repo>.wiki.git`（fork 场景推自己的 wiki）；
- 否则回落现有常量 `GITHUB_WIKI_URL`（Gitee 主仓 + GitHub 镜像的既有行为不变）。
`push_wiki(target: Path, *, github_url: str)` 接收解析结果，不再读模块常量。

**回归测试**（`tests/test_pack_wiki.py`）：
- `test_github_wiki_url_follows_a_github_origin`（`github.com/me/yate.git` → `.../me/yate.wiki.git`）
- `test_github_wiki_url_honours_the_environment_override`
- `test_github_wiki_url_falls_back_to_the_published_mirror`（Gitee origin → 既有常量）

## 5. m-25（MINOR）`tools/changelog/cli.py:299` `--limit` 无校验

**修法**：解析后 `if args.limit is not None and args.limit <= 0: parser.error("--limit must be a positive integer")`。
**回归测试**（`tests/test_changelog_tool.py`）：`test_cli_rejects_a_non_positive_limit`（`SystemExit` code 2）。

## 6. m-26（MINOR）`tools/pack/cli.py:246-250` 不可达兜底

**修法**：删除 `build_parser().error(f"unknown command ...")` 两行（`add_subparsers(required=True)`
已保证分支穷尽），保留三个分支的 `return`。
**回归测试**：`tests/test_smoke_cli.py` / `tests/test_pack_wiki.py` 既有 CLI 用例全绿。

## 7. m-27（MINOR）`tools/pack/rosters.py:21` 借道再导出

**修法**：`from tools.pack.icon import repo_root` → `from tools._util import repo_root`。
**回归测试**：`tests/test_pack_wiki.py` 既有用例全绿。

## 8. m-28（MINOR，执行期登记）`yate/logs.py:587` tracing 复位缺失

**背景**：W-D 执行期发现 `tracing.install()` 把 `yate` 根 logger 进程级置 `DEBUG`，
`uninstall()`（:605-609）只摘 handler、**不复位级别**；`tests/test_tracing.py` 与
`tests/test_syntax_engine.py` 同跑时后者断言被污染（W-D 只在测试侧就地加固，根因未修）。

**修法**（`yate/logs.py`，只动 `TracingService`）：
1. `__init__`（:515-521）增 `self._previous_level: int | None = None`；
2. `install()` 在 :587 `setLevel(logging.DEBUG)` **之前**记录首次进入时的级别：
   `if self._previous_level is None: self._previous_level = self._logger.level`；
3. `uninstall()` 末尾恢复并清空：`if self._previous_level is not None:
   self._logger.setLevel(self._previous_level); self._previous_level = None`。

**回归测试**（`tests/test_tracing.py`）：
- `test_uninstall_restores_the_previous_logger_level`（先把 `logging.getLogger("yate")`
  置 `WARNING`，`install()` → `DEBUG`，`uninstall()` → 回到 `WARNING`）
- `test_install_twice_then_uninstall_restores_once`（两次 `install()` 后 `uninstall()`，
  级别只复位到安装前值，不残留 `NOTSET`）
- `test_tracing_install_does_not_leak_debug_to_the_next_test`
  （`install()` + `uninstall()` 后向 `yate.x` 发一条 `debug`，断言 caplog 在 `WARNING` 级别下收不到）

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py tests/test_pack_wiki_errors.py tests/test_pack_wiki_parallel.py tests/test_changelog_tool.py tests/test_smoke_cli.py tests/test_tracing.py tests/test_syntax_engine.py -q --cov-fail-under=0
.\.venv\Scripts\python.exe -m tools.changelog check
```

## 风险与回滚

- B-3 的"只删 manifest 记录过的孤儿页"会让历史遗留孤儿页保留下来：首次在新护栏下运行时
  可能残留旧页（比误删源文档安全），在帮助文本里说明"如需清理请手工删除或先跑一次带
  `--translate-cmd` 的完整生成"。
- M-9 语义由"失败也放行"变"失败即红"：CI 环境必须能跑 git（现状 CI 就是 git 检出），
  本地 sdist 场景仍走 SKIP 分支。
- 回滚：按条 `git revert`。
