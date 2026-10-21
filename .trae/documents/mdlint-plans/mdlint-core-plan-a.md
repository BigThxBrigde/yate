# mdlint 核心包 + 自定义插件 (plan_a)

**波次**: wave-1（与 plan_c 并行）

## 一、输入

- pymarkdown 0.9.41 Python API（已验证可用）；
- 自定义插件机制（已验证：ID 格式 `YMnnn`，类名 = 文件名 PascalCase）；
- 既有工具包风格（`tools/pack/cli.py`、`tools/translate/cli.py`、`tools/_util.py`）。

## 二、独占文件清单

**新增**（全部在 `tools/mdlint/` 下）：

| 文件 | 职责 | 预估行数 |
|---|---|---|
| `tools/mdlint/__init__.py` | 惰性包根（不 re-export） | ~15 |
| `tools/mdlint/__main__.py` | `python -m tools.mdlint` 入口 shim | ~10 |
| `tools/mdlint/cli.py` | argparse CLI + 退出码 | ~120 |
| `tools/mdlint/lint.py` | `LintEngine` 封装 pymarkdown API | ~130 |
| `tools/mdlint/rules.py` | 规则配置（en/zh profile） | ~100 |
| `tools/mdlint/plugins/__init__.py` | 惰性包根 | ~5 |
| `tools/mdlint/plugins/ym_cjk_spacing.py` | YM001: CJK-拉丁空格 | ~50 |
| `tools/mdlint/plugins/ym_fullwidth_punct.py` | YM002: 中文全角标点 | ~60 |
| `tools/mdlint/plugins/ym_chinese_quotes.py` | YM003: 中文引号 | ~55 |
| `tools/mdlint/plugins/ym_heading_trailing_punct.py` | YM004: 标题尾标点 | ~45 |

**新增测试**：

| 文件 | 用例数 |
|---|---|
| `tests/test_mdlint.py` | ~15 |
| `tests/test_mdlint_plugins.py` | ~12 |

**不触碰**：`yate/`、`tools/pack/`、`tools/translate/`、`.githooks/`、`pyproject.toml`。

## 三、模块设计

### 3.1 `tools/mdlint/__init__.py`

```python
"""Markdown lint tool backed by pymarkdownlnt.

The package exposes a CLI via ``python -m tools.mdlint`` and a programmatic
:class:`LintEngine` for embedding (see :mod:`tools.pack.wiki`).
"""

from __future__ import annotations
```

惰性包根，不 re-export 子模块符号（遵守 `architecture-boundaries.md` §三.5）。

### 3.2 `tools/mdlint/__main__.py`

```python
"""Entry shim: ``python -m tools.mdlint``."""

from __future__ import annotations

import sys

from tools.mdlint.cli import main

sys.exit(main())
```

### 3.3 `tools/mdlint/lint.py`

核心封装类 `LintEngine`：

```python
class LintEngine:
    """Scan and fix Markdown text using pymarkdown with a given rule profile."""

    def __init__(self, lang: str, *, plugin_dir: Path | None = None) -> None:
        """Initialise with *lang* profile ('zh' or 'en').

        *plugin_dir* overrides the default custom plugin directory
        (``tools/mdlint/plugins``).
        """

    def scan(self, text: str) -> list[LintViolation]:
        """Return every violation found in *text*."""

    def fix(self, text: str) -> tuple[str, list[LintViolation]]:
        """Auto-fix what pymarkdown can; return (fixed_text, remaining)."""

    def scan_file(self, path: Path) -> list[LintViolation]:
        """Scan a file on disk."""

    def fix_file(self, path: Path) -> tuple[bool, list[LintViolation]]:
        """Fix a file in place; return (was_fixed, remaining)."""
```

```python
@dataclass(frozen=True)
class LintViolation:
    """One lint violation."""
    rule_id: str
    rule_name: str
    line: int
    column: int
    message: str
```

**依赖方向**：`lint.py` 只依赖 `pymarkdown.api` + `rules.py` + `tools/_util.py`（定位插件目录）。不 import `tools/pack`、`yate/`。

**关键实现细节**：

