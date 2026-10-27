# mdlint wiki 集成 (plan_b)

**波次**: wave-2（依赖 wave-1 的 plan_a + plan_c 全部验收通过）

## 一、输入

- plan_a 产出的 `tools.mdlint.lint.LintEngine`；
- `tools/pack/wiki.py` 的三条产出路径（已定位行号）；
- `tools/pack/errors.py` 的 `Code` 枚举。

## 二、独占文件清单

**修改**：

| 文件 | 改动类型 | 改动量 |
|---|---|---|
| `tools/pack/wiki.py` | 新增 `_lint_page_text` 函数 + 4 处调用插入 | ~50 行新增 |
| `tools/pack/errors.py` | 新增 `Code.WIKI_LINT_FAILED` 枚举值 | ~3 行新增 |

**新增测试**：

| 文件 | 用例数 |
|---|---|
| `tests/test_pack_wiki_lint.py` | ~8 |

**不触碰**：`tools/translate/`、`yate/`、`tools/mdlint/`、`.githooks/`、`pyproject.toml`。

## 三、wiki 产出链路的 lint 插入点

### 3.1 路径总览

```mermaid
flowchart TD
    S["collect_sources()"] --> P["_prepare_pages()"]
    P -->|"zh_bytes 读源"| ZH["写中文页<br/>L1182: _write_page_bytes"]
    P -->|"en_bytes 拷贝孪生"| EN_COPY["写双语孪生英文页<br/>L1195: _write_page_bytes"]
    P -->|"plans 进入翻译"| T["_translate_pending()"]
    T -->|"主线程写盘"| EN_TRANS["写翻译英文页<br/>L1361: _write_page_text"]
    T -->|"导航页"| NAV["写 Home/Sidebar<br/>L1472-1475: _write_page_text"]

    ZH -.->|"插入 lint zh"| LZH["_lint_page_text(zh_text, 'zh')"]
    EN_COPY -.->|"插入 lint en"| LEN1["_lint_page_text(en_text, 'en')"]
    EN_TRANS -.->|"插入 lint en"| LEN2["_lint_page_text(en_text, 'en')"]
    NAV -.->|"插入 lint"| LNAV["_lint_page_text(nav_text, lang)"]
```

### 3.2 逐处插入点（文件:行号）

#### 插入点 1: 中文页原样写盘

**位置**: `tools/pack/wiki.py` L1180-1182

**现状**:

```python
zh_bytes = _read_source_bytes(page.zh_source)
digest = hashlib.sha256(zh_bytes).hexdigest()
_write_page_bytes(target / page.zh_target, zh_bytes)
```

**改后**:

```python
zh_bytes = _read_source_bytes(page.zh_source)
digest = hashlib.sha256(zh_bytes).hexdigest()
zh_bytes = _lint_page_bytes(zh_bytes, "zh")
_write_page_bytes(target / page.zh_target, zh_bytes)
```

`_lint_page_bytes` 是新辅助函数，内部解码 -> fix -> 编码。

#### 插入点 2: 双语孪生英文页拷贝写盘

**位置**: `tools/pack/wiki.py` L1191-1195

**现状**:

```python
try:
    en_bytes = page.en_source.read_bytes()
except OSError:
    en_bytes = None
if en_bytes is not None:
    _write_page_bytes(en_path, en_bytes)
```

**改后**:

```python
try:
    en_bytes = page.en_source.read_bytes()
except OSError:
    en_bytes = None
if en_bytes is not None:
    en_bytes = _lint_page_bytes(en_bytes, "en")
    _write_page_bytes(en_path, en_bytes)
```

#### 插入点 3: 翻译产出英文页落盘

**位置**: `tools/pack/wiki.py` L1361

**现状**:

```python
_write_page_text(target / page.en_target, outcome.english)
```

**改后**:

```python
linted_english = _lint_page_text(outcome.english, "en")
_write_page_text(target / page.en_target, linted_english)
```

此处用 `_lint_page_text`（文本版）因为 `outcome.english` 已是 `str`。

