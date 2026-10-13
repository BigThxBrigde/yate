# 扩展系统增强 — plan-e：Lua 模块表入口形态（plan-e 追加波）

主计划：[../extension-system-enhance-plan.md](../extension-system-enhance-plan.md)
分支：`enh/extension-system-enhance`　worktree：`../yate-extension-system-enhance`（沙箱复用，已自证）

来源：用户 review 反馈——通用 Vim/Neovim Lua 生态的扩展写法是
`local mod = {}; mod.setup = ...; return mod` 模块表形态，yate 当前忽略
chunk 返回值（`runtime.py:120`），该形态会"成功加载、零注册、静默无产出"。

## 一、目标与非目标

### 目标

1. 支持**模块表入口**：chunk 返回 Lua 表时按模块契约处理——
   `mod.setup(api)` 被调用（纳入 A13 回滚 scope）、`mod.teardown(api)`
   作为卸载钩子；
2. 优先级链钉死并文档化：**模块表 > 全局 setup/teardown > 顶层即 setup**；
3. **响亮失败**：返回表但无可调用 `setup` → 报错（意图明确却缺入口，
   多半是拼写错误），不静默跌回顶层语义；
4. 文档三形态重排：模块表为推荐形态、全局 setup 为 Python 对照形态、
   顶层为快速脚本形态（双语同步 + `_yate.lua` 头注释 + `lua.example`）。

### 非目标

- Lua 多文件包化（require 路径解析，主计划已列为后续 STEP）；
- `_yate.d.lua` 新增声明（本计划不改导出面，lockstep 测试不受影响）；
- Python 侧任何改动。

## 二、调研事实清单（文件:行号）

| # | 事实 | 位置 |
|---|---|---|
| F1 | `chunk()` 返回值被丢弃，仅回收全局 setup/teardown | `yate/services/extensions/lua/runtime.py:118-128` |
| F2 | 陈旧全局预清已存在（`teardown = nil; setup = nil`） | `runtime.py:118` |
| F3 | setup 调用在 loader 回滚 scope 内（`_load_lua` 包裹 run_extension） | `yate/services/extensions/loader.py:162-183` |
| F4 | lupa 无 stub，桥接值一律 `Any` + 理由注释；`create_runtime` 动态 import lupa 先例 | `runtime.py:72-97` |
| F5 | live-lua 测试组 `@requires_lupa` + 真注册表 `_ApiBundle` 基线成熟 | `tests/test_lua_extensions.py:30-127` |
| F6 | 手册 §6 现为"两种写法"（顶层/显式），双语 | `yate/docs/extensions.zh.md:728-753`（en 对应节） |
| F7 | `_yate.lua` 头注释 "Setup styles" 两形态 | `yate/extensions/_yate.lua:15-23` |
| F8 | `lua.example` 头注释与尾部示例块同为两形态 | `yate/extensions/lua.example:9-17, 66-103` |

## 三、备选方案与否决理由

| 决策点 | 采用 | 否决路线及理由 |
|---|---|---|
| 返回表缺 setup | 报错（响亮失败） | 静默跌回顶层语义会复活"静默零产出"最差失败模式；返回表即模块意图，缺 setup 多半是拼写错误 |
| 表检测手段 | `runtime.eval` 注入 `type(v)=='table'` 判定函数 | `lupa.lua_type` 需在 `run_extension` 里再次动态 import lupa；eval 判定自包含于 runtime，桥接语义一致（nil/非表均判非） |
| teardown 优先级 | `mod.teardown > 全局 teardown` | 与 setup 对称；全局钩子在模块表形态下属于误用混合，取模块契约为准 |
| 入口形态取舍 | 三形态并存 + 优先级链 | 只留模块表破坏存量脚本；只留顶层则放弃显式契约价值 |
| 文档结构 | 模块表推荐 → 全局对照 → 顶层快速 | 维持"两形态"叙述会与实现漂移 |

## 四、分步实施

### step-1 runtime.py 优先级链

- 输入：F1-F4；
- 改动文件：`yate/services/extensions/lua/runtime.py`（`run_extension` 重写 +
  模块 docstring 与 `loader.py:163` docstring 措辞同步）；
