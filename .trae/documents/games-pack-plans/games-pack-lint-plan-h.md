# H 波：Lua lint 工具（`tools/lint_lua.py`）

上级：[overview.md](overview.md) ｜ 依赖：无（可最早开工，C-F 落地后复跑）｜ 独占文件：
`tools/lint_lua.py`、`tests/test_lua_lint.py`

## 一、目标

给仓库内的 Lua 代码一条**可复制执行、可进 CI、可被 pytest 固化**的 lint 通道：

```powershell
.venv\Scripts\python.exe tools/lint_lua.py            # 默认扫 yate/extensions/**/*.lua
.venv\Scripts\python.exe tools/lint_lua.py path ...   # 指定文件或目录
```

退出码：`0` 全部通过；`1` 有 issue；`2` 环境问题（lupa 不可用）。

> 背景：本机与 CI 均无 `luacheck` / `stylua` / `lua-language-server`（实测 `Get-Command` 全部 NOT FOUND），
> 但 `lupa` 属 `dev` extra 已随测试安装，因此用「lupa 编译 + 规则扫描」自建最小 lint，
> 保证语法层用的是**真正的 Lua 解析器**而不是正则猜。

## 二、检查项（逐条可独立失败）

| 规则码 | 检查 | 判据 |
|---|---|---|
| `syntax` | 语法 | `runtime.compile(source)` 抛错 → `文件:行 语法错误: <msg>` |
| `tab` | 缩进 | 行内含 `\t` |
| `trailing-space` | 行尾 | 行尾有空格/制表符 |
| `line-length` | 行长 | 显示字符数 > 100（按 Python `len`，UTF-8 解码后） |
| `eof-newline` | 文件尾 | 不以单个 `\n` 结尾（或多于一个空行） |
| `crlf` | 换行 | 含 `\r` |
| `banned-call` | 禁项 | 出现 `print(` / `io.` / `os.execute` / `os.exit` / `dofile` / `loadfile`（注释内不算：先剥 `--` 之后） |
| `global-leak` | 全局泄漏 | 顶层（列 1 起）`function <name>(` 或 `^[A-Za-z_]\w*\s*=` 且名字不在白名单 |
| `require` | 模块白名单 | `require("x")` 的 x 不属于 `{"yate"} ∪ lib/*.lua 的 stem` |

白名单（`global-leak`）：`yate`、`api`、`mod`、`setup`、`teardown`。
白名单（`require`）：由 `yate.paths.bundled_extensions_dir()/"lib"/"*.lua"` 的 stem 动态生成。

## 三、实现要点

```python
"""Minimal Lua lint for the bundled game extensions.

Rules are deliberately narrow: a real Lua parse via lupa (the same engine the
extension runtime uses), plus textual style guards the repo already applies to
Python ...
"""
from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yate.paths import bundled_extensions_dir

@dataclass(frozen=True)
class Issue:
    path: Path
    line: int
    rule: str
    message: str
    def format(self) -> str: ...

def _lua_runtime() -> Any: ...          # importlib.import_module("lupa").LuaRuntime()，缺失时抛 LintUnavailable
def check_source(path: Path, source: str, allowed_modules: set[str]) -> list[Issue]: ...
def check_paths(paths: Sequence[Path]) -> list[Issue]: ...
def main(argv: Sequence[str] | None = None) -> int: ...
```

- 语法检查每条文件一次（编译整份源码），错误消息里的 `chunkname:line:` 解析成 `Issue.line`。
- 注释剥离：只用于 `banned-call` 与 `global-leak`，按行 `line.split("--", 1)[0]`（已知局限：
  字符串里含 `--` 会误判，登记为可接受近似，规则只作用于**扩展文件**且由测试固定）。
- 目录参数递归 `rglob("*.lua")`；默认参数 = `[bundled_extensions_dir()]`。
- 输出格式：`relative/path.lua:12: [tab] message`（一行一条），末尾 `N issue(s)`；
  路径相对仓库根打印（`Path.relative_to(Path.cwd())`，失败则打绝对路径）。
- `main` 里 `print(...)` 是**允许的**：`tools/` 不在 `PRINT_EXEMPT_SITES` 扫描面
  （`tests/test_architecture.py` 只扫 `yate/`）。

## 四、测试 `tests/test_lua_lint.py`

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_bundled_lua_files_pass_the_linter` | `check_paths([bundled_extensions_dir()])` 为空（实文件 0 issue） |
| 2 | `test_syntax_error_is_reported_with_a_line_number` | 临时文件 `return (` → 有 `syntax` issue 且 `line >= 1` |
| 3 | `test_tabs_and_trailing_space_are_reported` | 各一条 |
| 4 | `test_long_line_is_reported` | 101 字符行 → `line-length` |
| 5 | `test_missing_final_newline_is_reported` | 末尾无 `\n` |
| 6 | `test_banned_calls_are_reported` | `print("x")` / `io.open` / `os.execute` 各一条 |
| 7 | `test_global_leak_is_reported_and_whitelisted_names_pass` | `foo = 1` 报错；`yate = {}` 通过 |
| 8 | `test_unknown_require_is_reported` | `require("nope")` 报错；`require("game_engine")` 通过 |
| 9 | `test_main_exit_codes` | 干净目录 `0`、违规文件 `1`（`capfd` 断言输出） |

临时文件写入 `tmp_path`，**不得**污染仓库。

## 五、验收命令

```powershell
.venv\Scripts\python.exe tools/lint_lua.py
.venv\Scripts\python.exe -m pytest tests/test_lua_lint.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
```

通过判据：实文件 0 issue、9 条用例全绿、pyright 零诊断。

## 六、风险

| 风险 | 缓解 |
|---|---|
| 正则近似（注释/字符串）误报 | 规则白名单 + 只扫扩展文件；测试固化行为 |
| lupa 不在环境里 | 退出码 `2` + 明确提示 `pip install yate[lua]`；pytest 用例用 `requires_lupa` 跳过 |
| 行长按字符数而非显示宽度 | 文档写明；Lua 文件以 ASCII + 字形表为主，差异可忽略 |