1. 构造时创建 `PyMarkdownApi` 实例；
2. 按 `lang` 从 `rules.py` 取规则配置，调用 `set_boolean_property` / `set_integer_property` / `set_string_property` 配置内置规则；
3. 若 `lang == "zh"`，调用 `add_plugin_path` 加载自定义插件目录；
4. `scan` 调 `api.scan_string(text)`，将 `scan_failures` 映射为 `LintViolation` 列表；
5. `fix` 先调 `api.fix_string(text)` 获取 `fixed_file`，再 `scan(fixed_file)` 获取残留违规。

### 3.4 `tools/mdlint/rules.py`

```python
"""Rule profiles for the en and zh languages.

Each profile is a mapping of pymarkdown rule IDs to their configuration.
Built-in rules are configured via the pymarkdown API; custom plugins
(loaded only for ``zh``) are enabled/disabled via the same mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

@dataclass(frozen=True)
class RuleProfile:
    """A set of rule configurations for one language."""
    lang: str
    enabled_rules: frozenset[str]
    disabled_rules: frozenset[str]
    properties: dict[str, str | int | bool]

def get_profile(lang: str) -> RuleProfile:
    """Return the rule profile for *lang* ('zh' or 'en')."""

def plugin_dir() -> Path:
    """Return the path to the custom plugins directory."""
```

**en 规则集**（基于 pymarkdown 内置规则）：

| 规则 | 含义 | 启用 | 参数 |
|---|---|---|---|
| MD001 | 标题层级递增 | Yes | - |
| MD003 | 标题风格一致 | Yes | `style=atx` |
| MD004 | 无序列表符号 | Yes | `style=dash` |
| MD005 | 列表缩进一致 | Yes | - |
| MD007 | 无序列表缩进 | Yes | `indent=4` |
| MD009 | 无行尾空格 | Yes | - |
| MD010 | 无硬制表符 | Yes | - |
| MD012 | 无连续空行 | Yes | `maximum=1` |
| MD013 | 行长限制 | Yes | `line_length=100` |
| MD018 | ATX 标题后需空格 | Yes | - |
| MD019 | ATX 标题无多空格 | Yes | - |
| MD022 | 标题前后空行 | Yes | - |
| MD023 | 标题顶格 | Yes | - |
| MD024 | 标题不重复 | Yes | `siblings_only=true` |
| MD025 | 单 H1 | Yes | - |
| MD026 | 标题无尾标点 | Yes | `punctuation=".,;:!?"` |
| MD029 | 有序列表前缀 | Yes | `style=one_or_ordered` |
| MD031 | 围栏代码块前后空行 | Yes | - |
| MD032 | 列表前后空行 | Yes | - |
| MD034 | 无裸 URL | Yes | - |
| MD035 | 水平线风格 | Yes | `style=---` |
| MD037 | 强调内无空格 | Yes | - |
| MD038 | 代码内无空格 | Yes | - |
| MD039 | 链接内无空格 | Yes | - |
| MD040 | 围栏代码块标语言 | Yes | - |
| MD041 | 首行标题 | Yes | - |
| MD042 | 无空链接 | Yes | - |
| MD046 | 代码块风格 | Yes | `style=fenced` |
| MD047 | 文件尾单换行 | Yes | - |
| MD048 | 围栏风格 | Yes | `style=backtick` |
| MD002 | 首标题须 H1 | **No** | - |
| MD006 | UL 起始左对齐 | **No** | - |
| MD033 | 禁内联 HTML | **No** | - |
| MD036 | 禁强调作标题 | **No** | - |
| MD049 | 强调风格 | **No** | - |
| MD050 | 粗体风格 | **No** | - |

**zh 规则集**（在 en 基础上调整 + 自定义插件）：

| 变更 | 说明 |
|---|---|
| MD013 禁用 | 中文行长不宜硬限（代码块/URL 除外） |
| MD026 调整 | 尾部标点含中文标点 `".;:!?。，；：！？"` |
| MD041 禁用 | 中文文档首行未必是 H1（可能是说明文字） |
| MD013 替代 | 由 `code_blocks` / `tables` 参数控制 |
| + YM001 | CJK-拉丁/数字空格 |
| + YM002 | 中文语境全角标点 |
| + YM003 | 中文引号（""''） |
| + YM004 | 标题尾部无中文标点 |

