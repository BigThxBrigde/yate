# pack wiki 工具增强方案（issue IKJPEK）

> 分支：`enh/pack-wiki`（worktree：`../yate-pack-wiki`）
> Issue：<https://gitee.com/jermaine/yate/issues/IKJPEK>（ENHANCE - PACK WIKI TOOL 增强）
> 状态：待执行（无人值守时段，已按 `task-orchestration.md` §二.3 直接批准进入执行）

## 一、目标与非目标

### 目标

1. **统一异常输出**：任何错误都不向终端打印 traceback，改为
   `error[<CODE>]: <message>`（stderr）+ 可选 `hint:` 行；traceback 只进
   debug 通道（`--debug` 才显示、始终写 logging）。
2. **并行翻译**：
   - 待翻译页按**每批最多 10 份文档**切分为任务池；
   - 用线程池从任务池取任务执行（瓶颈是外部翻译子进程，线程足够且
     `translate_via_cmd` 无进程级共享状态）；
   - 并发上限 **CPU 核心数 × 2**（`--jobs` 可下调，上限硬 clamp）；
   - 实时报告排队 / 执行中 / 成功 / 失败状态与总体进度。
3. 顺带修掉 issue 复现出的真实缺陷：`wiki.py:618` 读 `zh_source` 无保护，
   源文件在收集后消失会抛裸 `FileNotFoundError`（即 issue 里的堆栈）。

### 非目标

- 不改 `translate_via_cmd` 的 I/O 协议（stdin 中文 → stdout 英文）与 900s
  超时语义（前序 `wiki-translate-progress-plan.md` 明确列为非目标）。
- 不改 `translate-cmd` 作为参数传 shell 的信任模型（`shell=True` 保留）。
- 不给 `tools/` 引入新第三方依赖（`rich` 已是 textual 传递依赖且已被
  `wiki.py` 使用；并发用 stdlib `concurrent.futures`）。
- 不做进程池（见 §三 否决理由）。

## 二、事实基线（已核对，带文件:行号）

| 事实 | 位置 |
|---|---|
| CLI 只捕 `WikiError`，其余裸奔 traceback | `tools/pack/cli.py:183-185`、`:196-207` |
| 错误输出无错误码，前缀三套风格（`tools.pack:` / `wiki:` / `wiki-translate:`） | `cli.py:147,160,184`；`wiki.py:315,379,383` |
| `zh_source` 读无保护 → issue 里的 `FileNotFoundError` | `wiki.py:618`；预扫描同样无保护 `wiki.py:411` |
| `_assert_unique` 抛裸 `ValueError` | `wiki.py:206-215` |
| `run_git` 不在 PATH → 裸 `FileNotFoundError`（无兜底） | `wiki.py:269-280` |
| 翻译串行：单 `for page in pages` + 阻塞 `translate_via_cmd` | `wiki.py:617`、`:665-667` |
| 进度条：单 overall task，rich `Progress` 手动 `start()`/`stop()` | `wiki.py:603-614`、`:660-662`、`:681,686`、`:687-689` |
| 失败永久行格式 `[k/N] <page> failed (X.Xs)`（测试断言依赖） | `wiki.py:672-676`；`tests/test_pack_wiki.py:586-609` |
| 全仓**零**池化并发先例（`concurrent.futures` / `ThreadPoolExecutor` 0 命中） | 全仓搜索 |
| `tools/translate` 是包（`tools/translate/cli.py` + `runner.py`），非单文件 | `tools/translate/__init__.py` |
| pyright strict、零诊断门禁，include `tools` | `pyproject.toml:100-107` |
| 既有测试用 `pytest.raises(ValueError)` 断言 target 冲突 | `tests/test_pack_wiki.py:67-70` |

## 三、方案选型

### 3.1 异常输出（需求 A）

**选定**：`tools/pack/errors.py` 新模块 + CLI 层单点兜底。