- 输出：优先级链实现，契约错误为 `RuntimeError`（loader 记录为
  `RuntimeError: extension module table has no setup(api) function ...`）；
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_lua_extensions.py -q` 全绿。

### step-2 测试

- 改动文件：`tests/test_lua_extensions.py`（新分组 "--- module-table entry ---"）；
- 用例：模块表 setup/teardown 全链路；表缺 setup 响亮报错且零注册；
  模块 setup 失败回滚；模块表压过全局 setup；mod.teardown 压过全局 teardown；
  非表返回值回落全局/顶层语义；
- 验收：`pytest tests/test_lua_extensions.py -q` 全绿。

### step-3 文档与模板

- 改动文件：`yate/extensions/_yate.lua`（头注释 Setup styles 三形态）、
  `yate/extensions/lua.example`（头注释 + 模块表示例块）、
  `yate/docs/extensions.zh.md` / `extensions.en.md`（§6 三形态重排，模块表推荐）、
  简介段（`.zh.md:8-9` / en 对应行）补模块表形态；
- 验收：`test_lua_defs.py` 不受影响（不改导出面）；双语文件同时提交。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| lupa 对 `chunk()` 返回值/表字段访问语义与预期不符 | 实现前跑临时探针脚本验证（验证完删除） | git 单文件还原 |
| 表缺 setup 报错误伤"顶层注册 + 返回辅助表"的非常规脚本 | 错误消息明示两种修正路径；手册写明契约 | 文档澄清；必要时降级为警告（须再评审） |
| pyright strict 对 Any 边界 | 沿 F4 先例（`Any` + noqa 理由注释） | — |

## 六、验收门禁（主代理亲跑，全波共用）

```text
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/        # 0 诊断
.venv\Scripts\python.exe -m pytest tests/ -q                    # 全绿
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75
.venv\Scripts\python.exe -m tools.smoke_test run                # UI 无变更，回归确认
```

## 七、提交切分（每步单独提交，不推送；推送由收尾统一执行）

1. `docs(plans): add plan-e for the lua module-table entry form`
2. `feat(lua): support the module-table entry form for extensions`
3. `docs(extensions): document the module-table entry style`

pr-review 修复与 CHANGELOG 另行提交；收尾推送 `enh/extension-system-enhance`
至 origin，**不推送 wiki 仓库**。

## 八、pr-review 记录（2026-10-14）

范围：`be6e4a0..HEAD`（plan-e 三笔提交，7 文件 +329/-58；实现前 lupa
语义探针两轮，验证后已删除）。

**Overall: APPROVE**

硬门禁实测（主代理亲跑，真实退出码）：

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors, 0 warnings, exit 0 |
| `pytest tests/ -q` | exit 0（全绿，新增 6 用例） |
| `pytest tests/test_architecture.py -q` | exit 0 |
| `pytest --cov --cov-fail-under=75` | 91.95%，exit 0 |
| `tools.smoke_test run` | 112/112 scenarios passed, exit 0 |

六维度结论：

1. **功能与正确性**：优先级链与两轮 lupa 探针实证一致（Lua 表 / nil /
   数字 / 字符串 / Python 对象 / 多返回值 tuple / 缺字段返回 None）；
   模块 setup 全链路、失败回滚、对全局 setup 与 teardown 的优先级覆盖
   均有用例锁定；非表返回回落语义有用例锁定。
2. **安全**：无新攻击面；错误消息为固定串，`eval` 仅注入固定 helper。
3. **性能**：每扩展加载一次 helper eval，可忽略。
4. **可维护性**：三形态 docstring 齐全；`Any` 边界沿既有
   `# noqa: Any - lupa ships no stubs` 先例。
5. **架构边界**：`services/extensions/lua/` 无向上依赖；无新增
   Protocol / TYPE_CHECKING / 全局总线；`test_lua_defs.py` lockstep 不受
   影响（仅改 `_yate.lua` 头注释）。
6. **硬门禁**：全绿（见上表）。

MINOR（2 项，登记不阻塞）：

1. **行为边界**：plan-e 前"顶层注册 + `return` 一张表（无 setup）"的
   脚本可静默加载成功；现按本文 §三/§五 的响亮失败决策改为报错并回滚
   顶层注册。缓解依据：返回值此前无任何语义、作者无理由返回表，误伤面
   趋近于零；契约已在双语手册与 `_yate.lua` 头注释写明。
   → 处置：CHANGELOG 记录该边界（收尾执行）。
2. **多值返回**：`return mod, x` 经 `unpack_returned_tuples` 成 Python
   tuple，非表 → 回落全局/顶层语义。契约即"返回表"，不做特判。
   → 处置：维持现状，留档即可。
