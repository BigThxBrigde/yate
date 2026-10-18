# plan_b — Lua 全成员镜像 + IDE lint 基建（wave-2）

## 目标

NEXT STEPS 点 3 + 点 4：`_yate.lua` 与 Python API 同成员；`_yate.d.lua`（`---@meta`）+ `.luarc.json` 让用户 lua 脚本在 lua-language-server 下 0 诊断；机械漂移守卫测试双向锁死三份表面（Python API / _yate.lua / _yate.d.lua）。

## 前置

wave-1（plan_a）已完成并提交 —— Lua 包装转发到 `api.bind_action` / `api.unbind_key` / `api.theme` / `api.clipboard` / `api.docs` / `api.actions` / `api.ui.add_segment` / `api.events.EditorEvent`。

## 专属文件清单（独占）

- `yate/extensions/_yate.lua`
- `yate/extensions/_yate.d.lua`（新建）
- `.luarc.json`（新建，仓库根）
- `yate/extensions/lua.example`
- `tests/test_lua_extensions.py`
- `tests/test_lua_defs.py`（新建）

## 精确改动

### 1. yate/extensions/_yate.lua（注释/注解一律英文）

1. 头部块注释的 "Exported functions" 清单同步新增全部成员（见下）。
2. 新增包装（全部 positional-only、nil 显式补默认 —— 沿用 bind_key L107-120 的 nil 语义说明）：
   - `yate.events.subscribe(name, fn)`：name 为小写字符串（"document_saved" / "document_opened" / "document_closed" / "document_activated" / "diagnostics_updated" / "keymap_changed" / "theme_changed"），映射 `api.events.EditorEvent` 的大写枚举成员（lupa 属性访问）；未知 name → `error("unknown event: " .. name)`；返回 unsubscribe 闭包（Python 返回的 thunk 原样透传即可）。
   - `yate.ui.add_segment(id, provider, align, priority)`：`align or "right"`、`priority ~= nil and priority or 0`，转发 `api.ui.add_segment`。
   - `yate.theme.set(name)` / `yate.theme.active()`（返回主题名字符串）。
   - `yate.clipboard.set(text)`（返回 bool）/ `yate.clipboard.get()`。
   - `yate.docs.all()`（Python list，0 基） / `yate.docs.is_open(path)`（bool）。
   - `yate.actions.run(name)`（bool）/ `yate.actions.names()` / `yate.actions.has(name)`。
   - `yate.bind_action(spec, action, keymap)`：`keymap or "vsc"`；注明"绑定前 action 必须已注册"。
   - `yate.unbind_key(spec, keymap)`：`keymap or "vsc"`；返回 bool。
   - `yate.keymaps = api.keymaps`（原样透传，加注释）。
3. 每个新函数带 `---@param` / `---@return` EmmyLua 注解（先例 L77-79）；嵌套表（yate.events 等）在函数上方用 `yate.events = {}` 形式组织，或直接 `function yate.events.subscribe(...)` 定义（选后者，与 LLS 兼容最好）。
4. 不触碰既有函数与桥接注释语义。

### 2. yate/extensions/_yate.d.lua（新建，`---@meta`）

- 首行 `---@meta yate`；文件只含声明与注解，无可执行逻辑（meta 文件不会被执行，loader 也因 `_` 前缀跳过装载）。
- 声明全局 `yate` 表：全部导出函数（既有 8 个包装 + 透传字段 + 全部新成员）逐个 `function yate.xxx(...) end` + 与 _yate.lua 一致的 `---@param`/`---@return` 签名。
- 事件名参数用 `---@param name string` + 注释列出 7 个合法值（或 `---@alias` 枚举联合，选实现最简者）。
- 头部注释说明用途：IDE（VS Code Lua 插件 / lua-language-server）把本文件加入 workspace.library 后，用户脚本中 `yate.*` 即获得补全与 0 unknown-global 诊断。

### 3. .luarc.json（新建，仓库根；JSON 无注释，保持最小）

```json
{
  "$schema": "https://raw.githubusercontent.com/LuaLS/vscode-lua/master/setting/schema.json",
  "runtime.version": "Lua 5.4",
  "workspace.library": ["yate/extensions"],
  "workspace.checkThirdParty": false,
  "diagnostics.globals": ["api"]
}
```

- `runtime.version` 取 5.4（LLS 支持上限；lupa 内嵌更高版本时 5.4 是最近的可用档，缺口仅 require 多返回值语义，不影响库文件 lint）。
- `workspace.library` 使 `_yate.lua` / `_yate.d.lua` 对仓库内所有 lua 文件可见。

### 4. yate/extensions/lua.example（英文注释）

- 增补：`setup(api)` 显式风格下演示 `yate.events.subscribe("document_saved", ...)`（含 teardown 里调用返回的 unsubscribe）、`yate.ui.add_segment`、`yate.bind_action("gq", "my_action")`（先 register_action 后 bind_action 的顺序示例）。
- 保留既有内容不删。

### 5. tests/test_lua_extensions.py（新增用例）

- subscribe：合法名映射到对应 EditorEvent 枚举并完成订阅/退订往返（用真 EventHub）；未知名触发 LuaError 且 error 消息含 "unknown event"。
- ui.add_segment：注册后经 `api.ui.segments("right")` 可见；nil align/priority 落到默认值。
- theme.set/active、clipboard.set/get、docs.all/is_open、actions.run/names/has：monkeypatch 注入回调或桥接层（与现有测试风格一致）。
- bind_action：绑定后 keymap lookup 的 action 为名（复用现有测试的 keymap 夹具）；unbind_key 移除返回 True。
- 沿用现有 lupa skip 机制（无 lupa 环境下 pytest.skip）。

### 6. tests/test_lua_defs.py（新建，机械漂移守卫；纯文本解析，不依赖 lupa）

- 常量 `LUA_SURFACE`：_yate.lua 应导出的全量成员名 frozen 集（含嵌套 `yate.events.subscribe` 等点路径）。
- 常量 `PYTHON_SURFACE`：Lua 必须转发到的 Python API 成员名 frozen 集（message/register_command/register_action/bind_key/bind_action/unbind_key/shell/open_path/save/buffer/doc/workspace/theme/clipboard/docs/actions/events/ui/keymaps/highlight/sprites/lsp/syntax）。
- 断言：解析 `_yate.lua` 中 `function yate.<path>(` 行 → 与 LUA_SURFACE 相等（双向：不多不少）。
- 断言：`api.<name>` 引用（正则 `api%.([%w_]+)` 的 Python 侧等价 `r"api\.(\w+)"`）覆盖 PYTHON_SURFACE 全部成员。
- 断言：解析 `_yate.d.lua` 中 `function yate.<path>(` 声明 → 与 LUA_SURFACE 相等。
- 任一漂移（新增函数漏 meta / 删函数漏清理 / Lua 引用了不存在的 Python 成员）即红。

## 硬规则自检

- 规则 377：_yate.lua / _yate.d.lua / lua.example 全部英文注释与注解。
- R6：测试与产物 0 新增 Any/TYPE_CHECKING/ignore。
- `_yate.d.lua` 以 `_` 前缀确保 loader 永不装载（extension_loader.py:74）。
- .luarc.json 不影响 Python 测试/打包（非资源目录，不入 wheel 语义面；如打包测试断言资源清单变化则同步 test_pack 断言——先查再改）。

## 验收命令

```
python -m pytest tests/test_lua_extensions.py tests/test_lua_defs.py -q
python -m pytest tests/test_extension_examples.py -q
```

exit 0。

## 回滚

单提交 `feat(lua): mirror the python api surface and ship ide lint defs`；revert 即可。
