# Release 自动化工具实施计划

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> `tools/release/`（`__init__.py` / `__main__.py` / `cli.py`）已落地，
> 含 `release(version, *, dry_run=False, no_push=False)`、各 helper、
> `_VERSION_FILES` 两处 bump（`yate/__init__.py` 与
> `tests/test_theme_palettes.py`）与"先 bump 再 generate"的两阶段提交顺序；
> `tools/release/__init__.py` 原为空文件，现已填入 docstring。
>
> 注意：`tests/test_theme_palettes.py` 中的 `assertEqual(yate.__version__, ...)`
> 必须与当前 `yate/__init__.py::__version__`（**0.2.4**）保持一致——
> 这正是本工具 `_VERSION_FILES` 同时 bump 两处的原因。
>
> **后续增强（2026-09-26）**：v0.2.5 发布实操暴露了本方案"不自动回滚"
> 决策与缺分支/远端守卫的风险，加固计划见
> [release_tool_hardening_plan.md](release_tool_hardening_plan.md)
> （前置守卫 + 自动回滚，实施中）。

## Context（为什么做这个）

手动发布流程（版本号 bump → changelog 生成 → 提交 → 打 tag → 推送）步骤多、易出错。
上一轮 0.2.1 发布时因为 changelog 文件未提交，CI 报 "stale changelog files" 失败。
用户希望只输入一个版本号就能完成全部发布操作，规避人为遗漏。

本工具复用 `tools.changelog` 已有的 git 网关（`gitdata.run_git`）和 changelog 生成/检查逻辑（`generate`/`check`），不重新实现任何 git 或 changelog 逻辑。

## 要创建的文件

| 文件 | 状态 | 说明 |
|------|------|------|
| [tools/release/\_\_init\_\_.py](tools/release/__init__.py) | 已存在但为空，填入 docstring | 包说明 |
| [tools/release/\_\_main\_\_.py](tools/release/__main__.py) | 新建 | `python -m tools.release` 入口 |
| [tools/release/cli.py](tools/release/cli.py) | 新建 | 核心逻辑 |

复用（不修改）：
- [tools/changelog/gitdata.py](tools/changelog/gitdata.py) — `run_git()`、`GitError`
- [tools/changelog/cli.py](tools/changelog/cli.py) — `generate()`、`check()`

## CLI 接口

```
python -m tools.release <version>           # 完整发布
python -m tools.release <version> --dry-run # 只打印计划，不改文件/git
python -m tools.release <version> --no-push # 全部做完但不推送
```
- argparse（与 `tools.changelog` 一致，不用 click/typer）
- `main(argv=None)` 可测试，返回 int 退出码
- `release(version, *, dry_run=False, no_push=False) -> int` — 核心函数，`no_push=True` 对应 `--no-push`

## 版本文件（bump 两处）