- `@dataclass`-free 的 `class Code(StrEnum)`：稳定错误码枚举（`WIKI_*` / `ICON_*` /
  `ROSTERS_*`），值即终端里印出的码，如 `WIKI_ZH_SOURCE_MISSING = "WIKI-0101"`。
- `class PackError(RuntimeError)`：携带 `code` + 可选 `hint`，`str(exc)` 即
  可读信息；`wiki.WikiError` 改为 `PackError` 的子类（名字保留，既有引用与
  `except wiki.WikiError` 全部继续可用）。
- CLI 层：`except PackError` → `error[CODE]: msg` + `hint:`；兜底
  `except Exception`（`# noqa: BLE001`，唯一允许的宽catch，且必须记日志）
  → `error[PKG-0001]`。`--debug` 时额外打印 traceback，且 traceback 始终经
  模块级 `logging` 记录（`logging.getLogger("yate.pack")`，DEBUG 级、无 handler
  时被 `lastResort` 阈值挡住，绝不进终端）。
- 库层不再 `print` 裸错误行：涉及的失败点改为抛 `PackError`（zh/en 读写、
  manifest 读写、git 缺失、target 冲突）；**翻译页失败仍降级为 `None` 不抛**
  （保持单页失败不中断整体的行为），但消息带错误码。

**否决的备选**：

| 备选 | 否决理由 |
|---|---|
| 复用 `yate.logs.tracing` | `tools/` 现状 0 处 logging，且 tracing 绑定 yate 应用生命周期与文件 handler，为开发工具引入耦合不划算；用 stdlib `logging` + `--debug` 即可满足 issue |
| 只在 `main()` 加 `except Exception` 兜底，不做码表 | issue 明确要求"对应的**错误码**和错误信息"；无码表则用户无从检索/文档化 |
| 让异常直接从库层 `sys.exit` | 已被 `wiki.py:101-108` docstring 明确禁止；测试直接调 `wiki.run()` 依赖返回码 |
| 把 `zh_source` 缺失当作"跳过该页" | `prune_orphan_pages` 会按本轮收集结果剪枝，静默跳过会连带删除 en 页/留下不一致状态；中止更安全 |

### 3.2 并行翻译（需求 B）

**选定**：线程池 + 显式分批 + 主线程归并。

```
prepare(串行, 现状逻辑不变)
  → 产出 _TranslationTask 列表（每批 ≤ BATCH_SIZE=10 页）
  → ThreadPoolExecutor(max_workers=resolve_jobs(jobs)) 提交批任务
  → 主线程 as_completed 消费：写 en 页 / 记 manifest / 更新进度 / 收集异常
```

- `BATCH_SIZE: Final[int] = 10`（issue 硬要求，直接常量 + 单测断言）。
- `resolve_jobs(jobs: int | None, *, cpu_count: int | None = None) -> int`：
  `None` → `cpu_count * 2`；显式值 clamp 到 `[1, cpu_count*2]`，超出时打印
  一次提示。**并发硬上限 = CPU×2 由此单点保证。**
- worker 只做"纯翻译"：`translate_via_cmd(text, cmd) -> str | None`，
  返回 `None` 表示失败；**BaseException（含 `KeyboardInterrupt`）必须作为值
  带回主线程再 raise**，否则 Future 永挂死、`Ctrl+C` 无法映射 130。
- 进度：仍用 rich `Progress`（单 overall task，total=pending 页数），
  `description` 实时改为 `running N · queued M · <正在跑的页名…>`，
  失败永久行沿用 `[k/N] <page> failed (X.Xs)`（不破坏既有断言）。
- 批次结果与页顺序解耦：完成顺序不影响 manifest（每页独立 key）、
  不影响剪枝集合（仍按本轮收集的 `pages`）。

**否决的备选**：

