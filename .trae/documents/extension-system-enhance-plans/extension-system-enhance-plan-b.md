# plan-b — Lua 桥分包 + setup/teardown 镜像（wave-2，与 plan-c 并行）

父计划：[../extension-system-enhance-plan.md](../extension-system-enhance-plan.md)

## 目标

1. `services/lua_extensions.py`（153 行平铺模块）拆为 `services/lua/` 包，
   与 Python 侧 `extension_api` / `extension_bridges` 分层对齐；
2. Lua 脚本镜像 Python 钩子模型：显式 `setup(api)` / `teardown(api)` 全局函数，
   保留"顶层即 setup"向后兼容；
3. `_yate.lua` 补 EmmyLua（`---@`）注解——"开放 pyi" 的 Lua 等价物，
   供 lua-language-server 补全（单一事实源，不另发 `.d.lua`）。

## 改动文件（独占清单）

| 文件 | 动作 |
|---|---|
| `yate/services/lua/__init__.py` | 新建：包 docstring（**不 re-export**，§三.5 服务包禁 re-export） |
| `yate/services/lua/library.py` | 新建：`is_lua_available` / `lua_api_library_source`（自原模块迁入） |
| `yate/services/lua/runtime.py` | 新建：`create_runtime` / `_compile_chunk` / `run_extension` + 新增 setup 镜像逻辑 |
| `yate/services/lua_extensions.py` | 删除（loader 外无其他 import 方；核对后删） |
| `yate/services/extension_loader.py` | import 改 `yate.services.lua.library` / `.runtime`；`_load_lua` 不变（run_extension 签名不变） |
| `yate/extensions/_yate.lua` | 全函数补 `---@param`/`---@return` 注解；头注释补 setup/teardown 两种写法说明 |
| `tests/test_lua_extensions.py`（存在则改，不存在则新建） | 包导入路径锁定 + setup 镜像行为 + 顶层兼容 |

## 设计

setup 镜像语义（`runtime.run_extension`）：

1. `runtime.execute("teardown = nil; setup = nil")`（防上一 chunk 泄漏，
   setup 一并清）；
2. 执行 chunk 顶层（兼容模式：顶层即 setup）；
3. 取全局 `setup`：可调用 → 以 runtime 内 `api` 全局为参调用
   `setup(api)`（A13 scope 由 loader 包裹，回滚覆盖显式 setup 的注册）；
4. 取全局 `teardown`：可调用 → 返回给 loader（现状语义不变）。

判定顺序保证向后兼容：无 `setup` 全局的存量脚本行为逐字节不变。

包结构（对齐 §三.5：服务包根不 re-export，重量级实现不进包根）：

```
yate/services/lua/
  __init__.py   # docstring: deliberately not re-exported
  library.py    # 可用性探测 + 库源读取（轻）
  runtime.py    # runtime 生命周期 + chunk 编译 + 钩子提取（重）
```

lupa 动态导入与 `Any` 注记纪律原样保留（无 stubs，理由注释随迁）。

## 步骤

1. 建 `services/lua/` 三文件，搬运现有函数（纯迁移，不改行为）。
2. `runtime.py` 实现 setup 镜像（步骤语义见上）。
3. `extension_loader.py` 改 import；`lua_extensions.py` 删除。
4. `_yate.lua` 注解与头注释（不改运行时行为）。
5. 测试：导入路径（`from yate.services.lua.library import is_lua_available`）、
   显式 setup 调用次序（顶层先于 setup）、teardown 提取、无 setup 兼容、
   setup 内注册失败回滚。

## 验收命令

```text
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_lua_extensions.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 新增测试清单

- `test_lua_package_import_paths`
- `test_explicit_setup_hook_called_after_chunk`
- `test_toplevel_only_script_still_loads`（兼容）
- `test_setup_failure_rolls_back_registrations`
- `test_teardown_global_extracted`

## 回滚

git 还原 `lua_extensions.py` + `extension_loader.py` import 行；删除新包目录。