### 3.5 自定义插件

每个插件文件遵循 pymarkdown 命名约定：

#### `plugins/ym_cjk_spacing.py` (YM001)

检测 CJK 统一表意文字与 ASCII 字母/数字之间缺少空格。

```
你好world  ->  violation at column 3
hello 世界  ->  violation at column 6
你好 world  ->  ok
```

实现：`next_line` 中正则 `[\u4e00-\u9fff\u3400-\u4dbf][A-Za-z0-9]` 和反向。
排除：代码围栏内（``` 包裹行）、行内代码内（`...`）。

#### `plugins/ym_fullwidth_punct.py` (YM002)

检测中文语境中使用了半角标点（逗号、句号、分号、冒号、问号、感叹号、括号）。

实现：`next_line` 中检测 CJK 字符邻域的半角标点。
启发式：若行内存在 CJK 字符，则 `,` `.` `;` `:` `?` `!` `(` `)` 在 CJK 邻域（前后 1 字符内）视为违规。
排除：代码围栏 / 行内代码 / URL。

#### `plugins/ym_chinese_quotes.py` (YM003)

检测中文语境中使用英文引号 `"..."` / `'...'` 而非 `「...」` / `『...』` 或 `""` / `''`。

实现：`next_line` 中检测 CJK 邻域的 ASCII 引号。
排除：代码围栏 / 行内代码 / 代码块。

#### `plugins/ym_heading_trailing_punct.py` (YM004)

检测 ATX 标题行尾部是否带中文标点（`。，；：！？、`）。

实现：`next_line` 中匹配 `^#{1,6}\s+.*[。，；：！？、]\s*$`。

### 3.6 CLI 契约

```
python -m tools.mdlint [OPTIONS] PATH [PATH ...]

Options:
  --lang {zh,en}     Rule profile (default: en)
  --check            Scan and report violations (default mode)
  --fix              Auto-fix what is fixable, then report remaining
  --list-rules       Print enabled rules and exit
  --quiet            Suppress per-file output, only summary

Exit codes:
  0  Clean (or all fixable in --fix mode)
  1  Remaining violations after fix / scan found violations
  2  Usage error (bad args, missing files, backend failure)

stdout: violation reports (one per line: path:line:col: rule_id message)
stderr: errors and warnings
```

### 3.7 退出码映射（`cli.py`）

```python
def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; return process exit code."""
    # 0 = clean, 1 = violations, 2 = error
```

## 四、具体修改

### 4.1 新增 `tools/mdlint/__init__.py`

模块 docstring + `from __future__ import annotations`。无 re-export。

### 4.2 新增 `tools/mdlint/__main__.py`

3 行：import + `sys.exit(main())`。

### 4.3 新增 `tools/mdlint/lint.py`

- `LintViolation` dataclass（frozen=True）
- `LintEngine` 类
- `_default_plugin_dir()` 函数（返回 `Path(__file__).parent / "plugins"`）
- `_configure_api(api, profile)` 内部函数

### 4.4 新增 `tools/mdlint/rules.py`

- `RuleProfile` dataclass
- `get_profile(lang)` 函数
- `plugin_dir()` 函数
- `_EN_PROFILE` / `_ZH_PROFILE` 常量

### 4.5 新增 `tools/mdlint/cli.py`

- `build_parser()` -> `argparse.ArgumentParser`
- `main(argv=None) -> int`
- `_format_violation(path, violation) -> str`
- `_run_check(engine, paths) -> int`
- `_run_fix(engine, paths) -> int`
- `_list_rules(engine) -> int`

### 4.6 新增 4 个插件文件

见 §3.5。每个插件：
- 继承 `RulePlugin`
- `get_details()` 返回 `PluginDetails(plugin_id="YMnnn", ...)`
- `starting_new_file()` 空实现
- `next_line(context, line)` 实现检测逻辑
- 代码/围栏行跳过（内部状态跟踪）

