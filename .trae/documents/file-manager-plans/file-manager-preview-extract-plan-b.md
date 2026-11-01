# plan-b：预览管线提取共享模块 preview.py（wave-1）

## 输入
总纲 §三（预览复用裁决）。事实基线（yate/editor_view/palette.py，711 行）：
`_PreviewData`（54-64，frozen dataclass）、`PREVIEW_CACHE_SIZE = 16`（68）、
`PreviewLog(RichLog)`（116-142，can_focus=False + on_mount apply_slim_scrollbars +
theme.attach）、`_cache_current`（382-388）、`_update_preview`（390-416，
worker group="palette-preview" exclusive）、`_load_preview`（428-484，
线程侧：超大/二进制 note、islice 截断、tokenize_document）、`_load_preview_worker`
（497-511）、`_cache_store`（486-495 FIFO）。`FilePreviewConfig` 在 `yate/config.py:113-120`
（enable/max_lines=2000/max_size=1MiB）。

## 目标
把 palette 的文件预览管线提取为 L2 共享模块 `editor_view/preview.py`，
供 palette 与 filemgr 复用（组合优于复制）。**纯搬运 + 改名 + 最小适配**，
行为逐字节等价；palette.py 行为不变，`test_palette_preview.py` 17 用例全绿即验收。

## 独占文件清单
- `yate/editor_view/preview.py`（新建）
- `yate/editor_view/palette.py`（仅改 import 与引用，删除被迁走的定义）
- `tests/test_palette_preview.py`（回归跑，不改断言；仅当引用私有名必须跟随改名）

## 具体修改

### preview.py 新模块结构
```python
"""Shared file preview pipeline (worker-loaded lines, tokens, cache)."""
from __future__ import annotations
# ... 既有 palette 头部同款导入集（config/engine/tokens/tracing/theme/scrollbars/rich/textual）

PREVIEW_CACHE_SIZE: int = 16          # 原 palette.py:68

@dataclass(frozen=True)
class PreviewData:                    # 原 _PreviewData 去下划线（L2 包内共享）
    path: Path
    lines: list[str]
    tokens: list[list[Token]]
    mtime_ns: int
    size: int
    truncated: bool
    note: str | None

class PreviewLog(RichLog):            # 原 palette.py:116-142 原样迁移
    """Read-only preview pane (source lines, syntax highlighted). ..."""

def load_preview(path: Path, cfg: FilePreviewConfig) -> PreviewData:
    """Thread-side loader（原 _load_preview 428-484 静态逻辑）。"""

def load_preview_worker(path: Path, cfg: FilePreviewConfig) -> PreviewData:
    """Worker entry（原 _load_preview_worker 497-511）。"""

class PreviewCache:                   # 新类：原 _cache_current/_cache_store 逻辑对象化
    """FIFO preview cache with mtime+size staleness revalidation."""
    def __init__(self, capacity: int = PREVIEW_CACHE_SIZE) -> None: ...
    def get(self, path: Path, mtime_ns: int, size: int) -> PreviewData | None: ...
    def store(self, data: PreviewData) -> None: ...
    def clear(self) -> None: ...
```

### palette.py 适配（最小 diff）
1. 删除 `_PreviewData` / `PREVIEW_CACHE_SIZE` / `PreviewLog` / `_load_preview` /
   `_load_preview_worker` 定义体；
2. 顶部改：
   `from yate.editor_view.preview import PreviewData, PreviewCache, PreviewLog, load_preview_worker`；
3. `PaletteScreen` 实例属性 `self._preview_cache: dict[...]` →
   `self._preview_cache = PreviewCache()`；`_cache_current` 调用点改
   `self._preview_cache.get(path, mtime_ns, size)`；`_cache_store` 改 `.store(...)`；
   `_load_preview(partial)` 调用点改 `load_preview_worker`；
4. **保留** `_update_preview`（390-416）——它是 UI 侧编排（worker 派发 + 渲染），
   依赖 self 的 widget 状态，不属共享管线；
5. 绝不改 `fuzzy_match` / 索引 worker / 结果列表逻辑。

### 命名与守卫自查
- `PreviewData` 无下划线前缀 → 非"开放 API"三面（纯 L2 包内消费），合规；
- preview.py 含 `RichLog` 子类 → R15：`PreviewLog` 已在类体调
  `apply_slim_scrollbars` + `apply_scrollbar_theme`（原样迁移即满足守卫 #37）；
- 注释/docstring 全英文（misc-rules §四）。

## 新增测试
不新增文件；`tests/test_palette_preview.py` 17 用例作等价性回归（引用
`_PreviewData` 等私有名的地方跟随改为 `PreviewData`，断言不变）。
补 2 条 PreviewCache 单元用例（追加到同文件）：

| 用例 | 操作 | 断言 |
|---|---|---|
| `test_preview_cache_fifo_evicts_oldest` | capacity=2 连续 store 3 条 | 第 1 条 get 返回 None，后两条命中 |
| `test_preview_cache_stale_entry_rejected_by_mtime` | store 后以新 mtime_ns get | 返回 None |

## 验收命令
```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/preview.py yate/editor_view/palette.py tests/test_palette_preview.py
.venv\Scripts\python.exe -m pytest tests/test_palette_preview.py tests/test_app_palette.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 风险与回滚
- 循环导入：preview.py 不得 import palette（单向：palette → preview）；
- test_app_palette.py 涉及后台索引 worker，时序敏感——按 §4.7 用 wait_until 的
  既有断言形态跑 `-n auto`，flake 时 `-n 1` 复核修根因；
- 回滚：本子计划独立成笔提交，revert 即还原。
