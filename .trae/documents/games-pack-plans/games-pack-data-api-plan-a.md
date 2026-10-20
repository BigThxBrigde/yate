# A 波：Python 管道（数据存储 + `api.data` + 共享 Lua 模块预载）

上级：[overview.md](overview.md) ｜ 主计划：[../games-pack-plan.md](../games-pack-plan.md)

## 一、目标与非目标

**目标**

1. 新增 L0 叶子模块 `yate/services/data_store.py`：`~/.yate/data` 下的受控文本读写（路径安全 + 原子写）。
2. 新增 `api.data` 桥（`DataExtensionBridge`），并在 Lua 面暴露 `yate.data.read/write/remove/list`。
3. 让 `yate/extensions/lib/*.lua` 以 `package.preload` 方式被每个 Lua runtime 预载，
   使游戏文件能 `require("game_engine")` 复用同一份源码。
4. 上述三件事全部有单测，且 `tests/test_lua_defs.py` 的三面同步守卫仍然成立。

**非目标**

- 不做目录级 API（不暴露绝对路径、不暴露 `~`、不允许 `..`）。
- 不引入新依赖（不加 JSON 库、不加 `portalocker`）。
- 不改 canvas 渲染契约。

## 二、调研事实

| 事实 | 证据 |
|---|---|
| Lua 扩展各自独立 runtime，共享代码只能经 `package.preload` | `yate/services/extensions/lua/runtime.py:85-97` |
| 现有 API 无任何文件读写；`yate.shell` 是唯一进程通道 | `yate/services/extensions/api.py:520-535` |
| `~/.yate/data` 常量已在 `logs.py`（只服务日志/crash） | `yate/logs.py:79-80` |
| `_yate.lua` / `_yate.d.lua` / Python 面必须逐函数同步 | `tests/test_lua_defs.py:33-88` |
| `loader._load_lua` 是 runtime 的唯一创建点 | `yate/services/extensions/loader.py:184-189` |
| `services/*` 属 L0，禁 import `editor_view` | `architecture-boundaries.md` R4 |
| bundled 目录整体打包（新增 `lib/` 自动随包） | `pack/_common.py:179-183` |

## 三、A1：`yate/services/data_store.py`（新）

模块 docstring（英文）说明：写入面只覆盖 `~/.yate/data`；`logs.py` 的 crash/trace 文件不经过本模块；
路径规则集中在此，供 `api.data` 与将来的其它持久化共用。

```python
DATA_DIRNAME: str = "data"

def data_root() -> Path: ...              # Path.home() / ".yate" / DATA_DIRNAME（不创建）
def resolve(relative: str) -> Path: ...   # 校验后返回绝对路径（不创建）
def read_text(relative: str) -> str | None: ...
def write_text(relative: str, text: str) -> None: ...
def remove(relative: str) -> bool: ...
def names(relative_dir: str) -> list[str]: ...
```

校验规则（`resolve`）：

1. `relative` 必须是 `str` 且非空（否则 `ValueError`）；
2. `Path(relative)` 不得为绝对路径、不得有盘符（`drive`）、任一部件不得是 `..`；
3. 归一化后必须仍位于 `data_root()` 之内（`Path.is_relative_to` 兜底）；
4. 不展开 `~`（出现即当作普通相对名，最终仍落在 data_root 下）。

写语义：

- `write_text`：先 `parent.mkdir(parents=True, exist_ok=True)`，写同目录临时文件
  `<name>.<pid>.tmp`（`encoding="utf-8"`, `newline=""`），随后 `tmp.replace(target)`；
  任一步 `OSError` 直接上抛（由桥转成 `False`）。
- `read_text`：文件不存在返回 `None`；解码失败（`UnicodeDecodeError`）返回 `None` 并记 `log.warning`。
- `remove`：存在则删并返回 `True`，否则 `False`。
- `names`：目录不存在返回 `[]`；否则返回文件名升序列表（不递归）。

日志：`log = tracing.get_logger(__name__)`（R12）。

## 四、A2：`DataExtensionBridge`（`bridges.py` 追加）

放在 `DocsExtensionBridge` 之后、`ActionExtensionBridge` 之前：

```python
class DataExtensionBridge:
    """``api.data`` -- small text documents under ``~/.yate/data``."""
    def read(self, name: str) -> str | None
    def write(self, name: str, text: str) -> bool
    def remove(self, name: str) -> bool
    def list(self, prefix: str) -> list[str]
```

- 全部委托 `data_store`；`ValueError` / `OSError` 一律转成 `None` / `False` / `[]` 并 `log.warning`
  ——脚本是用户代码，不得因一次写盘失败把 canvas 回调打崩。
- 无注册状态，故不参与 A13 rollback scope。

## 五、A3：`api.py` 接线

- `ExtensionAPI.__init__` 末尾：`self._data = DataExtensionBridge()`（放在 `self._actions` 之后）。
- 新增属性：

```python
@property
def data(self) -> DataExtensionBridge:
    """Read/write small text documents under ``~/.yate/data``."""
```

- 模块 docstring 的桥清单里补 `data`。
- `ExtensionContext` 不动（无需注入，`data_store` 是纯函数模块）。