| 备选 | 否决理由 |
|---|---|
| `ProcessPoolExecutor` | 翻译是外部 CLI 子进程，进程池只增加 Windows spawn/重序列化开销；且需把 `WikiPage`/回调跨进程传参，复杂度不换收益 |
| asyncio + `to_thread` | 与 `concurrent.futures` 等价但本场景纯阻塞 IO，无需事件循环 |
| 每页一个 Future（不分批） | issue 明确"每份任务最多包含 10 个文档"；且每页一 Future 会让进度/状态行噪声爆炸 |
| 让 `--jobs` 无上限（用户可设任意值） | 违反 issue 的"最多 CPU×2"硬约束 |
| 成功也打永久行（149 页刷屏） | 终端可读性倒退；成功状态由进度行 + 汇总行体现 |

## 四、接口契约（子代理任务书的唯一依据）

### 4.1 `tools/pack/errors.py`（新增）

```python
class Code(StrEnum):
    """稳定错误码（终端输出与文档共用同一取值）。"""
    UNEXPECTED = "PKG-0001"
    GIT_MISSING = "PKG-0002"
    WIKI_TARGET_COLLISION = "WIKI-0101"
    WIKI_ZH_SOURCE_MISSING = "WIKI-0102"
    WIKI_SOURCE_UNREADABLE = "WIKI-0103"
    WIKI_MANIFEST_READ = "WIKI-0104"
    WIKI_MANIFEST_WRITE = "WIKI-0105"
    WIKI_PAGE_WRITE = "WIKI-0106"
    WIKI_TRANSLATE_FAILED = "WIKI-0201"
    WIKI_TRANSLATE_TIMEOUT = "WIKI-0202"
    WIKI_PRUNE_FAILED = "WIKI-0107"
    ICON_BUILD = "ICON-0301"
    ROSTERS_RENDER = "ROSTERS-0302"

class PackError(RuntimeError):
    def __init__(self, code: Code, message: str, *, hint: str | None = None) -> None: ...

def report(exc: BaseException, *, debug: bool = False) -> None:
    """把异常渲染成 ``error[CODE]: message``（+ hint）到 stderr，并记日志。"""
```

- `log = logging.getLogger("yate.pack")` 模块级；`report()` 内
  `log.debug("unhandled", exc_info=exc)`；`debug=True` 时额外
  `traceback.print_exception` 到 stderr。
- `PackError.__str__` 即 message（不含码，码由 `report()` 统一渲染）。

### 4.2 `tools/pack/wiki.py`（改）

- `class WikiError(PackError)`，默认 `code=Code.WIKI_SOURCE_UNREADABLE`？
  → 不行：既有 `raise WikiError(f"manifest read error: ...")` 位置参数形态要
  兼容。定：`WikiError(message, *, code=..., hint=...)`？统一为
  `WikiError(message: str, *, code: Code = Code.WIKI_SOURCE_UNREADABLE,
  hint: str | None = None)`，`str(exc)` = message。调用点显式传 code。
- `_assert_unique` 抛 `WikiError(..., code=Code.WIKI_TARGET_COLLISION)`。
- 新增：
  - `BATCH_SIZE: Final[int] = 10`
  - `def cpu_count() -> int`
  - `def resolve_jobs(jobs: int | None, *, cpu_count: int | None = None) -> int`
  - `def chunk_pages(items: Sequence[_T], size: int = BATCH_SIZE) -> list[list[_T]]`
    （泛型：`def chunk_pages[T](items: Sequence[T], size: int = BATCH_SIZE) -> list[list[T]]`）
  - `@dataclass(frozen=True) class _TranslationTask`：`pages: tuple[WikiPage, ...]`、
    `texts: tuple[str, ...]`，方法 `translate(translate_cmd) -> tuple[_PageResult, ...]`
    不放在 dataclass 里（保持"能用函数就不造类"），改为模块函数
    `def _run_task(task: _TranslationTask, translate_cmd: str) -> list[_PageOutcome]`
  - `@dataclass(frozen=True) class _PageOutcome`：`page`、`english: str | None`、
    `error: BaseException | None`、`elapsed: float`