## 五、测试用例

### 5.1 `tests/test_mdlint.py`

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_scan_clean_markdown_returns_empty` | `LintEngine("en")` | `scan("# Title\n\nBody\n")` | `result == []` |
| `test_scan_detects_md013_long_line` | `LintEngine("en")` | `scan("# Title\n" + "x" * 120 + "\n")` | `len(result) >= 1` 且 `result[0].rule_id == "MD013"` |
| `test_scan_detects_md047_missing_trailing_newline` | `LintEngine("en")` | `scan("# Title\n\nBody")` | 存在 `rule_id == "MD047"` 的违规 |
| `test_fix_resolves_trailing_newline` | `LintEngine("en")` | `fix("# Title\n\nBody")` | `fixed == "# Title\n\nBody\n"` 且 `remaining == []` |
| `test_fix_resolves_multiple_blanks` | `LintEngine("en")` | `fix("# Title\n\n\n\nBody\n")` | `"\n\n\n" not in fixed` |
| `test_zh_profile_loads_custom_plugins` | `LintEngine("zh")` | `scan("# 标题\n\n你好world\n")` | 存在 `rule_id == "YM001"` 的违规 |
| `test_zh_profile_skips_md013` | `LintEngine("zh")` | `scan("# 标题\n" + "中" * 120 + "\n")` | `result == []`（MD013 在 zh 禁用） |
| `test_scan_file_reads_disk` | tmp_path 写入违规 md | `engine.scan_file(path)` | 返回非空违规列表 |
| `test_fix_file_writes_disk` | tmp_path 写入可修复 md | `engine.fix_file(path)` | `(True, [])` 且文件内容已修复 |
| `test_list_rules_returns_sorted` | `LintEngine("en")` | 调 `_list_rules` 相关接口 | 规则列表非空且按 ID 排序 |
| `test_invalid_lang_raises` | - | `LintEngine("fr")` | `raise ValueError` |
| `test_cli_check_exit_1_on_violation` | tmp_path 写入违规 md | `main(["--check", "--lang", "en", str(path)])` | 返回 1 |
| `test_cli_check_exit_0_on_clean` | tmp_path 写入合法 md | `main(["--check", "--lang", "en", str(path)])` | 返回 0 |
| `test_cli_fix_exit_0_when_all_fixable` | tmp_path 写入可修复 md | `main(["--fix", "--lang", "en", str(path)])` | 返回 0 |
| `test_cli_list_rules_exit_0` | - | `main(["--list-rules"])` | 返回 0 |

### 5.2 `tests/test_mdlint_plugins.py`

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_ym001_detects_cjk_ascii_adjacency` | `LintEngine("zh")` | `scan("你好world\n")` | 存在 YM001 违规 |
| `test_ym001_clean_with_space` | `LintEngine("zh")` | `scan("你好 world\n")` | 无 YM001 违规 |
| `test_ym001_skips_code_fence` | `LintEngine("zh")` | `scan("```\n你好world\n```\n")` | 无 YM001 违规 |
| `test_ym002_detects_halfwidth_comma_near_cjk` | `LintEngine("zh")` | `scan("你好,世界\n")` | 存在 YM002 违规 |
| `test_ym002_clean_with_fullwidth_comma` | `LintEngine("zh")` | `scan("你好，世界\n")` | 无 YM002 违规 |
| `test_ym003_detects_ascii_quotes_near_cjk` | `LintEngine("zh")` | `scan("他说\"你好\"\n")` | 存在 YM003 违规 |
| `test_ym003_clean_with_chinese_quotes` | `LintEngine("zh")` | `scan("他说\u201c你好\u201d\n")` | 无 YM003 违规 |
| `test_ym004_detects_trailing_cjk_punct` | `LintEngine("zh")` | `scan("## 标题。\n")` | 存在 YM004 违规 |
| `test_ym004_clean_heading_no_trailing_punct` | `LintEngine("zh")` | `scan("## 标题\n")` | 无 YM004 违规 |
| `test_en_profile_has_no_custom_plugins` | `LintEngine("en")` | `scan("你好world\n")` | 无 YM001 违规（en 不加载自定义插件） |
| `test_plugin_dir_exists_and_contains_plugins` | - | `plugin_dir().iterdir()` | 至少 4 个 `.py` 文件 |
| `test_all_plugins_have_valid_id_format` | - | 扫描插件文件 | 每个 `plugin_id` 匹配 `^[A-Z]{2,3}\d{3}$` |

