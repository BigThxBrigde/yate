# 测试迁移 pytest 与 ~/.yate 隔离实施计划

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> - `tests/conftest.py` 提供 autouse `isolated_home` 夹具（`Path.home` +
>   `USERPROFILE` / `HOME` → 每用例临时目录）；哨兵 `tests/test_isolation.py`
>   已加入。
> - `pyproject.toml`：`dev` 含 `pytest>=8.0`，并已配置
>   `[tool.pytest.ini_options]`（`testpaths = ["tests"]`、`addopts = "-q"`）。
> - 测试文件已全部为 pytest 函数风格（23 个 `tests/test_*.py` 加
>   `conftest.py`），不再依赖逐用例手动 patch HOME。
> - CI 双流水线均运行 `python -m pytest tests`；`.github/workflows/test.yml`
>   另有 `fetch-depth: 0` 与 `python -m tools.changelog check`。

> 目标：**pytest 成为唯一测试运行器与断言风格**（现有约 20 个测试文件全量
> 重写），并通过全局 conftest 夹具实现**机制性隔离**——任何测试都读写不到
> 用户真实的 `~/.yate`（yaterc、extensions、themes、crash data）。
>
> 核心原则：隔离靠机制（autouse fixture），不靠逐用例自觉 patch。

---

## 1. 现状事实（基于代码证据）