## 六、A4：`lua/library.py` 增 `lua_module_sources()`

```python
#: Sub-directory of the bundled extensions holding requirable Lua modules.
LUA_LIB_DIRNAME: str = "lib"

def lua_module_sources() -> dict[str, str]:
    """Read every bundled shared Lua module (``lib/*.lua``), keyed by stem."""
```

- 目录不存在 → `{}`（向后兼容：没有 `lib/` 的旧安装不报错）。
- 单个文件读失败 → `RuntimeError`（与 `lua_api_library_source` 同口径：安装损坏要快失败）。
- 排序读入，`dict` 保序。

## 七、A5：`lua/runtime.py` 支持预载模块

```python
def create_runtime(
    api: object,
    library_source: str,
    modules: Mapping[str, str] | None = None,
) -> Any:
```

- 在注册 `yate` 之后、返回之前：

```python
for name in sorted(modules or {}):
    preload[ name ] = _compile_chunk(runtime, modules[name], f"={_MODULE_CHUNK_PREFIX}{name}")
```

- 新增常量 `_MODULE_CHUNK_PREFIX: str = "lib."`（chunkname 只允许无引号 ASCII；
  stem 由文件名决定，实施时校验 `name` 只含 `[A-Za-z0-9_]`，否则 `ValueError`）。
- docstring 补「shared modules」段：模块与 `yate` 同机制，require 到的是**每个 runtime 自己的**副本。

## 八、A6：`loader.py` 传参

`_load_lua` 里改为：

```python
runtime = create_runtime(self.api, lua_api_library_source(), lua_module_sources())
```

import 行同步补 `lua_module_sources`；模块 docstring 无需改。

## 九、A7：Lua 面与声明

`_yate.lua`：

```lua
-- Persistent data under ~/.yate/data (one JSON document per game, ...).
yate.data = {}

function yate.data.read(name) return api.data.read(name) end
function yate.data.write(name, text) return api.data.write(name, text) end
function yate.data.remove(name) return api.data.remove(name) end
function yate.data.list(prefix) return api.data.list(prefix) end
```

- 顶部导出清单补四行；`---@param` / `---@return` 注解齐全（`list` 返回 Python list，注明 0-based）。
- `_yate.d.lua` 逐函数镜像（`---@param name string` / `---@return string|nil` 等），
  文件头说明不变。

`tests/test_lua_defs.py`：

- `LUA_SURFACE` 增 `data.read` / `data.write` / `data.remove` / `data.list`；
- `PYTHON_SURFACE` 增 `data`（`_yate.lua` 里以 `api.data.*` 出现，正则 `api\.(\w+)` 命中 `data`）。

## 十、测试

### 10.1 `tests/test_data_store.py`（新）

| 用例 | 断言 |
|---|---|
| `test_read_missing_file_returns_none` | 不存在 → `None` |
| `test_write_then_read_roundtrip_creates_parents` | `games/x.json` 写入后目录存在、内容一致（含中文/emoji） |
| `test_write_is_atomic_and_leaves_no_temp_file` | 连续两次写，目录里只有目标文件 |
| `test_write_replaces_previous_content` | 二次写覆盖 |
| `test_rejects_absolute_and_traversal_names` | `"/etc/passwd"`、`"../x"`、`"a/../../b"`、`"C:\\x"`、`""` → `ValueError` |
| `test_remove_reports_whether_the_file_existed` | `True` / `False` |
| `test_names_lists_files_sorted_and_tolerates_missing_dir` | 升序；缺目录 `[]` |

### 10.2 `tests/test_extension_bridges.py`（追加）

| 用例 | 断言 |
|---|---|
| `test_api_exposes_a_data_bridge` | `api.data` 是 `DataExtensionBridge` |
| `test_data_bridge_roundtrip_under_the_isolated_home` | write → read → list → remove 全链路（`isolated_home` 已把家目录指向临时目录） |
| `test_data_bridge_reports_invalid_names_as_false` | 写入 `"../evil"` 返回 `False`、不抛异常 |
| `test_runtime_preloads_shared_lua_modules`（`@requires_lupa`） | `create_runtime(api, lib_src, {"demo": "return {n = 41 + 1}"})` → `require("demo").n == 42` |

## 十一、验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_data_store.py tests/test_lua_defs.py tests/test_extension_bridges.py -q
```

通过判据：pyright 零诊断；三文件全绿（`test_lua_defs.py` 三条同步守卫必须仍为绿）。

## 十二、风险

| 风险 | 缓解 |
|---|---|
| Windows 下 `Path.replace` 跨盘失败 | 临时文件与目标同目录，不跨盘 |
| `api.data` 无限额导致脚本写爆磁盘 | 文档写明「只放小 JSON」；单文件 > 1 MB 由将来限流（本次不做，登记为非目标） |
| 新增 `lib/` 被 loader 误装载 | loader 只 glob 顶层（事实 1）；B 波测试断言 |
| 预载模块编译失败拖垮所有扩展 | 编译错误在 `create_runtime` 抛出，`_load_lua` 已有 try/except 记到 `record.error` |