#### 插入点 4: 导航页写盘

**位置**: `tools/pack/wiki.py` L1472-1475

**现状**:

```python
_write_page_text(target / "Home.md", home_zh)
_write_page_text(target / "_Sidebar.md", sidebar_zh)
_write_page_text(target / "Home.en.md", home_en)
_write_page_text(target / "_Sidebar.en.md", sidebar_en)
```

**改后**:

```python
_write_page_text(target / "Home.md", _lint_page_text(home_zh, "zh"))
_write_page_text(target / "_Sidebar.md", _lint_page_text(sidebar_zh, "zh"))
_write_page_text(target / "Home.en.md", _lint_page_text(home_en, "en"))
_write_page_text(target / "_Sidebar.en.md", _lint_page_text(sidebar_en, "en"))
```

### 3.3 新增辅助函数

在 `tools/pack/wiki.py` 中新增（位于 `_write_page_text` 之后，约 L224）：

```python
def _lint_page_text(text: str, lang: str) -> str:
    """Run the mdlint fix pass on *text* and return the cleaned version.

    Remaining violations (not auto-fixable) are logged as warnings;
    they do not abort the wiki run.  The lint engine is created lazily
    and cached for the process lifetime (one per *lang*).
    """
    engine = _get_lint_engine(lang)
    fixed, remaining = engine.fix(text)
    if remaining:
        for v in remaining[:5]:  # cap warning noise
            errors.log.warning(
                "wiki lint: %s:%d:%d %s %s",
                "<page>", v.line, v.column, v.rule_id, v.message,
            )
    return fixed


def _lint_page_bytes(data: bytes, lang: str) -> bytes:
    """Decode *data* as UTF-8, lint, and re-encode."""
    text = data.decode("utf-8", errors="replace")
    fixed = _lint_page_text(text, lang)
    return fixed.encode("utf-8")


_LINT_ENGINES: dict[str, LintEngine] = {}


def _get_lint_engine(lang: str) -> LintEngine:
    """Return a cached :class:`LintEngine` for *lang*."""
    if lang not in _LINT_ENGINES:
        from tools.mdlint.lint import LintEngine
        _LINT_ENGINES[lang] = LintEngine(lang)
    return _LINT_ENGINES[lang]
```

### 3.4 `Code` 枚举扩展

在 `tools/pack/errors.py` L55 后新增：

```python
WIKI_LINT_FAILED = "WIKI-0109"
```

此 code 用于 lint 引擎本身不可用（import 失败、插件加载失败等）的极端场景。
常规 lint 违规（fix 后仍有残留）只记 warning，不上报 error。

### 3.5 多线程约束

- `_get_lint_engine` 在主线程调用（`_prepare_pages` 与 `_translate_pending` 的
  写盘循环均在主线程）；
- `LintEngine` 实例线程安全（pymarkdown API 每次 `scan_string` / `fix_string`
  创建独立内部状态）；
- worker 线程（`_run_batch`）不碰 lint 引擎——它们只做翻译，不写盘。

### 3.6 manifest digest 不受影响

- digest 在 `_prepare_pages` L1181 按 `zh_bytes`（**源原始字节**）计算；
- lint 在 L1182 之后执行，修改的是写盘内容，不改 `zh_bytes` 变量；
- 因此 freshness 判定（下一轮 run 比较 manifest 记录的 digest 与源字节）不受影响。

## 四、具体修改

### 4.1 `tools/pack/errors.py`

在 `Code` 枚举的 `WIKI_GIT_FAILED = "WIKI-0108"` 之后新增一行：

```python
WIKI_LINT_FAILED = "WIKI-0109"
```

### 4.2 `tools/pack/wiki.py`

1. **新增 import**（文件头部，L76 附近）：

```python
from tools.mdlint.lint import LintEngine, LintViolation
```

注意：这是延迟 import（在 `_get_lint_engine` 内），不在模块顶部。
原因：`tools.mdlint` 依赖 `pymarkdownlnt`（可选依赖），wiki 不应在 import 时
强制要求安装。