- `run()` 新增关键字参数 `jobs: int | None = None`（默认 → 自动 CPU×2），
  其余签名与语义不变；`translate_via_cmd` 失败消息改为
  `error[WIKI-0201]: translate-cmd failed (rc=...): ...` / `[WIKI-0202]` 超时。
- 页面读写全部经 `_read_bytes(path, code)` / `_write_bytes(path, data)` /
  `_write_text(path, text, code)` 包装 → 抛 `WikiError`（对应码），消除裸 OSError。

### 4.3 `tools/pack/cli.py`（改）

- 全局选项 `--debug`（顶层 parser 与三个子命令共用 parents 技巧不必，
  直接加到顶层 + 各子命令？→ 只加顶层 `--debug`，但 argparse 顶层选项必须
  在子命令前写。定：三处各加 `--debug`（`icon`/`rosters`/`wiki` 都有），
  `_icon`/`_rosters`/`_wiki` 增加 `debug: bool` 参数，层数最少。
  → 简化：仅 `wiki` 子命令需要（长耗时 + issue 场景），`icon`/`rosters` 也统一
  打印 `error[CODE]` 但不带 `--debug`。定：`--debug` 加在 `wiki` 子命令上。
- `wiki` 新增 `--jobs N`（`type=int`、`default=None`、help 写明默认 = CPU×2、
  超过上限会被 clamp）。
- `_icon` / `_rosters`：`except (OSError, RuntimeError, ValueError)` →
  `except errors.PackError` + `except OSError`（映射到 `Code.ICON_BUILD` /
  `Code.ROSTERS_RENDER`），统一走 `errors.report()`。
- `main()`：
  ```python
  except KeyboardInterrupt: ... return 130
  except errors.PackError as exc: errors.report(exc, debug=debug); return 1
  except Exception as exc:  # noqa: BLE001 - CLI 边界兜底，绝不吐 traceback
      errors.report(exc, debug=debug); return 1
  ```
  `debug` 从 `getattr(args, "debug", False)` 取（顶层没有该属性时为 False）。

### 4.4 测试（新增两个文件，文件边界互斥）

- `tests/test_pack_wiki_errors.py`：错误码渲染 / `--debug` 才见 traceback /
  zh_source 消失 → `error[WIKI-0102]` 且退出码 1 且**无 traceback** /
  target 冲突 → `WikiError` / git 缺失 → `PKG-0002` / `_icon` `_rosters` 错误码。
- `tests/test_pack_wiki_parallel.py`：批次切分每批 ≤10 / `resolve_jobs` 默认与
  clamp / 并发峰值 ≤ 上限（用计数器）/ 实时状态行含 running/queued/失败行格式
  保持 / `KeyboardInterrupt` 在 worker 内抛出仍映射 130 / manifest 只在成功后写入。

## 五、分步实施计划

每步一个提交（`git-commit-message.md`，subject 全英文）。

| 波次 | 步骤 | 输入 | 改动文件 | 输出 | 验收命令（worktree 内执行） |
|---|---|---|---|---|---|
| 1 | 方案落盘 | issue + 调研 | `.trae/documents/pack-wiki-parallel-translate-plan.md` | 本文档 | — |
| 2 | 错误码体系 | §4.1 | `tools/pack/errors.py` | 码表 + `report()` | `.venv\Scripts\python.exe -m pyright tools/pack/errors.py` |
| 3 | wiki 层接入错误码 | §4.2 | `tools/pack/wiki.py` | `PackError` 化 + 并行执行器 | `.venv\Scripts\python.exe -m pyright tools/pack/wiki.py` |
| 4 | CLI 接入 + `--debug`/`--jobs` | §4.3 | `tools/pack/cli.py` | 统一输出 | `.venv\Scripts\python.exe -m pyright tools/pack/cli.py` |
| 5 | 既有测试适配 | 冲突断言从 `ValueError` 改 `WikiError` | `tests/test_pack_wiki.py` | 绿 | `.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py -q` |
| 6 | 新增测试（可并行，子代理 A/B） | §4.4 | `tests/test_pack_wiki_errors.py`、`tests/test_pack_wiki_parallel.py` | 绿 | `.venv\Scripts\python.exe -m pytest tests/ -q` |
| 7 | 审核（code-review-expert） | 全部改动 | — | 严重度清单 | pyright + pytest + 架构测试 |
| 8 | 收尾门禁 + 回填 + 提交 | — | 本文档回填 | 退出码 0 | 见 §六 |