1. [yate/\_\_init\_\_.py:11](yate/__init__.py#L11) — `__version__ = "X.Y.Z"`
2. [tests/test_theme_palettes.py:249](tests/test_theme_palettes.py#L249) — `self.assertEqual(yate.__version__, "X.Y.Z")`

**不碰 pyproject.toml**——hatchling 用 `dynamic = ["version"]` 从 `yate/__init__.py` 读取版本。

## 模块常量

```python
_VERSION_FILES = ("yate/__init__.py", "tests/test_theme_palettes.py")
_CHANGELOG_FILES = (
    "CHANGELOG.md",
    "CHANGELOG.zh.md",
    "yate/resources/changelog.en.md",
    "yate/resources/changelog.zh.md",
)
```

## helper 函数（每个都接受 dry_run 参数）

| 函数 | 签名 | 说明 |
|------|------|------|
| `discover_repo_root()` | `-> Path` | `Path(__file__).resolve().parents[2]`（同 changelog 的实现） |
| `read_current_version(repo)` | `-> str` | 复用 `gitdata.read_current_version(repo)` 读 `yate/__init__.py` |
| `validate_version(version, current)` | `-> None` | semver `X.Y.Z` 格式 + 严格大于 current，失败抛 `RuntimeError` |
| `files_dirty(repo, files)` | `-> list[str]` | `git status --porcelain -- <files>`，返回有改动的文件名列表 |
| `bump_init_py(repo, version, *, dry_run)` | `-> None` | 正则替换 `__version__ = "..."`，dry_run 时只打印 |
| `bump_test_assertion(repo, version, *, dry_run)` | `-> None` | 正则替换 `assertEqual(yate.__version__, "...")`，dry_run 时只打印 |
| `git_add(repo, files, *, dry_run)` | `-> None` | `git add <files>`，dry_run 时只打印 |
| `git_commit(repo, message, *, dry_run)` | `-> None` | `git commit -m <message>`，dry_run 时只打印 |
| `generate_changelog(repo, *, dry_run)` | `-> None` | 调用 `tools.changelog.cli.generate(repo)`，dry_run 时只打印 |
| `gate_check(repo)` | `-> int` | 调用 `tools.changelog.cli.check(repo)`，返回退出码 |
| `run_version_tests(repo)` | `-> int` | `python -m pytest tests/test_theme_palettes.py -v`，返回退出码 |
| `git_tag(repo, version, *, dry_run)` | `-> None` | `git tag -a v{version} -m "Release v{version}"`，dry_run 时只打印 |
| `git_push(repo, refspec, *, dry_run)` | `-> None` | `git push origin <refspec>`，dry_run 时只打印 |

所有 git 操作通过 `gitdata.run_git(args, repo=repo)` 执行（唯一 git 网关）。

## release 函数主流程

```python
def release(version: str, *, dry_run: bool = False, no_push: bool = False) -> int:
    repo = discover_repo_root()
    current = read_current_version(repo)
    validate_version(version, current)

    # Step 0: 检查版本文件是否有未提交改动
    dirty = files_dirty(repo, _VERSION_FILES)
    if dirty and not dry_run:
        raise RuntimeError(f"refusing to release: uncommitted changes in {dirty}")

    # Step 1-2: bump 版本
    bump_init_py(repo, version, dry_run=dry_run)
    bump_test_assertion(repo, version, dry_run=dry_run)

    # Step 3: 提交版本 bump
    git_add(repo, _VERSION_FILES, dry_run=dry_run)
    git_commit(repo, f"chore(release): v{version}", dry_run=dry_run)

    # Step 4: 生成 changelog
    generate_changelog(repo, dry_run=dry_run)

    # Step 5: 提交 changelog
    git_add(repo, _CHANGELOG_FILES, dry_run=dry_run)
    git_commit(repo, f"docs(changelog): release v{version} bilingual changelog", dry_run=dry_run)

    # Step 6: changelog 门禁
    if gate_check(repo) != 0:
        raise RuntimeError("changelog gate failed")

    # Step 7: 版本测试
    if run_version_tests(repo) != 0:
        raise RuntimeError("version tests failed")

    # Step 8: 打 tag + 推送
    git_tag(repo, version, dry_run=dry_run)
    if not no_push and not dry_run:
        git_push(repo, "master", dry_run=dry_run)
        git_push(repo, f"v{version}", dry_run=dry_run)
    return 0
```

## main 函数

```python
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.release",
        description="One-command release: bump version, changelog, commit, tag, push.",
    )
    parser.add_argument("version", help="target version X.Y.Z, must be greater than current")
    parser.add_argument("--dry-run", action="store_true", help="print planned steps, no mutation")
    parser.add_argument("--no-push", action="store_true", help="do everything except push")
    args = parser.parse_args(argv)
    try:
        return release(args.version, dry_run=args.dry_run, no_push=args.no_push)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
```

## 关键设计决策

**两阶段提交顺序**：先提交版本 bump，再生成 changelog。因为 `generate()` 会读 `gitdata.read_current_version(repo)`（刚改的新值）和 `read_version_bumps(repo)`（刚提交的 bump commit），从而正确生成新版本的 changelog 段。

**tag 在测试通过后才创建**——测试失败则 tag 不存在，操作者可修正后重跑，无需先删 tag。

**不自动回滚**——中途失败抛 `RuntimeError`，`main()` 捕获后打印并返回 1。操作者自行检查 `git log` / `git status`，跨两个 commit + tag 的自动回滚太脆弱。

**用 pytest**——CI 用 `python -m pytest tests`，与项目测试框架一致。

**dry_run 各 helper 自处理**——每个 helper 接受 `dry_run` 参数，为 True 时只打印将执行的操作，不实际执行。`gate_check` 和 `run_version_tests` 不接受 `dry_run`（它们是只读的，正常执行）。

## 实现步骤

1. 填写 `tools/release/__init__.py`（仅 docstring）
2. 创建 `tools/release/__main__.py`（入口，4 行，同 changelog 的 `__main__.py`）
3. 创建 `tools/release/cli.py`：
   - 导入：`argparse`、`re`、`subprocess`、`sys`、`Path`、`Sequence`，以及 `from ..changelog import gitdata` 和 `from ..changelog.cli import check, generate`
   - 模块常量 `_VERSION_FILES`、`_CHANGELOG_FILES`
   - 上表 13 个 helper 函数
   - 公开函数 `release(version, *, dry_run=False, no_push=False) -> int`
   - CLI 入口 `main(argv=None) -> int`

## 验证

实现后从仓库根目录测试：

1. `python -m tools.release 0.2.0 --dry-run` — 应报错 "version 0.2.0 is not greater than current 0.2.1"
2. `python -m tools.release 0.3.0 --dry-run` — 应打印各步骤的 dry-run 信息并退出 0
3. `python -m tools.release 0.3.0` — 完整发布，结束后 `git log --oneline -3` 看到两个新 commit，`git tag --list v0.3.0` 有 tag
4. `python -m tools.release 0.3.1 --no-push` — 全部做完但跳过推送