1. **新增辅助函数**（L224 附近，`_write_page_text` 之后）：

```python
_LINT_ENGINES: dict[str, LintEngine] = {}


def _lint_page_text(text: str, lang: str) -> str:
    ...


def _lint_page_bytes(data: bytes, lang: str) -> bytes:
    ...


def _get_lint_engine(lang: str) -> LintEngine:
    ...
```

1. **插入点 1**（L1182）：在 `_write_page_bytes` 调用前加 `zh_bytes = _lint_page_bytes(zh_bytes, "zh")`

2. **插入点 2**（L1195）：在 `_write_page_bytes(en_path, en_bytes)` 前加 `en_bytes = _lint_page_bytes(en_bytes, "en")`

3. **插入点 3**（L1361）：将 `_write_page_text(target / page.en_target, outcome.english)` 改为
   `_write_page_text(target / page.en_target, _lint_page_text(outcome.english, "en"))`

4. **插入点 4**（L1472-1475）：4 处 `_write_page_text` 调用包裹 `_lint_page_text`

## 五、测试用例

### 5.1 `tests/test_pack_wiki_lint.py`

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_zh_page_written_with_lint_fix` | repo fixture 含 CJK-Latin 无空格源 | `wiki.run(target, None, repo_root=repo)` | 写出的 zh 页中 CJK-Latin 已加空格 |
| `test_en_twin_page_written_with_lint_fix` | repo fixture 含 trailing spaces 的 en 孪生页 | `wiki.run(target, None, repo_root=repo)` | 写出的 en 页 trailing spaces 已清除 |
| `test_translated_en_page_linted` | mock translate_cmd 返回含 MD047 违规的译文 | `wiki.run(target, cmd, repo_root=repo)` | 写出的 en 页末尾有换行 |
| `test_nav_pages_linted` | 正常 repo | `wiki.run(target, None, repo_root=repo)` | Home.md / _Sidebar.md 合法 |
| `test_lint_does_not_affect_manifest_digest` | 含 lint 违规源的 repo | 两轮 `wiki.run` | manifest 中 digest 一致（按源字节算） |
| `test_lint_engine_import_error_reported` | mock `tools.mdlint.lint` import 失败 | `wiki.run(...)` | 报 `WIKI-0109` 错误或优雅降级 |
| `test_lint_violations_logged_not_aborting` | 含不可修复违规的源 | `wiki.run(...)` | run 返回 0（不中止），warning 日志含违规信息 |
| `test_existing_wiki_tests_unaffected` | 原 test_pack_wiki.py 的 fixture | 原测试全部运行 | 全绿（lint 对合法 Markdown 零干预） |

## 六、验收命令

```powershell
# 1. pyright strict 零诊断
pyright --pythonplatform Windows tools/pack/wiki.py tools/pack/errors.py tests/test_pack_wiki_lint.py

# 2. wiki 相关测试全绿（含既有 + 新增；-n auto 依赖 pytest-xdist）
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py tests/test_pack_wiki_errors.py tests/test_pack_wiki_parallel.py tests/test_pack_wiki_lint.py -q -n auto

# 3. 架构测试无回归
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 七、风险与回滚

| 风险 | 缓解 |
|---|---|
| lint 修改了 wiki 产出导致与源不同步 | 源不改，产出是"发布态"；用户看到 fix 后的版本 |
| lint 引擎 import 失败导致 wiki run 崩溃 | `_get_lint_engine` 内 try/except，失败时记 warning 并返回原文本 |
| 既有 wiki 测试因 lint 介入而行为变化 | 测试 fixture 均为合法 Markdown，lint 零干预 |
| 回滚 | 删除 4 处插入点 + 辅助函数 + `WIKI-0109` 枚举值 |

## 八、执行结果与偏离记录（2026-10-20）

### 8.1 实测：全量 lint 成本与 profile 泄漏修正