| 事实 | 证据 |
|------|------|
| 20 个测试文件全部 unittest.TestCase 风格，共约 8200 行 | `tests/` 目录；最大 [test_app_textual.py](tests/test_app_textual.py) 2887 行 |
| 无 conftest.py、无 pytest 配置、pytest 未装进 .venv | 仓库根 grep 无 conftest；[pyproject.toml:20](pyproject.toml#L20) `dev = ["pyright>=1.1.400"]` |
| CI 用 unittest 运行 | [.github/workflows/test.yml:67](.github/workflows/test.yml#L67)、[.workflow/test.yml:57](.workflow/test.yml#L57) `python -m unittest discover -s tests` |
| **真实隔离漏洞 ①**：每个 Textual pilot 测试都会**执行用户真实扩展** | [app.py:1714](yate/app.py#L1714) `on_mount → load_startup_services()`；[app.py:1808](yate/app.py#L1808) 扫描并加载 `Path.home()/.yate/extensions` → test_app_textual 的每次 `app.run_test()`、[test_diagnostics.py:34](tests/test_diagnostics.py#L34) 都触发 |
| **真实隔离漏洞 ②**：CLI 主题启动测试扫描真实主题目录 | [cli.py:235](yate/cli.py#L235) `Path.home()/.yate/themes`；test_cli 仅 tilde 用例设置了 HOME/USERPROFILE |
| 隔离依赖"每个用例记得 patch"：crash 目录、yaterc exec | [crash.py:54](yate/crash.py#L54) `~/.yate/data`（会建目录写文件）；[config.py:117](yate/config.py#L117) `~/.yate/yaterc`（**exec 用户 Python**）；test_cli 靠 `patch("yate.crash.install")` + `-u NONE` 自觉规避 |
| 现有隔离手段分散、不统一 | test_crash patch `Path.home`；test_cli 手动存/恢复 HOME/USERPROFILE（[test_cli.py:203-219](tests/test_cli.py#L203-L219)）；test_config patch `user_config_path`；test_user_setup 传显式 `base_dir` |
| 裸 `YateApp()` 不读 yaterc（config=None → 空默认） | [app.py:160](yate/app.py#L160) `self.config = config if config is not None else YateConfig()` |
| 仓库根无 `yaterc`/`themes/`/`extensions/`；.gitignore 已含 `.pytest_cache/` | 实测 `Test-Path` 均为 False |
| `.yate` 相关 touchpoint 全部经 `Path.home()` 或 `expanduser("~")` | config.py:117/220/295、crash.py:54、cli.py:235/243、app.py:767/1207/1808、user_setup.py:89、diagnostics.py:231/366、fonts.py:252（`~/.local/share/fonts`）、completion.py:291 |

## 2. 隔离设计（`tests/conftest.py`，本计划核心）

**一条 autouse fixture 覆盖所有测试（function 级）**，双通道堵死：

```python
# tests/conftest.py
"""Global test isolation: no test may touch the real user ~/.yate."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point home (Path.home + USERPROFILE/HOME) at a per-test temp dir."""
    home = tmp_path / "home"
    home.mkdir()

    def _fake_home(cls: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(_fake_home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home
```

设计要点：

1. **双通道原因**：
   - `Path.home()` 直接调用（config.py:117、crash.py:54、app.py:1808、
     cli.py:235、user_setup.py:89、diagnostics.py:231/366、fonts.py:252）
     → 被 `monkeypatch.setattr(Path, "home", ...)` 命中；
   - `expanduser("~")` 字符串路径（config.py:220/295、app.py:767/1207、
     cli.py:243、completion.py:291）→ 走环境变量：Windows `ntpath` 读
     `USERPROFILE`，POSIX `posixpath` 读 `HOME`，两个都设全平台覆盖；
   - 两条通道互为冗余，防 CPython 行为差异/未来变化。
2. **monkeypatch 自动恢复**：无需手写 try/finally（替代 test_cli 的
   手动存/恢复模式）。
3. **autouse 对纯函数测试与迁移中间态都生效**：conftest 落地当天起，
   即使 TestCase 文件尚未重写，pytest 运行时也已全局隔离。
4. **临时 home 为空目录**：`~/.yate/yaterc`、themes、extensions 天然
   不存在 → 用户扩展不再被执行、用户主题/yaterc 不再被读取。
5. **需要"用户配置存在"的用例**：自己在 `isolated_home` 返回的临时
   home 下写 `yaterc`/extensions/themes（显式造数，等价现有
   test_config / test_user_setup 模式）。
6. **不 chdir**：避免破坏大量相对路径断言；仓库根当前无
   `yaterc`/`themes/`/`extensions/`，`Path.cwd()/...` 扫描为空操作；
   CLI `main()` 测试继续显式 `-u NONE` 或显式 rc（重写时保留并注释
   原因——`find_project_config` 会从 cwd 向上找 rc，属 cwd 污染面）。
7. **哨兵测试** `tests/test_isolation.py`（新增，防夹具被误删/失效）：

   ```python
   def test_home_is_isolated(isolated_home: Path) -> None:
       assert Path.home() == isolated_home
       assert os.environ["USERPROFILE"] == str(isolated_home)
       assert not (isolated_home / ".yate" / "yaterc").exists()
   ```

## 3. 全量重写规范（unittest → pytest 对照）

新增依赖只有 pytest 本体；**不引 pytest-mock / pytest-asyncio**（保持
零第三方插件原则：Mock 断言保留标准库 `unittest.mock`，Textual pilot
保留 `asyncio.run(_scenario())` 模式）。

| unittest 现状 | pytest 目标 |
|---------------|-------------|
| `class XxxTests(unittest.TestCase)` | 模块级 `test_*` 函数 + 分组注释 |
| `setUp` / `addCleanup` | fixture（普通或 `yield` 式） |
| `self.assertEqual/True/False/In/IsNone/IsInstance` | 裸 `assert` |
| `self.assertRaises` | `with pytest.raises(...)` |
| `self.subTest(...)` | `@pytest.mark.parametrize`（含 `id=`） |
| `mock.patch.object(Path, "home", ...)` 等 | `monkeypatch.setattr`（重写时删除用例级 HOME 处理，直接用 `isolated_home` 返回值） |
| `mock.patch.dict(os.environ, ...)` | `monkeypatch.setenv / delenv` |
| 需要 `assert_called_once` 等 Mock 断言 | 保留 `unittest.mock.patch` 上下文管理器（仅此处允许） |
| `TemporaryDirectory()` 上下文 | `tmp_path` fixture |
| `redirect_stdout(io.StringIO())` | `capsys`（`capsys.readouterr().out`） |
| Textual `asyncio.run(...)` + `app.run_test()` | 模式保留，仅去掉 TestCase 壳 |
| `if __name__ == "__main__": unittest.main()` | 删除 |
| 1760 行附近的 overlay 参数化表 | `@pytest.mark.parametrize` 改写并追加行 |

pyright strict 约束（include 已含 tests）：pytest 函数统一 `-> None`；
fixture 签名用 `pytest.MonkeyPatch`、`Path` 等内置类型注解；目标零诊断
零豁免。

## 4. 工程配置与 CI

### 4.1 pyproject.toml

```toml
[project.optional-dependencies]
dev = ["pyright>=1.1.400", "pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

实施时在 .venv 执行 `pip install -e ".[dev]"`。

### 4.2 CI（两个 workflow 同步切）

| 位置 | 现状 | 改为 |
|------|------|------|
| [.github/workflows/test.yml:60-67](.github/workflows/test.yml#L60-L67) | `pip install -e .` + `python -m unittest discover -s tests` | `pip install -e ".[dev]"` + `python -m pytest tests`；步骤名 "Run pytest suite"；文件头注释同步 |
| [.workflow/test.yml:49-57](.workflow/test.yml#L49-L57) | 同上（Gitee Go） | 同步改；保留 `TERM=xterm-256color` 前缀 |

changelog 门禁（`python -m tools.changelog check`）、checkout
`fetch-depth: 0`、双平台 matrix 均不动。

## 5. 实施步骤（每批次结束跑 `python -m pytest tests -q` 保持绿）

0. **基建**：pyproject 配置 + 安装 pytest → 新增 `tests/conftest.py`
   （autouse `isolated_home`）+ `tests/test_isolation.py` 哨兵。
   *从此刻起全套测试已与真实 ~/.yate 隔离（含尚未重写的 TestCase）。*
1. **小文件立范式**（7 个，54–179 行）：
   test_paths → test_fonts → test_extensions → test_changelog_view →
   test_diagnostics → test_crash → test_workspace_filter
   （test_crash 删除其自带 HOME patch 改用 isolated_home；
   test_diagnostics `_build_app` 的扩展扫描自此天然指向临时 home）。
2. **中文件**（8 个）：
   test_syntax_engine → test_highlight → test_theme_palettes →
   test_user_setup → test_panes → test_editor_core → test_terminal →
   test_cli（保留 `-u NONE` 纪律并注释；删除 `_run_main` 的
   HOME/USERPROFILE 手动存/恢复）。
3. **大文件**（4 个）：test_ts_backend → test_config →
   test_changelog_tool（git e2e 用例保持 skip-if-no-git 逻辑）→
   test_lsp。
4. **收尾最大件**：test_app_textual（2887 行）按区间分段迁移——
   基础屏/主题 → 编辑器视图 → 文档屏（998–1246，参数化表 1760）→
   命令与快捷键；每段迁移后即跑该文件 `-q` 验证。
5. **CI 切换**：两个 workflow 改 pytest；推送观察双平台结果。
6. **文档刷新**：README/手册中"unittest"字样、CI 复现命令改为
   pytest（仅提及测试命令处，最小改动）。

## 6. 验证方案

```powershell
# 1) 全套件绿（本机 Windows）
python -m pytest tests -q

# 2) pyright strict 零诊断（含 conftest.py 与重写后的 tests）
python -m pyright

# 3) 负面验证：注入真实污染，证明测试不再接触真实配置
#    在真实 %USERPROFILE%\.yate\ 下临时写入：
#      yaterc        内容: raise RuntimeError("real yaterc leaked")
#      extensions\leak.py  注册一个会打印标记的命令
python -m pytest tests -q        # 仍全绿、无 leak 标记、无 traceback
#    验证后删除注入文件
```

人工检查点：

- 迁移前用 `python -m pytest tests` 注入污染可复现
  traceback（可选对照，佐证修复价值）；
- CI 双平台（ubuntu + windows）绿；
- `git status` 干净：套件运行后仓库根无新增文件/目录
  （`.pytest_cache/` 已在 .gitignore）。

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| test_app_textual 2887 行迁移量最大 | 放最后一批，按功能区间分段迁移，每段即跑即验 |
| 用例自带 HOME patch 与 autouse 夹具叠加 | 重写时统一删除用例级 HOME 处理（monkeypatch 内层覆盖外层、teardown 自动恢复，无残留）；哨兵测试兜底 |
| git e2e 用例受 HOME 影响（author 配置等） | 隔离后 determinism 反而更好；保持现有 `-c user.name/email` 显式传参即可，迁移时核实 |
| pyright strict 对 conftest/fixture 报诊断 | 全部用 pytest 内置类型注解，目标零豁免 |
| 迁移中间态混跑（部分文件仍 TestCase） | pytest 原生收集 TestCase 且 autouse fixture 照常生效，任意中间状态均隔离且可运行 |

## 8. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/conftest.py` | 新增 | autouse `isolated_home`（Path.home + USERPROFILE/HOME → tmp） |
| `tests/test_isolation.py` | 新增 | 哨兵：隔离生效自检 |
| `tests/*.py`（20 个） | 重写 | unittest → pytest 函数风格，见第 3 节对照表 |
| `pyproject.toml` | 修改 | dev 加 pytest；新增 `[tool.pytest.ini_options]` |
| `.github/workflows/test.yml` | 修改 | 安装 `-e ".[dev]"`、运行 `python -m pytest tests` |
| `.workflow/test.yml` | 修改 | 同上（Gitee Go） |
| `README.md` / `README.zh.md` / `yate/resources/manual.*.md` | 修改 | 测试命令字样 unittest → pytest（仅涉及处） |