## 六、验收命令

```powershell
# 1. pyright strict 零诊断
pyright --pythonplatform Windows tools/mdlint/ tests/test_mdlint.py tests/test_mdlint_plugins.py

# 2. 新增测试全绿
.venv\Scripts\python.exe -m pytest tests/test_mdlint.py tests/test_mdlint_plugins.py -q

# 3. CLI 冒烟
.venv\Scripts\python.exe -m tools.mdlint --list-rules
.venv\Scripts\python.exe -m tools.mdlint --check --lang en README.md
.venv\Scripts\python.exe -m tools.mdlint --check --lang zh .trae\rules\architecture-boundaries.md
```

## 七、风险与回滚

| 风险 | 缓解 |
|---|---|
| pymarkdown 内部 API（`RulePlugin` / `PluginDetails`）变更 | 锁版本 `<1.0`；插件只用公开基类 |
| 自定义插件误报（代码块内 CJK 未跳过） | 测试覆盖代码围栏跳过逻辑 |
| 插件 ID 格式不符 pymarkdown 约束 | 已验证 `YMnnn` 格式可用 |
| 回滚 | 删除 `tools/mdlint/` 整目录即可 |

## 八、执行结果与偏离记录（2026-10-20）

### 8.1 偏离：规则配置改为 allowlist（原方案为"关闭少量规则"）

**现象**：按原 `_configure_api` 只 `disable_rule_by_identifier` 了 6 条规则
（MD002/MD006/MD033/MD036/MD049/MD050），其余 pymarkdown 默认规则（约 44 条）
仍然生效，导致：

- 规则集与 `RuleProfile.enabled_rules` 不一致——实测 zh 档在真实文档上冒出
  `MD028 no-blanks-blockquote`，而 MD028 从未出现在任何 profile 中；
- 性能劣化：单文档 52KB 的 `fix` 从 2.5s 涨到 9.2s（部分默认规则是超线性实现）。

**修正**：`_configure_api` 改为先 `disable_rule_by_identifier("*")` 再做逐条
`enable_rule_by_identifier(...)`（自定义 `YMnnn` 同样显式启用，实测可用）；
`RuleProfile` 去掉 `disabled_rules` 字段，未启用的规则由注释登记。

**验收**：新增 `tests/test_mdlint.py::test_zh_profile_ignores_rules_outside_the_allowlist`
（MD028 场景必须零违规）；`tests/test_mdlint.py` + `tests/test_mdlint_plugins.py`
共 39 例全绿。

### 8.2 偏离：单文件 lint 失败不再冒泡

**现象**：pymarkdown 0.9.41 在真实仓库的 3 个文档上自行抛异常
（`AssertionError: Rehydrate index must match up at end of paragraph`、
`BadPluginError: Plugin id 'MD031' ... critical failure`），原 CLI 会让异常穿透。

**修正**：`_run_check` / `_run_fix` 逐文件 try/except，打印
`error: cannot lint <path>: ...` 并计数；只要有文件失败，`main` 返回 **2**
（模块 docstring 早先把 2 定义为"usage error or lint backend failure"）。

**验收**：新增 `test_cli_backend_failure_on_one_file_exits_2`。

## 九、增量：目录 PATH 与 `--parallel`（2026-10-21）

### 9.1 需求与语义

- `PATH` 由"仅文件"扩展为**文件或目录**：目录递归收集 `*.md`（`batch.collect_markdown`，
  排序后去重）；既非文件也非目录 → `error: not a file or directory` + 退出码 2。