- 本仓库 `.trae/documents` 共 **293 篇 / 2.32MB**；按修正后的 allowlist 配置
  （见 plan_a §8.1）跑一遍 zh 档 `fix` 实测 **184s**（≈ 630ms/篇，其中约
  50ms 是 pymarkdown 每次调用的固定开销）。修正前同一批文档因 44 条默认规则
  叠加，量级为 20~30 分钟。
- 结论：wiki 全量发布（zh 页 + 英文孪生 + 翻译页 + 导航页）新增约 **4~6 分钟**
  CPU 时间，与翻译阶段（外部 LLM 命令，按页计秒级到分钟级）相比可接受，
  因此**保留 plan_b 原定的 4 处插入点**，不做覆盖率妥协。

### 8.2 偏离：单页 lint 崩溃降级（新增）

pymarkdown 在 3 个真实文档上自行抛异常（详见 plan_a §8.2）。`_lint_page_text`
在 `engine.fix()` 外层捕获异常，记 `wiki lint: <page> could not be linted (...)；
published as-is` 警告并返回原文：

- 引擎**构造**失败（依赖缺失 / 插件加载失败）仍按原方案报
  `error[WIKI-0109]`（环境问题）；
- **单页**处理失败只降级为 warning，绝不阻断发布。

验收：新增 `tests/test_pack_wiki_lint.py::test_lint_backend_crash_publishes_page_as_is`。

### 8.3 偏离：两个既有测试的适配

| 测试 | 问题 | 处理 |
|---|---|---|
| `test_pack_wiki.py::test_keyboard_interrupt_maps_to_exit_130` | 未隔离 `_util.repo_root`，走真实仓库时会对 293 篇真实文档跑 lint（分钟级，实测挂起） | 补 `monkeypatch.setattr("tools._util.repo_root", lambda: repo)`，与 `test_pack_wiki_parallel.py` / `test_pack_wiki_errors.py` 既有写法一致 |
| `test_pack_wiki_parallel.py::test_interrupt_leaves_the_queued_batches_untranslated` | 墙钟阈值 1.6s 被 lint 的固定开销（25 篇 × 2 次 API 调用）挤爆（实测 2.2s） | 该用例关注中断延迟而非 lint 吞吐：测试内把 `wiki._lint_page_text` 换成透传，阈值与断言保持原样 |

### 8.4 收尾验收

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/test_pack_wiki.py tests/test_pack_wiki_errors.py tests/test_pack_wiki_parallel.py tests/test_pack_wiki_lint.py tests/test_mdlint.py tests/test_mdlint_plugins.py tests/test_githook.py -q` | 全绿（详见收尾汇报） |
| `python -m pyright --pythonplatform Windows tools/pack/wiki.py tools/pack/errors.py tools/mdlint tests/test_pack_wiki_lint.py` | 0 errors |

### 8.5 评审修复（code-review-expert，2026-10-20）

| 发现 | 处置 |
|---|---|
| `fix_file` 在 Windows 上把 LF 写成 CRLF（绕开 `core.autocrlf=false`，修复内容以 CRLF 进库） | [lint.py](../../tools/mdlint/lint.py) 改为 `write_text(..., newline="")`；新增 `test_fix_file_keeps_lf_line_endings` 与 hook 集成用例的 `b"\r" not in stored` 断言 |
| CLI 退出码优先级：任一文件后端失败即返回 2，吞掉其他文件的违规 | [cli.py](../../tools/mdlint/cli.py) 改为"违规优先（1），无违规时才用 2 表示失败"；新增 `test_cli_violations_win_over_a_failed_file` |
| `functools.cache` 共享引擎的线程安全前提未固定 | `_get_lint_engine` docstring 明示"所有 lint 调用都在主线程" |
| `plugin_dir` 在 `rules.py` / `lint.py` 双份定义 | `LintEngine` 改用 `rules.plugin_dir()`，删除私有副本；形参改名 `custom_plugin_dir` 以免与函数重名 |
| `lang_for_path` 中 `README/CHANGELOG` 分支为死分支，且 `.trae` 判断先于 `.en.md` | 删除死分支，`.en.md` 提前判定；新增 `test_lang_for_path_en_suffix_wins_inside_trae` |
| 已知限制（评审第二轮已修复）：YM001/YM002 用正则跟踪围栏，列表内 4 空格缩进围栏、`~~~` 夹杂与双反引号 code span 会误报 | 抽出 `tools/mdlint/fences.py`（`FenceTracker` + `mask_code_spans`），按围栏字符与长度配对关闭、按反引号串长度匹配 code span；四个插件共用该实现，新增 4 条回归用例 |
| YM004 只匹配列 0 的 ATX 标题，1–3 空格缩进的合法标题漏报 | 正则改为 `^ {0,3}#{1,6}\s+...`，新增 `test_ym004_detects_indented_atx_heading` |
| `--auto-lang` 帮助文本与 `lang_for_path` 契约不符（`.trae/**/*.en.md` 实际走 en） | 帮助文本补齐三条路由规则 |
| `_LANG_CHOICES` 与 `rules._VALID_LANGS` 两份语言清单 | `rules.LANGS` 单点定义，CLI 直接复用 |
| `--fix` 的后端失败分支无测试 | 新增 `test_cli_fix_backend_failure_exits_2` |
| hook 注释仍指向已删除的 grep 过滤器 | 注释改为 `case` 过滤 |

