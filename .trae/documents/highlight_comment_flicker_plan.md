# 全语法高亮输入抖动一次性修复 实施计划

> **实施状态（2026-09-22 核对）：❌ 未实施。**
>
> - `yate/editor_syntax/regex_backend.py` 只有私有 `_tokenize_code_line()`
>   （第 451 行），**没有**公开的 `tokenize_line()` / pattern LRU 缓存；
>   `yate/editor_syntax/engine.py` 无 `tokenize_line_sync`；
>   `yate/editor_view/editor.py` 无 `_hl_line_snapshot` / `_hl_ml_states`
>   （Step 3 的行级快照 + 变化行 regex 替换 + multiline 向后传播）；tree-sitter
>   后端也没有 `_highlight_incremental`（Step 4 的增量 parse）。
> - 因此"变化行 regex 同步替换以消除**所有 token 类型**行尾边界抖动"未落地，
>   本文档描述的抖动按设计仍然存在。
> - 已实现的是其**前置计划** `typing_flicker_debounce_plan.md`
>   （0.08s 防抖 + 陈旧 token 复用，消除整屏脱色帧）。

## 问题

之前的 typing_flicker_debounce_plan 实现了陈旧 token 复用 + 0.08s debounce，消除了整屏脱色帧，但**所有语言、所有 token 类型在输入时都存在行尾局部抖动**：刚输入的 1-2 个字符在 debounce 窗口内短暂显示默认前景色，debounce 完成后才恢复正确颜色。注释因其常在行尾最容易被注意到，但关键字、字符串、数字、decorator、function 等任何在行尾的 token 都会抖动。

## Repository Research（调研结论）

### 抖动根因：陈旧 token 边界不匹配（架构层面，所有语言所有 token 通用）

