# perf-audit-fixes-leaf-packs-plan-c（成员 A3：P15 + P19 + P20）

总纲：[overview.md](overview.md)。证据来源：[评审记录](../../reviews/2026-10-26-perf-audit.md) §Minor P15/P19/P20。

## 一、目标

1. **P15（minor）**：tree-sitter 后端每轮高亮把整文档编码两遍（`"\n".join(lines)`
   后整体 encode，又逐行 encode），`ts.Parser` 每次调用重建；`_to_char` 每个捕获
   端点从行首前缀解码 O(byte_col)；
2. **P19（minor）**：Lua 捆绑 API 库每扩展重复读盘 + 重编译（`loader.py:188-195`
   每扩展各调一次 `lua_api_library_source()` / `lua_module_sources()`，后者读
   `library.py:36-75` 无缓存）；
3. **P20（minor）**：`workspace.walk_files`（workspace.py:240-301）每次全树重遍历、
   每条目一次 `is_dir()` stat，ctrl+p 与全项目查找各自重复。

## 二、独占文件（只许改这些；清单外一律停下上报）

产品码：
- `yate/editor_syntax/ts_backend/backend.py`
- `yate/services/extensions/lua/library.py`
- `yate/services/extensions/loader.py`
- `yate/services/workspace.py`

关联测试（可改/可新增用例）：
- `tests/test_ts_backend.py`、`tests/test_syntax_engine.py`、
  `tests/test_extensions.py`、`tests/test_lua_extensions.py`、
  `tests/test_workspace_filter.py`、`tests/test_app_palette.py`

## 三、实施要点

### P15（backend.py）
1. 行字节只编码一次：`line_bytes = [line.encode("utf-8") for line in lines]`，
   解析输入用 `b"\n".join(line_bytes)`（替代 `text.encode`），下游复用同一列表；
2. Parser 缓存：模块级 `dict`（键 = 已加载语言对象/语言名），`get_parser(language)`
   复用；注意 py-tree-sitter 的 Parser 是否可跨 parse 复用——可复用则缓存 Parser，
   不可则缓存 language 并复用单例 Parser（按实测 API 定，不猜测）；
3. `_to_char`（backend.py:139-143）：对同一行的多个端点排序后做间隙增量解码
   （维护"已解码字符数 ↔ 字节偏移"游标），或为每行建一次字节↔字符偏移表
   （行内端点多时更优）；实现取简单正确者优先，两方案均可。

### P19（library.py + loader.py）
1. `lua_api_library_source()` 与 `lua_module_sources()` 结果加 `functools.lru_cache`
   （捆绑资源只读不变；返回值注意不可变性——返回的 dict/list 若被调用方修改会污染
   缓存，按现状调用方式确认无修改，或返回拷贝/`MappingProxyType`）；
2. runtime 仍按扩展各建（隔离设计不动）。

### P20（workspace.py）
1. `walk_files` 增加 TTL 缓存：模块级或 Workspace 实例级（按现有调用方结构选——
   调用方经 workspace 实例则实例级更干净），缓存 `(expires_at, files)`；
   TTL 常量默认 5s（模块级命名常量）；
2. 暴露 `invalidate()`（或等价方法）；palette / find_replace 调用方不强制改
   （它们自动受益于缓存）；若调用方语义需要"打开面板即刷新"，可由调用方在打开时
   先 `invalidate()`——保持行为可预期，登记选择；
3. limit 逻辑（默认 5000）保持。

## 四、验收命令（worktree 内）

```powershell
Set-Location d:\Programming\yate-perf-audit
.\.venv\Scripts\python.exe -m pyright yate/
.\.venv\Scripts\python.exe -m pytest tests/test_ts_backend.py tests/test_syntax_engine.py tests/test_extensions.py tests/test_lua_extensions.py tests/test_workspace_filter.py tests/test_app_palette.py -q
```

补用例：P15 高亮结果与改前一致（编码路径变化零行为差异）；P20 TTL 内二次调用
不重扫（monkeypatch 时间或计数 stat）。

## 五、报告格式

改动清单 → 命令与结果摘要 → 偏离与未解决项。

## 六、风险与回滚

py-tree-sitter API 差异（Parser 复用语义）——按实测 API 决定缓存对象，不猜测；
TTL 缓存 5s 窗口内新文件不可见——已在总纲登记为可接受。
回滚：本成员产物单独提交，可独立 revert。