## 九、增量：wiki 全量 lint 并行化（2026-10-27）

### 9.1 需求

`python -m tools.pack wiki --translate-cmd ... --push` 的 lint 阶段原本**逐页串行**
（`_prepare_pages` 每篇读盘后立刻 `_lint_page_bytes`，翻译结果也在 `as_completed`
循环里逐页 lint）。全量实测约 660s，与并行化的 mdlint CLI（plan_a §9）不成比例，
要求在 wiki 内复用同一进程池并行 fix。

### 9.2 方案：两相位 + 池化 fix

| 项 | 实现 |
|---|---|
| 池 API | `tools/mdlint/batch.py` 新增 `TextOutcome` / `fix_texts`（`(lang, text)` 进、结果按**输入顺序**出），与 `iter_batches` 共用 `_engine` 惰性缓存与 worker 数策略 |
| 任务粒度 | `TEXT_BATCH_SIZE = 1`（"longest processing time" 调度），因 pymarkdown 的 `fix` 对单篇是**超线性**的（实测 78 KiB 手册 67s，小页几十毫秒），粗粒度会把几篇大的捆进同一个任务 |
| 调度 | 父进程按文本长度降序分发，回收后按原索引还原顺序 |
| wiki 读段 | `_prepare_pages` 改为两相位：先读全部源 + 收集 lint 请求，再一次性并行 fix，最后统一落盘；`_PagePlan` 与 manifest 语义不变 |
| wiki 译段 | `_publish_translations` 在翻译池排干后对全部落地页做一次并行 fix + 落盘（原先逐页 lint，等价但不可并行）；中断分支先发布已落地页再抛出，避免 Ctrl+C 丢掉已完成的译页 |
| 小批量 | 双阈值：篇数 `PARALLEL_LINT_MIN_TEXTS = 2 * BATCH_SIZE`（20）与文本量 `PARALLEL_LINT_MIN_CHARS = 128 KiB`。池启动约 0.5s（spawn + 后端 import），单页约 75ms，所以小仓库仍走进程内 `_lint_page_text`；而 `fix` 对单篇超线性（78 KiB 手册 67s），几篇大文档即可越过文本阈值并行 |
| 失败语义 | 完全沿用 serial 路径：引擎构造失败 → `error[WIKI-0109]`；单页 lint 崩溃 → `published as-is` 警告；剩余违规 → 每页最多 5 条 warning。worker 侧异常折叠为 `TextOutcome.error` 值，不炸池 |

