# plan-b：中栏万级条目增量刷新（R1 + m11）

依赖：plan-a 完成（改动落在 `filemgr/screen.py` / `filemgr/model.py` 新布局）。

## 背景（坐标为 plan-a 后的 screen.py 行号，即迁移前 filemgr.py 行号）

- `_reload`（:274-293）：`list_dir` → `filter_entries` → **逐 entry `stat_entry`** → `sort_entries` → 渲染。万级目录每次全量 scandir + N 次 stat + sort。
- `_refilter`（:295-308）：已免二次 stat（仅对新 entry 补 stat），不重复处理。
- m11（评审记录 `.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一）：`_render_dir_preview`（:424-441，触发点 `on_list_view_highlighted` :549-554）每次高亮目录都对高亮目录全量 `list_dir`。
- 现有可参照缓存：`PreviewCache`（`yate/editor_view/preview.py:174`，FIFO + mtime/size 复验）；`_child_counts` setdefault 缓存已在（:174，`action_refresh` :760-764 清空）。

## 设计（裁决 Q1-Q3 已定）

### b-1 目录列表缓存

`FileManagerScreen` 增加实例状态：

```python
self._dir_cache: dict[tuple[Path, bool], DirListing] = {}
```

- 键：`(path, show_hidden)`（toggle_hidden 改 listing，故入键；裁决定案）。
- 值 `DirListing`（model 层轻量记录）：`stamp: int`（目录 `mtime_ns`）、`entries: list[Entry]`（`workspace.list_dir` 原始结果，未过滤未排序）。
- 新鲜度：命中键后 `path.stat().st_mtime_ns` 复验 == `stamp` 才复用；不等则重 `list_dir` 并回填。FIFO 容量 **16**（对齐 `PREVIEW_CACHE_SIZE`，Q2）。
- 复用方法（screen 内私有）：`_list_dir_cached(path: Path) -> list[Entry]`。
- 接入点：
  - `_reload`：`self._all = self._list_dir_cached(self._cwd)`；`self._cwd is None`（盘符虚拟层）走 `workspace.list_drives()` 不缓存（其 docstring 自述探测廉价，维持现状）。
  - `_refilter` 不接入（它不 list_dir，且 `_all` 已在手）。
- **清缓存点**（任何 mutation 必清，红线）：
  - `action_refresh`（:760-764，`r` 强刷）：与 `_child_counts` 一起清（Q3：`r` 同时强刷目录预览）。
  - 所有改文件系统后走 `workspace.invalidate()` + `_reload` 的 action（create/rename/delete/paste/mkdir/toggle_hidden 等）：执行前调 `_drop_dir_cache()`。执行时以 grep 枚举 screen.py 内全部 mutation action 清单并落盘本文档执行记录节，逐一接线。
- 排序/过滤仍为 model 层纯函数（`filter_entries` / `sort_entries`），缓存只覆盖"目录未变 → 跳过全量 scandir + 逐 entry stat_entry"；stat 复用策略：`_stats` 现字典在条目未变时保持（`_reload` 里仅对 `self._all` 中 `path not in self._stats` 的 entry 补 stat，语义等同 `_refilter` 的 setdefault 补法；`action_refresh` 清缓存时连 `_stats` 一起清，保持强刷语义）。
  - 注意甄别：`_stats` 按 path 缓存后，同名覆盖（rename 到同 path）由 mutation 清缓存兜底；mtime 变化但路径不变的情形（文件被外部修改）不在本缓存职责内（`_stats` 只影响排序/装饰列，现状 `r` 强刷路径不变）。

### b-2 m11：目录预览记忆化

`_render_dir_preview`（:424-441）：

- 不再直接 `self.workspace.list_dir(path)`；改 `_list_dir_cached(path)`（同一缓存，同一键含 `show_hidden`）。
- 渲染 `Text` **每次**从缓存 entries 重排（Q2：主题切换不陈旧）；`_DIR_PREVIEW_CAP` 截断逻辑不变。
- `action_refresh` 清缓存后下一次高亮自然重扫（Q3：mtime 复验 + `r` 强刷足够，不做 inotify）。

### b-3 测试

`tests/test_filemgr.py` 新增（沿用本地 `_Host` + `_screen` 宿主）：

1. 目录未变时第二次 `_reload` 不再触发 `workspace.list_dir`（host 计数桩）。
2. 目录 mtime 变化后 `_reload` 重扫。
3. `action_refresh` 清缓存：清后 `_list_dir_cached` 重扫（并保留对 `_child_counts`/`_stats` 清空的既有断言）。
4. mutation action（至少 rename/delete 各一）后缓存已清。
5. m11：连续两次高亮同一目录只 list_dir 一次；`r` 后再高亮重扫。
6. `show_hidden` 切换命中不同键（两键各自缓存）。

## 验收

- 全量门禁五项绿（见总纲）；架构 37+ 用例全绿。
- **性能实测**（不适用先红后绿）：临时脚本（放 worktree 外或测后删除，不入库）构造 `>=10000` 子项目录，计时：
  1. `_reload` 全量一次（迁移前 master vs 本分支，缓存冷/热各一组）；
  2. 连续 `j/k` 高亮目录条目时 `_render_dir_preview` 单键耗时（迁移前 master vs 本分支）。
  - 验收断言：热路径下每键不再全量 `scandir + stat + sort`（计数桩证明 `list_dir` 调用次数为 0）。
  - 实测数字回填本文档「执行记录」节。
- 可见行为零变化：排序、过滤、隐藏开关、预览渲染、`r` 强刷语义与迁移前一致（既有全量测试回归背书）。

## 回滚

单提交 `perf(filemgr): incremental directory refresh with mtime-keyed cache`；失败 reset 到 plan-a 提交点。