[yate/editor_view/editor.py#L276-L304](yate/editor_view/editor.py#L276-L304) `_tokens_for` 在 `content_version` 落后时返回**上一版** token 列表。token 的 `start`/`end` 字符偏移是基于**旧内容**计算的。当在行尾输入字符：

```
版本 N:   def foo(x): return 42    (keyword "def": 0-3, number "42": 25-27)
版本 N+1: def foo(x): return 423   (keyword "def": 0-3, number "423": 25-28)
                                              ↑ 数字边界漂了
```

```
版本 N:   # hello world            (comment: 0-12)
版本 N+1: # helloX world           (comment: 0-13)
                                         ↑ 注释边界漂了
```

```
版本 N:   "hello"                  (string: 0-7)
版本 N+1: "helloX"                 (string: 0-8)
                                        ↑ 字符串边界漂了
```

任何 token（keyword / string / number / decorator / function / comment / 运算符...）只要在行尾，输入新字符都会落在旧 token 的 `end` 之后 → debounce 窗口内显示默认前景色 → 抖动。

### 为什么之前的陈旧 token 复用不够

之前的方案在编辑后返回旧 token 继续着色（避免整屏脱色帧），但旧 token 的 `end` 比实际行长短了 1（或多）个字符 → 新增字符超出 token 覆盖范围 → 显示默认前景色。Worker 在 0.08s + tokenize 耗时后返回精确 token → 颜色恢复 → 抖动一次。

快速连打时这个过程不断重复 → 持续闪烁。

### 所有语言都受影响

**Backend 选择**（[engine.py](yate/editor_syntax/engine.py)）：tree-sitter 优先，否则 regex。

| 语言 | Backend | 全量分词耗时 | 抖动严重度 |
|------|---------|-------------|-----------|
| python | tree-sitter | 3.4ms / 500 行 | 高（边界漂移 + 3.4ms 等待） |
| shell | tree-sitter | ~3ms / 500 行 | 高 |
| c/cpp/java/rust/go/js/ts | regex | ~44ms / 1000 行 | 中（边界漂移，全量分词也慢） |
| json/jsonc/markdown/toml/ini/yaml | regex | ~30ms / 1000 行 | 中 |

无论哪种 backend，**陈旧 token 边界漂移**是共同根因。

### 性能基线（实测）

| 路径 | 耗时 | 可同步跑？ |
|------|------|-----------|
| regex 单行 tokenize | **2.2 μs** | ✅ 完全可以 |
| regex 10 行 tokenize | ~20 μs | ✅ |
| regex 100 行 tokenize | ~0.5 ms | ✅ |
| regex 1000 行全量 tokenize | 44 ms | ❌ 不行（人眼可感知延迟） |
| regex 5000 行全量 tokenize | 199 ms | ❌ |
| tree-sitter 500 行全量 parse | 3.4 ms | ⚠️ 勉强（to_thread 调度 + parse） |
| tree-sitter 增量 parse（单字符改动） | **0.6 ms** | ⚠️ 接近可同步 |

**关键洞察**：regex 单行 tokenize 2.2μs 足够快，可以在 UI 线程同步执行。regex 全量 tokenize 在大文件上太慢（44ms/1k行），不能同步跑。因此**行级替换是唯一可行的同步精确着色方案**。

### 通用修复路径（覆盖所有 token 类型、所有语言）

regex backend 对**所有 15 种语言**都有完整 LangSpec 注册（含 line_comment、block_comment、triple_strings、keywords、builtins、constants、types）。因此：

1. **变化行**：regex 同步 tokenize 该行（2.2μs），边界精确匹配当前内容 → 所有 token 类型（keyword/string/number/decorator/function/comment/...）的边界都正确 → **消除所有 token 类型的行尾抖动**
2. **未变化行**：直接复用旧 token（快照比对），边界本来就对 → 零成本
3. **多行构造向后传播**：若变化行处于 multiline 状态（block comment / triple string），从变化行向后逐行 tokenize，直到状态归零 → 确保多行构造内所有行的 token 都正确
4. **完整重分词**：debounce 窗口后 worker 跑完整 tokenize（tree-sitter 精确 / regex 全量），替换回更精确的结果（tree-sitter 的 decorator/function.call 等 capture 比 regex 更精确）

### 代码位置

- 核心渲染路径：`EditorView.render_line` → `_syntax_kinds` → `_tokens_for`
- 高亮调度：`_schedule_highlight` / `_launch_highlight` / `_highlight_later`
- tree-sitter 全量 parse：[ts_backend/backend.py#L55-L74](yate/editor_syntax/ts_backend/backend.py#L55-L74) 每次 new Parser + `parser.parse(text)`
- regex 单行 tokenize：[regex_backend.py#L451-L499](yate/editor_syntax/regex_backend.py#L451-L499) `_tokenize_code_line`（含 multiline 状态机）

## Files and Modules

| 文件 | 改动 | 作用范围 |
|------|------|---------|
| `yate/editor_view/editor.py` | 行快照 + 变化行 regex 替换 + multiline 向后传播 | **所有语言，所有 token 类型** |
| `yate/editor_syntax/regex_backend.py` | 暴露 `tokenize_line` 公开函数 + pattern LRU 缓存 | **所有语言** |
| `yate/editor_syntax/engine.py` | 新增 `tokenize_line_sync` 入口 | **所有语言** |
| `yate/editor_syntax/ts_backend/backend.py` | 引入增量 parse 复用 Parser/Tree | **python, shell**（性能优化） |
| `tests/test_app_textual.py` | 新增多 token 类型抖动消除测试 | 测试覆盖 |

## Implementation Steps

### Step 1：regex backend 暴露单行 tokenize（regex_backend.py）

```python
import functools

# 新增 pattern LRU 缓存（避免每次 _code_line_pattern 重新编译）
@functools.lru_cache(maxsize=64)
def _get_code_pattern_cached(spec: LangSpec) -> re.Pattern[str]:
    return _code_line_pattern(spec)

# 新增公开函数
def tokenize_line(line: str, filetype: str, state: int = 0) -> tuple[list[Token], int]:
    """Tokenize one line synchronously via the regex backend.
    
    Microsecond-fast (2.2μs/line) — safe to call on the UI thread.
    Returns (tokens, new_multiline_state). Used by EditorView to replace
    stale tokens on changed rows during the debounce window, ensuring
    exact boundary alignment for ALL token types (keywords, strings,
    numbers, decorators, functions, comments, ...).
    """
    spec = lang_for(filetype)
    if spec is None:
        return [], state
    pattern = _get_code_pattern_cached(spec)
    return _tokenize_code_line(line, spec, pattern, state)
```

### Step 2：engine 层同步入口（engine.py）

```python
def tokenize_line_sync(line: str, filetype: str, multiline_state: int = 0) -> tuple[list[Token], int]:
    """Sync single-line tokenize via regex backend.
    
    Used by EditorView._tokens_for to replace stale tokens on changed rows.
    Always uses the regex backend (fast, synchronous, covers all 15 built-in
    languages) — tree-sitter precision comes later from the debounced worker.
    """
    return regex_backend.tokenize_line(line, filetype, multiline_state)
```

### Step 3：行级快照 + 变化行 regex 替换 + multiline 向后传播（editor.py）【核心】

在 `EditorView.__init__` 新增：

```python
self._hl_line_snapshot: Optional[tuple[str, ...]] = None
# regex 全量 tokenize 最后一次的 multiline 状态序列
# _hl_ml_states[r] = regex tokenize 第 r 行后的 multiline state
# 用于从变化行向后继续 tokenize，确保多行构造内所有行的 token 正确
self._hl_ml_states: Optional[tuple[int, ...]] = None
```

修改 `_tokens_for` 的 version 落后分支（**所有 token 类型抖动消除的核心逻辑**）：

```python
def _tokens_for(self, row: int) -> list[Token]:
    doc = self.doc
    buf = doc.buffer
    if (
        self._hl_tokens is None
        or self._hl_doc is not doc
        or self._hl_version != buf.content_version
        or self._hl_filetype != doc.filetype
    ):
        tokens = self._hl_tokens
        if tokens is None or self._hl_doc is not doc or self._hl_filetype != doc.filetype:
            self._schedule_highlight(0.0)
            return []
        # ── version 落后（编辑场景） ──
        self._schedule_highlight(self._HIGHLIGHT_DEBOUNCE_S)
        
        # 行数变化太大（>5 行增删）：退化为全量 stale 复用
        if (self._hl_line_snapshot is not None
            and abs(len(self._hl_line_snapshot) - buf.line_count) > 5):
            return tokens[row] if row < len(tokens) else []
        
        # 行数变化：快照不匹配，尝试重建快照
        if self._hl_line_snapshot is None or len(self._hl_line_snapshot) != buf.line_count:
            # 无有效快照，退化为旧 token + 排重 tokenize_line 缓存
            return self._row_tokens_via_regex(row, tokens)
        
        # ── 逐行快照比对 ──
        old_snap = self._hl_line_snapshot
        old_ml = self._hl_ml_states
        changed = [i for i in range(min(len(old_snap), buf.line_count))
                   if old_snap[i] != buf.lines[i]]
        if len(old_snap) != buf.line_count:
            changed.extend(range(min(len(old_snap), buf.line_count), buf.line_count))
        
        if not changed:
            # 快照没变化（只动了光标），直接复用旧 token
            return tokens[row] if row < len(tokens) else []
        
        # 只有变化行和后续可能被 multiline 状态影响的行需要重 tokenize
        # 从第一个变化行开始，向后 tokenize 直到 multiline 状态归零
        # （或到达文件末尾）
        first_changed = min(changed)
        start_state = old_ml[first_changed - 1] if (old_ml and first_changed > 0) else 0
        
        # 构建新的 tokens 列表：未变化行复用旧 token，变化行 + 后续受影响行用 regex
        new_tokens_list: list[list[Token]] = []
        current_state = start_state
        for r in range(buf.line_count):
            if r < first_changed:
                # 未变化行，复用旧 token
                new_tokens_list.append(tokens[r] if r < len(tokens) else [])
                # 但仍需更新 multiline state（用 regex 跑一行看状态）
                try:
                    _, current_state = tokenize_line_sync(buf.lines[r], doc.filetype, current_state)
                except Exception:
                    current_state = old_ml[r] if old_ml and r < len(old_ml) else 0
            else:
                # 变化行或后续行，regex 同步 tokenize
                try:
                    line_tokens, current_state = tokenize_line_sync(
                        buf.lines[r], doc.filetype, current_state
                    )
                    new_tokens_list.append(line_tokens)
                except Exception:
                    new_tokens_list.append(tokens[r] if r < len(tokens) else [])
                # multiline 状态归零后，后续行复用旧 token
                if current_state == 0 and r > first_changed:
                    # 从 r+1 开始可以复用旧 token
                    for rest in range(r + 1, buf.line_count):
                        new_tokens_list.append(tokens[rest] if rest < len(tokens) else [])
                    break
        
        # 缓存这份重建的 tokens（debounce 窗口内后续 render 复用）
        self._hl_tokens = new_tokens_list
        self._hl_doc = doc
        self._hl_version = buf.content_version
        self._hl_filetype = doc.filetype
        # 更新快照
        self._hl_line_snapshot = tuple(buf.lines)
        # 同步更新 multiline 状态序列
        new_ml = []
        s = 0
        for r in range(buf.line_count):
            if r < len(new_tokens_list):
                try:
                    _, s = tokenize_line_sync(buf.lines[r], doc.filetype, s)
                except Exception:
                    pass
            new_ml.append(s)
        self._hl_ml_states = tuple(new_ml)
        
        return new_tokens_list[row]
    
    # 完全有效：直接返回
    return self._hl_tokens[row] if row < len(self._hl_tokens) else []
```

修改 `_highlight_later`，tokenize 完成后保存快照和 multiline 状态序列：

```python
self._hl_line_snapshot = tuple(buf.lines)
# 用 regex 跑一遍拿到完整的 multiline 状态序列（2.2μs × N 行 ≈ 可接受）
new_ml = []
s = 0
for line in buf.lines:
    try:
        _, s = tokenize_line_sync(line, doc.filetype, s)
    except Exception:
        pass
    new_ml.append(s)
self._hl_ml_states = tuple(new_ml)
self._hl_tokens = tokens
self._hl_doc = doc
self._hl_version = version
self._hl_filetype = filetype
```

doc/filetype 切换时清空 `_hl_line_snapshot = _hl_ml_states = None`。

### Step 4：tree-sitter 增量 parse（ts_backend/backend.py）【python/shell 性能优化】

这是**可选的性能优化**——行级 regex 替换已消除所有抖动，增量 parse 仅让 debounce 窗口内 worker 完成更快（3.4ms → 0.6ms）。

在 `EditorView` 新增：

```python
self._hl_ts_parser: Optional[Any] = None
self._hl_ts_tree: Optional[Any] = None
```

在 `ts_backend/backend.py` 新增增量入口（复用 Parser + 传递 old_tree）：

```python
def _highlight_incremental(
    lines: list[str], loaded: LoadedLanguage,
    parser: Optional[Any] = None, old_tree: Optional[Any] = None,
) -> tuple[list[list[Token]], Any, Any]:
    """Incremental tree-sitter parse. Returns (tokens, parser, tree)."""
    ts = tree_sitter()
    if ts is None:
        return [[] for _ in lines], parser, old_tree
    if parser is None:
        parser = ts.Parser(loaded.language)
    text = "\n".join(lines)
    new_tree = parser.parse(text.encode("utf-8"), old_tree=old_tree)
    # ... query + token 映射逻辑与现有 _highlight 完全相同 ...
    return result, parser, new_tree
```

`_highlight_later` 中调用增量版本并保存 Parser/Tree。doc/filetype 切换时清空。

### Step 5：测试补充（test_app_textual.py）

新增测试（覆盖多种 token 类型、多种语言）：

1. **test_no_flicker_keyword_edit**：`.py` 文件，在 `def foo():` 的 `def` 中间插入 `X` → `deXf foo():`，断言 keyword token 边界即时更新（regex 行级替换），无脱色帧。
2. **test_no_flicker_string_edit**：`.py` 文件，在 `"hello"` 的末尾引号前输入 `X` → `"helloX"`，断言 string token 边界即时更新。
3. **test_no_flicker_number_edit**：`.py` 文件，在 `42` 后输入 `3` → `423`，断言 number token 边界即时更新。
4. **test_no_flicker_block_comment_c_edit**：`.c` 文件，在 `/* comment */` 的 `*/` 前输入 `X` → `/* comment X*/`，断言 block comment token 边界即时更新。
5. **test_no_flicker_decorator_edit**：`.py` 文件，在 `@property` 的末尾输入 `X` → `@propertyX`，断言 decorator token 即时更新。
6. **test_same_line_reuses_old_tokens**：光标移动不 bump version，断言快照比对直接命中旧 tokens。

## Dependencies and Considerations

- **行级 regex 替换的覆盖率**：regex LangSpec 覆盖全部 15 种语言的所有高频 token 类型（注释、字符串、数字、关键字、常量、类型、函数、decorator、运算符），足够消除所有 token 类型的行尾抖动。tree-sitter 精确结果（更细的 capture 如 `function.call`、`attribute.builtin`）在 debounce 窗口后替换回来。
- **多行状态传播**：从第一个变化行向后 tokenize，直到 multiline 状态归零。对于 block comment / triple-quote，这确保多行构造内所有行的 token 都正确。2.2μs/行，100 行 block comment = 220μs，可接受。
- **行数剧变**：>5 行增删时快照行数不匹配，退化为全量 stale 复用——但 worker 很快完成（增量 parse 0.6ms / regex 全量虽慢但有 debounce），边界漂移仅短暂出现。
- **增量 parse 降级**：blocked 的 tree-sitter（0.26.x）自动退化为 regex backend，行级 regex 替换仍工作。
- **debounce 常量**：0.08s 不变。行级替换消除了边界漂移，增量 parse 缩短了 worker 等待时间。
- **内存**：`_hl_line_snapshot` ≈ 500 行 × 40 字符 = 20KB；`_hl_ml_states` ≈ 500 整数 = 2KB；Parser/Tree 由 C 分配，Python 侧仅持有引用。
- **`_hl_ml_states` 重建开销**：tokenize 完成后用 regex 跑一遍全量 2.2μs × N 行 ≈ 1ms/500行，可接受。

## Validation

1. `python -m pytest tests` 全量通过
2. pyright strict 零诊断
3. **多 token 类型手动验证**（.py 文件，每种 10 秒）：
   - keyword：`def|foo():` 在 `def` 中间输入 → keyword 边界立即更新
   - string：`"hello|"` 在引号前输入 → string 边界立即更新
   - number：`42|` 在后面输入 → number 边界立即更新
   - comment：`# hello|` 在中间输入 → comment 边界立即更新
   - decorator：`@property|` 在末尾输入 → decorator 边界立即更新
   - block comment：C 的 `/* hello|*/` → block comment 边界立即更新
   - multi-line block comment：在中间行输入，确认后续行 token 正确
4. **多语言手动验证**：.py（ts）、.c（regex）、.rs（regex）、.sh（ts）、.md（regex）、.jsonc（regex）
5. **headless 截图验证**（可选）：用 textual-pilot-smoke 在 pilot 模式下对编辑前后帧做 SVG diff

## Risks

| 风险 | 处理 |
|------|------|
| `_tokens_for` version 落后分支逻辑复杂度增加 | 提取为 `_rebuild_tokens_on_edit(row)` 独立方法 + 充分测试 |
| multiline 向后传播在超长大文件上（>10k 行）仍慢 | 行数剧变时已退化为 stale 复用；行级编辑只影响附近几十行 |
| `_hl_ml_states` 用 regex 全量跑 ≈ 1ms/500行 | tokenize 完成后跑一次，可接受；后续 render 复用 |
| regex 重 tokenize 覆盖了 worker 还没完成的结果 | worker 完成后会覆盖 `_hl_tokens`，下次 render 用更精确的 tree-sitter 结果 |
| 未知 filetype 无 regex LangSpec | `lang_for()` 返回 None 时安全降级为旧 token |
| tree-sitter Parser/Tree 泄漏 | EditorView 销毁时 GC 清理；doc/filetype 切换时显式置 None |