否决路线：① 线程池 —— pymarkdown 是纯 Python CPU 密集，GIL 下无加速；
② 每页起一次池 —— 启动成本高于单页 lint；③ 只并行翻译阶段 —— 中文页在 `_prepare_pages`
就已全部 lint，那才是耗时大头。

### 9.3 实测（本机 8 逻辑核，语料 454 篇文本）

| 模式 | 耗时 |
|---|---|
| 串行（按篇长分层抽样 35 篇外推） | ≈660s |
| 池化（`TEXT_BATCH_SIZE = 4`，无 LPT） | 330s |
| 池化（LPT，一篇一任务） | **252s**（≈2.6×；受单篇 67s 下界与物理核数限制） |

结论：全量 wiki 发布的 lint 阶段从"约 11 分钟"降到"约 4 分钟"；单篇巨文档的
超线性开销是剩余下界，属 pymarkdown 自身特性，不在本轮范围。

### 9.4 测试适配与新增

| 用例 | 处理 |
|---|---|
| `test_pack_wiki_parallel.py::test_interrupt_leaves_the_queued_batches_untranslated` | 该用例只关注中断延迟，25 篇会触发池化 lint（约 +1s），改为把 `tools.mdlint.batch.fix_texts` 换成透传（原来换的是 `wiki._lint_page_text`） |
| `test_pack_wiki_lint.py::test_bulk_lint_runs_through_the_process_pool` | 新增：加宽仓库越过阈值，断言请求确实进了池，且池的修复结果落盘 |
| `test_pack_wiki_lint.py::test_pool_lint_failure_publishes_page_as_is` | 新增：worker 报错（`TextOutcome.error`）时单页原样发布 + 一条 warning |

`test_lint_backend_crash_publishes_page_as_is` 仍覆盖串行路径（fixture 4 篇 < 阈值）。

### 9.5 收尾验收

| 命令 | 结果 |
|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors |
| `python -m pytest tests/test_pack_wiki_lint.py tests/test_pack_wiki_parallel.py tests/test_pack_wiki.py tests/test_pack_wiki_errors.py tests/test_mdlint.py tests/test_mdlint_parallel.py tests/test_mdlint_plugins.py tests/test_architecture.py -q` | 全绿（1 skip 为既有用例） |

### 9.6 评审修复（2026-10-27，pr-review 预评审）

| 级别 | 发现 | 处置 |
|---|---|---|
| MAJOR | 译页改为池排干后统一落盘，Ctrl+C 会丢弃本轮已完成的译页 | 中断分支先 `_publish_translations(landed, target)`（尽力而为，失败只记 warning）再 `raise outcome.error`；新增 `test_interrupt_publishes_the_pages_that_already_landed` |
| MAJOR | 并行门槛只看篇数，几篇大文档仍串行（单篇 67s → 数分钟） | 追加文本阈值 `PARALLEL_LINT_MIN_CHARS = 128 KiB`（篇数**与**文本量都低于下限才串行）；新增 `test_text_size_floor_lints_in_the_pool_below_the_count_floor` |
| MAJOR | `fix_texts` 用 `with ProcessPoolExecutor(...)`，lint 期间 Ctrl+C 会等队列排干（分钟级） | 改为显式 `shutdown(wait=False, cancel_futures=True)` 的 `except BaseException` 分支（与翻译池 R-15 同形）；新增 `test_fix_texts_cancels_queued_work_when_the_pool_fails` |
| MINOR | `_translate_pending` 的 `translated = 0` / `digests = {}` 是死初始化 | 删除（返回值在 `try` 内唯一赋值） |
| MINOR | `_landed_pages` 返回 `(page, digest, english)` 位置元组 | 改为冻结 dataclass `_LandedPage` |
| MINOR | 本文件 §8.5 用例名笔误、`_PagedPlan` 笔误、文末残留重复表格行 | 已订正 |

