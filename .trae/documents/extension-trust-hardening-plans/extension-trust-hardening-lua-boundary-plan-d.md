# 子计划 d — S-01 Lua 运行时真值与 chunkname 安全化（wave-2）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-01。
> 只改 2 个文件。按主计划 §二 A 否决沙箱路线，本子计划**不得**裁剪 Lua 标准库。

## 一、目标与非目标

- 目标：`runtime.py` 全部注释 / docstring 不再暗示「无 Lua 文件 I/O」或
  「每扩展一个 runtime 构成沙箱」；把 chunkname 作为 Lua 值传入而非字符串
  插值，消除未来放宽命名时的 Lua 代码注入点；新增用例把「标准库可用」
  钉成受信任代码契约。
- 非目标：不改 `LuaRuntime(...)` 构造参数、不改共享模块 / `package.preload`
  装载机制、不改 `_MODULE_NAME_RE` 的校验存在性、不改 `loader.py`、不改
  `_yate.lua`（那是 plan_e 的独占文件）。

## 二、独占文件清单

1. `yate/services/extensions/lua/runtime.py`
2. `tests/test_lua_engine.py`

## 三、具体改动

### 3.1 `yate/services/extensions/lua/runtime.py:1-29, 42-59, 62-79, 87-109`

- 模块 docstring 增补一段（英文 ASCII）：本模块提供的是**扩展间隔离**，不是
  安全沙箱；Lua 5.4 标准库 `io` / `os` / `package` / `debug` 与 Python 桥接
  保持可用，`.lua` 与 `.py` 扩展同为完全受信任代码（与
  `yate/docs/extensions.{en,zh}.md` 的 Trust model 一致）。
- 常量区：
  - 新增 `_CHUNK_NAME_GLOBAL: str = "_YATE_CHUNK_NAME"`，`#:` 说明其用途；
  - 新增 `_COMPILE_EXPR: str = "assert(load(_YATE_CHUNK_SOURCE, _YATE_CHUNK_NAME))"`
    （常量字符串，**无 f-string / 无插值**）；
  - 修正 `:42-44` 与 `:55-57` 两处注释：chunknames 不再被插入 Lua 字符串
    字面量，`_MODULE_NAME_RE` 的作用是保证共享模块名是合法的 Lua 标识符
    （供 `require("<name>")` 使用），不是「quote-free」要求；
  - `_CHUNK_SOURCE_GLOBAL` 注释保持，补一句两个全局都会在 `finally` 清空。
- `_compile_chunk()`：
  ```python
      globals_ = runtime.globals()
      globals_[_CHUNK_SOURCE_GLOBAL] = source
      globals_[_CHUNK_NAME_GLOBAL] = chunkname
      try:
          return runtime.eval(_COMPILE_EXPR)
      finally:
          globals_[_CHUNK_SOURCE_GLOBAL] = None  # assigning nil removes it
          globals_[_CHUNK_NAME_GLOBAL] = None
  ```
  docstring 同步：`assert(load(source, chunkname))` 的两个值都由全局传入，
  语法错误仍以 :class:`lupa.LuaError` 命名该 chunk 抛出，且两个停车全局
  对用户 chunk 不可见。
- `create_runtime()` docstring `:101-103`：把「The preload table is the only
  channel on purpose: no ``package.path`` entry and no Lua-side file I/O」改为
  准确表述：`package.preload` 是 yate 共享模块的唯一解析通道（便于冻结
  构建），**并不禁用** `io` / `os` 等标准库，也不构成沙箱。
- 保持 `LuaRuntime(unpack_returned_tuples=True)` 与 Lua 5.4 pin 及其 GC 说明原样。

### 3.2 `tests/test_lua_engine.py`

先读 `:1-60` 了解 `@requires_lupa` / `_lua_quote` 等既有夹具；本文件已有
`# pyright: reportPrivateUsage=false` 或同等处理（若没有，按现有风格处理私有
`_compile_chunk` 调用，不得新增 `Any` 无理由注释）。

- 修改 `:365-371 test_create_runtime_rejects_unsafe_module_names` 的 docstring：
  理由改为「共享模块名必须是合法 Lua 标识符（供 `require` 使用）」，断言不变
  （仍 `pytest.raises(ValueError, match="invalid shared Lua module name")`）。
- 新增 `@requires_lupa` 用例
  `test_compile_chunk_passes_chunkname_as_a_lua_value()`：
  - arrange：`runtime = create_runtime(FakeApi(), lua_api_library_source())`；
    `chunkname = '"] .. os.execute("echo pwned") .. ["'`（含引号与 Lua 闭合尝试）；
    `side_effect = tmp_path / "pwned.txt"` 不创建（如需文件系统副作用，
    用 `os.execute` 写 tmp 文件的形式，并断言文件不存在）。
  - act：`chunk = _compile_chunk(runtime, "return 7", chunkname)`；
    `value = chunk()`。
  - assert：`value == 7`；`side_effect` 不存在；`runtime.globals()["_YATE_CHUNK_SOURCE"]`
    与 `["_YATE_CHUNK_NAME"]` 均为 `None`（Lua nil 映射）。
  - 说明：旧实现把该 chunkname 插入双引号字符串，会触发 Lua 语法错误或注入；
    新实现把整个字符串当值处理。
- 新增 `@requires_lupa` 用例
  `test_lua_runtime_exposes_standard_libraries_as_trusted_code()`：
  `runtime = create_runtime(FakeApi(), lua_api_library_source())`；
  `probe = runtime.eval("return type(os.execute) .. ':' .. type(io.open) .. ':' .. type(require)")`；
  `assert probe == "function:function:function"`。该用例把「无沙箱」作为
  **有意契约**钉死，防止后续误以为已裁剪。
- 新增 `@requires_lupa` 用例
  `test_compile_chunk_names_syntax_errors_by_chunkname()`（可选但建议）：
  `with pytest.raises(Exception, match="bad-chunk")` 由 `_compile_chunk(runtime, "return =", "=bad-chunk")`
  触发；用 `lupa.LuaError` 具体类型需先确认本文件既有异常断言形态，无法确认时
  用 `pytest.raises(Exception)` 并附注释说明 lupa 无 stub。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/services/extensions/lua/runtime.py tests/test_lua_engine.py
.venv\Scripts\python.exe -m pytest tests/test_lua_engine.py tests/test_lua_extensions.py -q
.venv\Scripts\python.exe -m pytest tests/test_lua_engine.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

不跑 `tests/test_lua_defs.py`（wave-2 由 plan_e 并行修改该文件，避免竞态）。
通过判定：三条退出码全 0；lupa 已随 `[dev]` 安装，若未安装则相关用例 skip，
须在报告中列明 skip 数。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 全局名 `_YATE_CHUNK_NAME` 与用户 chunk 冲突 | 编译期立即清空；用例断言清空 | `git checkout -- yate/services/extensions/lua/runtime.py tests/test_lua_engine.py` |
| `runtime.eval` 常量表达式与 lupa 版本行为差异 | 先跑现有 Lua 全量用例；表达式仍走 Lua-native `load` | 恢复原 f-string 但保留注释修正（需上报主代理） |
| 注释修正被 `test_comments_and_docstrings_stay_ascii` 拦截 | 全部注释英文 ASCII，不写 CJK / `§` / 全角标点 | 改写成 ASCII 后再跑架构用例 |

## 六、报告格式

改动清单、实跑命令与退出码、skip 清单、未解决项与原因。