- `--parallel` **只在 PATH 含目录时生效**：
  - 含目录 → 目录展开出的全部文件（含同时给出的显式文件）进入进程池；
  - 仅文件 → 打印 `mdlint: --parallel needs a directory PATH; running sequentially`，
    按原顺序单进程执行（退出码语义不变）。

### 9.2 选型：进程池而非线程池

`pack wiki` 的并行用的是 `ThreadPoolExecutor`，因为它的工作单元是**阻塞的外部翻译命令**；
而 mdlint 的工作单元是纯 Python 的 pymarkdown 解析，属 CPU 密集，GIL 会让线程池几乎没有
加速。因此 `--parallel` 用 `ProcessPoolExecutor`，形状与 wiki 一致：
`BATCH_SIZE = 10` 个文件一个任务（`batch.chunk`），worker 数 `min(cpu_count, 批数)`
（wiki 的 `cpu_count * 2` 是为 I/O 等待留余量，CPU 密集不需要）。每个 worker 进程内按
语言惰性建引擎并缓存；父进程只传 `(path, lang)` 并回收 `FileOutcome`（可 pickle）。
结果按输入顺序输出，报告顺序与是否并行无关；父进程先构造一次引擎做后端校验，
依赖缺失时只报一条 `error: lint backend failure`，而不是每文件一条。

### 9.3 实测（本机，机器负载 100%）

`.trae/documents`（293 篇 / 2.32MB）`--check --auto-lang`：

| 模式 | 耗时 |
|---|---|
| 单进程 | 76.9s |
| `--parallel`（8 worker） | 25.5s（约 3×；空载机器上接近核数上限） |

### 9.4 新增测试

`tests/test_mdlint_parallel.py` 共 10 例：目录收集/排序、`chunk`/`worker_count` 边界、
目录展开、并行 check 报告全部违规、并行 fix 落盘、无目录时降级顺序执行、
缺失路径退出码 2、进程池启动失败 → 2、worker 返回错误值 → 2。

## 十、增量：错误输出纪律与进度条（2026-10-21）

### 10.1 问题

pymarkdown 在内部失败时用**自己的 logger** 打印完整 traceback
（`WARNING:pymarkdown.main: ...` 加整段栈），CLI 又把异常文本原样打到 stderr，
终端上出现与 pack wiki 纪律相悖的堆栈噪声。

### 10.2 处置

| 项 | 实现 |
|---|---|
| 关闭第三方堆栈 | `tools/mdlint/lint.py` 导入时给 `pymarkdown` logger 挂 `NullHandler` 并置 `propagate = False`；wiki 内嵌该引擎时同样受益 |
| 单行详细错误 | `lint.error_message(exc)`：取异常信息首行、折叠空白、上限 300 字符；`PyMarkdownApiException` 首行即 `Unexpected Error(AssertionError): ...`，`BadPluginError` 首行带位置与插件 id |
| CLI 顶层兜底 | `cli.main` 只在边界处捕获：`KeyboardInterrupt` → 130，其余 `Exception` → 一行 `error: ...` + 退出码 2；参数解析的 `SystemExit` 不拦截 |
| 并行 worker 一致 | `batch._lint_one` 用 `error_message` 落 `FileOutcome.error`，父进程打印同样是单行 |
| wiki 告警一致 | `_lint_page_text` 的"published as-is"告警改用同一函数 |
| 进度条 | `cli._start_progress`：仅在 `sys.stdout.isatty()` 且非 `--quiet` 时启动 rich `Progress`（spinner + 文件数 + 耗时）；逐文件报告经 `progress.console.print` 叠在活动区上方；`_run_parallel` 改用 `batch.iter_batches` 生成器，按输入顺序边完成边推进 |

### 10.3 验收

- 真实语料 `--check --auto-lang --parallel .trae/documents`：输出无 `WARNING:`、无 `Traceback`，只有 `path:line:col: rule message` 与总结行。
- 新增测试：`test_cli_failure_reports_one_line_without_traceback`、
  `test_main_boundary_never_prints_a_traceback`、`test_pymarkdown_logger_is_silenced`、
  `test_progress_bar_is_not_drawn_without_a_tty`、并行 worker 错误值单行断言。