残余取舍：中断时的发布仍会跑一次 lint，因此 Ctrl+C 后最长要等"已落地页的一次
lint"（全量上限约 4 分钟）。这是为保住"发布的页一定 lint 过"这条质量线——若中断时
跳过 lint 直接落盘，manifest 不记录这些页，下一次运行会按 adopted（`FRESH`）保留，
未 lint 的正文会静默留在被推送的 wiki 里。控制台会先打印
`publishing N finished page(s) before the interrupt propagates` 说明这段等待。

### 9.7 增量：进度显示、中断静默、池注入（2026-10-28）

用户三条需求（附 Ctrl+C 后子进程打印堆栈的截图）：

1. **wiki 内 lint 要有与独立 CLI 一致的进度条与信息输出**。新增 `_LintBar`
   （rich `Progress`，列布局与独立 CLI 相同：Spinner/描述/Bar/百分比/耗时；TTY
   门控与独立 CLI 一致，非 TTY 只出汇总行），串行路径逐页 `step()`，池路径由
   `fix_texts` 的 `progress` 回调回放真实完成数；每轮 lint 结束打一行
   `wiki lint: N page(s) in X.Xs`。salvage 发布（中断打捞）传
   `show_bar=False`——翻译 bar 还在该 console 上，两个 live Progress 会打架；
   尾部发布移到 `finally` 之后，lint bar 与翻译 bar 依次独占 console。
2. **Ctrl+C 不打印错误堆栈**。三层噪音来源与处置：
   - 子进程 worker 各自打印 `KeyboardInterrupt` 堆栈（Windows 把 CTRL_C_EVENT
     发给整组进程）→ `tools.mdlint.batch.worker_initializer()`
     （`ProcessPoolExecutor(initializer=...)`，worker 内
     `signal.signal(SIGINT, SIG_IGN)`）：worker 无视信号做完当前任务，
     父进程拥有中断语义；
   - 排队任务排干 → `fix_texts` 的 `except BaseException` 分支
     `cancel_futures=True`（9.6 已有）；
   - 退出时 `Exception ignored on threading shutdown` → 池干净关闭后消失。
   实测（烟雾脚本：TEMP 建 40 篇大文档，真实 CLI 跑 wiki，8s 后
   `GenerateConsoleCtrlEvent(0, 0)` 广播整组）：输出仅
   `tools.pack: interrupted`，exit 130，无 Traceback / SpawnProcess 堆栈 /
   threading 噪音。注意脚本细节：`CREATE_NEW_PROCESS_GROUP` 的子进程默认
   禁用 Ctrl+C，烟雾里需 `SetConsoleCtrlHandler(None, False)` 恢复才是真实
   前台场景。
3. **lint 工具开放线程池（实为进程池）API**：`fix_texts(items, *, pool=None,
   progress=None)` —— `pool=None` 自建自关（独立 CLI 与一次性调用）；
   注入的池归所有者，`fix_texts` 只取消本轮 pending、从不 shutdown。
   wiki 侧新增 `_LintPool`（惰性 `ensure()`：`ProcessPoolExecutor` 对象创建
   不 spawn，串行小运行零成本；`shutdown(wait=False, cancel_futures=True)`），
   `run()` 创建一个实例贯穿 rebuild / salvage / publish 全部 lint 相位，
   `try/finally` 统一 teardown。`submit` 阶段也纳入 `except BaseException`
   保护（中断打中 submit 时不泄漏已提交的 future）。

测试：`test_fix_texts_pool_ownership_contract`（注入池不关 / 自建池关闭）、
`test_progress_reports_each_landed_document`（回调逐文档到达 `(total, total)`）、
`test_worker_initializer_ignores_sigint`、`test_one_lint_pool_serves_the_whole_run`
（rebuild 与 publish 两相位收到同一池对象）、
`test_main_thread_interrupt_salvages_the_landed_pages`（主线程直收 Ctrl+C
同样打捞已落地页）；三个既有 fake（`recording` / `failing` / `passthrough_fix`）
签名补齐 `pool` / `progress` 形参。`wiki.py` 复测 2149 行（`splitlines()` 口径），
维持豁免。