波次 2-4 由主代理串行执行（同一功能面、互相依赖、文件重叠风险高）；
波次 6 的两个测试文件互不重叠，下发给 2 个子代理并行（`acceptEdits`）。

## 六、收尾门禁（主代理亲自跑，退出码必须 0）

```powershell
cd d:\Programming\yate-pack-wiki
.venv\Scripts\python.exe -m pyright yate\ tests\ tools\
.venv\Scripts\python.exe -m pytest tests\ -q
.venv\Scripts\python.exe -m pytest tests\test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests\ -q --cov=yate --cov-fail-under=75
```

冒烟（真库、只读语义安全）：

```powershell
.venv\Scripts\python.exe -m tools.pack wiki --target .tmp-smoke-wiki --check
.venv\Scripts\python.exe -m tools.pack wiki --target .tmp-smoke-wiki --jobs 4 --debug
```

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `Ctrl+C` 时线程池 worker 未结束导致退出延迟 | worker 捕获 `BaseException` 带回主线程；`shutdown(cancel_futures=True)`；文档注明在跑子进程随控制台事件终止 | 回落串行（`--jobs 1` 即串行路径） |
| rich 多线程刷新撕裂 | 只有主线程调 `progress.update/advance`（worker 只翻译） | — |
| 并行写盘竞态 | 每页目标路径唯一，主线程串行写盘 | — |
| 既有测试对 `ValueError` / 失败行格式的断言 | 明确列入波次 5 与 §4.4，`WikiError` 保留原名 | — |
| 错误码破坏下游脚本对 `tools.pack:` 前缀的依赖 | 前缀升级为 `error[CODE]:`，仓库内无依赖该前缀的脚本（已搜索确认） | — |

回滚路径：单分支 `enh/pack-wiki`，`git reset --hard eb64cf4` 或整分支删除。

## 八、流程图

```mermaid
flowchart TD
    A["main(argv)"] --> B["parse_args"]
    B --> C{"command"}
    C -->|wiki| D["_wiki -> wiki.run"]
    C -->|icon| E["_icon"]
    C -->|rosters| F["_rosters"]
    D --> G["collect_sources (目标冲突 -> WikiError/WIKI-0101)"]
    G --> H["prepare: 读 zh 写 zh -> 判定 fresh/stale/missing"]
    H --> I{"待翻译 > 0 ?"}
    I -->|否| M["剪枝 + 导航 + manifest + 汇总"]
    I -->|是| J["chunk_pages(size=10) -> resolve_jobs(CPU*2)"]
    J --> K["ThreadPoolExecutor 提交批任务"]
    K --> L["主线程 as_completed: 写 en / 记 manifest / 进度 / 失败行"]
    L --> M
    E --> Z["errors.report -> error[CODE]"]
    F --> Z
    D --> Z
    Z --> Y{"PackError ?"}
    Y -->|是| R["return 1"]
    Y -->|否 (兜底)| S["return 1 + no traceback"]

    style J fill:#bbdefb,color:#0d47a1
    style K fill:#bbdefb,color:#0d47a1
    style L fill:#c8e6c9,color:#1a5e20
    style Z fill:#fff3e0,color:#e65100
```