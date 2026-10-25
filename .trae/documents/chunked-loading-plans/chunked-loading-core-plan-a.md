# chunked-loading-core-plan-a（wave-1：L0 分块机件）

## 输入

主计划 [../chunked-loading-plan.md](../chunked-loading-plan.md) §二/§三/§四。本计划是 wave-2 两个子计划的共同依赖。

## 目标

新增 L0 叶子模块 `yate/editor_core/chunked.py`：文件分块读取 + 块缓存（LRU）+ 文本行前缀和索引，供文本分段（plan-b）与 hex 分段（plan-c）共同消费。纯 stdlib，不 import 任何上层。

## 独占文件清单

只改这两个文件，不要动其它任何文件：

- `yate/editor_core/chunked.py`（新增）
- `tests/test_chunked.py`（新增）

## 具体设计

### `ChunkedTextFile`

```python
CHUNK_SIZE: int = 262_144          # 256 KiB target size per text chunk
SCAN_BATCH_CHUNKS: int = 4         # chunks per scan_next_batch() call

class ChunkedFallback(Exception):
    """File shape cannot be chunk-aligned (CR-only line endings)."""

class ChunkedTextFile:
    # __init__(path: Path, chunk_size: int = CHUNK_SIZE) -> None
    #   - stat(): total_bytes, chunk_count = ceil(total / chunk_size) lower bound
    #   - encoding probe: read first 64 KiB, reuse Document._decode semantics
    #     (BOM -> utf-8-sig -> utf-8 -> locale -> cp1252 -> replace); store
    #     encoding + strip BOM offset for the first chunk
    #   - CR-only guard: first block has b"\r" and no b"\n" -> raise ChunkedFallback
    # metadata (guarded by threading.Lock; scan appends prefix only)
    #   total_bytes: int / scanned_chunks: int / total_lines: int
    #   chunk_start_rows: list[int]  # prefix sums: first row of each chunk
    # scanning (called from a worker thread)
    #   scan_next_batch(batches: int = SCAN_BATCH_CHUNKS) -> bool  # False = done
    # rows (called from the UI thread; loads chunks on demand)
    #   row_count() -> int
    #   chunk_for_row(row: int) -> int          # O(log n) bisect over prefix sums
    #   read_rows(start: int, count: int) -> list[str]   # fills chunk cache
    # internals
    #   _read_chunk_lines(index: int) -> list[str]
    #   - block start = chunk end offsets[index] (chunk 0 = 0 or BOM offset)
    #   - read up to chunk_size bytes; if the last byte is not b"\n" and not
    #     EOF, keep reading until the next b"\n" (chunk boundary == row
    #     boundary; a line longer than chunk_size forms an oversized chunk)
    #   - decode(errors="replace"); normalize trailing "\r\n"/"\r" per row
    #   - LRU cache: dict[int, list[str]] + deque order, max MAX_CACHED_CHUNKS
```

LRU 上限常量：

```python
MAX_CACHED_CHUNKS: int = 32        # ~8 MiB text / 2 MiB binary resident cap
```

### `ChunkedBinaryFile`

```python
HEX_BLOCK_SIZE: int = 65_536       # 64 KiB blocks for the hex view

class ChunkedBinaryFile:
    # __init__(path: Path, size: int, mtime: float, block_size: int = HEX_BLOCK_SIZE)
    # read(offset: int, length: int) -> bytes
    #   - block-aligned reads through the LRU cache; dirty edits applied on top
    #   - out-of-range raises ValueError (mirrors parse_hex_address semantics)
    # apply_edit(offset: int, byte: int) -> None      # records into _dirty
    # dirty_edits() -> dict[int, int]                 # offset -> new byte
    # clear_edits(offsets: Iterable[int]) -> None     # after successful save
    # blocks_loaded() -> int                          # test/observability hook
```

线程纪律：`ChunkedTextFile.scan_next_batch` 由 worker 线程调用、其余由 UI 线程调用；`threading.Lock` 保护索引前缀列表的追加与读取。行内容缓存只在 `read_rows`/`_read_chunk_lines`（UI 线程）路径触碰，无需锁。

## 需要新增的测试（tests/test_chunked.py）

构造辅助：tmp_path 下生成确定性内容文件；用小 `chunk_size`（如 64）触发多块。每个用例三要素齐全：

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_chunked_text_reads_rows_across_chunks` | 1000 行文本，chunk_size=64（多块） | `read_rows(0, row_count())` 拼接 | 与原文 `split("\n")` 全等（含末行无换行形态） |
| `test_chunked_text_scan_progression` | 同上 | 循环 `scan_next_batch()` 至 False | `scanned_chunks` 单调增至块数；`total_lines` 终值 == 行数；`chunk_start_rows` 前缀和首项 0 |
| `test_chunked_text_lru_evicts_old_chunks` | chunk_size=64，读 > MAX_CACHED_CHUNKS 块 | 触发淘汰后重读旧块 | 内容仍正确；缓存条目数 ≤ MAX_CACHED_CHUNKS |
| `test_chunked_text_handles_crlf` | CRLF 文件（\r\n 行尾） | read_rows | 行内容不含 `\r`；块边界落在 CRLF 行之间不劈开 |
| `test_chunked_text_strips_utf8_bom` | 带 BOM 的 UTF-8 文件 | read_rows(0,1) + encoding | 首行无 U+FEFF；encoding == "utf-8-sig" |
| `test_chunked_text_falls_back_on_cr_only` | 仅 `\r` 行尾文件 | 构造 ChunkedTextFile | raises ChunkedFallback |
| `test_chunked_text_chunk_for_row_bisect` | 扫描完成后 | chunk_for_row(0 / 中间 / 末行 / 越界) | 返回块索引单调不降；越界负行 raise/clamp 语义与 TextBuffer.line 一致 |
| `test_chunked_text_partial_final_chunk` | 文件尾非 \n 结尾 | read_rows 至末行 | 末行内容正确、行数正确 |
| `test_chunked_binary_read_random_offsets` | 1 KiB 确定性 bytes，block_size=256 | 多个随机 offset/length read | 与原 bytes 切片全等 |
| `test_chunked_binary_dirty_edits_applied_on_read` | 同上 | apply_edit 两处后 read | 读出字节反映编辑；dirty_edits() 记录正确 |
| `test_chunked_binary_block_cache_limits_reads` | 同上 | 同一区域读两次，monkeypatch 计数底层 `read` | 第二次零底层读取（命中缓存） |
| `test_chunked_binary_out_of_range_raises` | size 已知 | read(size+1, 1) | raises ValueError |

## 验收命令（执行者跑）

```powershell
Set-Location D:\Programming\yate-chunked-loading
.venv\Scripts\python.exe -m pytest tests/test_chunked.py -q
.venv\Scripts\python.exe -m pyright yate/editor_core/chunked.py tests/test_chunked.py
```

通过判定：两条退出码 0，pyright 零诊断。

## 风险与回滚

- 新增文件，无回归面；回滚 = 删除两文件。
- 编码风格按 `python-coding-style.md`：`from __future__ import annotations`、完整注解、散文式 docstring（英文）、无 Any / 无 print / 日志不经此模块（纯数据机件，无日志需求；如需则 `tracing.get_logger` + 惰性 % 占位）。
