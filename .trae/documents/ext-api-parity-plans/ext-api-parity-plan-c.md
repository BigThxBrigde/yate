# plan_c — 双语手册与 Python 示例模板（wave-2）

## 目标

把 wave-1/plan_b 冻结的 API 面写进双语手册（点 1/2/3/4 的用户文档闭环），并把 Python 示例模板迁到免内部 import 的新 API 用法。

## 专属文件清单（独占）

- `yate/docs/extensions.en.md`
- `yate/docs/extensions.zh.md`
- `yate/extensions/example_ext.py.example`

## 精确改动

### 1. yate/docs/extensions.en.md 与 extensions.zh.md（结构对齐，双语同步）

1. **既有章节修订**：
   - api.events 示例改用 `api.events.EditorEvent`（免 `from yate.services.events import EditorEvent` 内部 import；en 现位于 §4.10，zh 对应节）。
   - api.ui 状态栏段示例（§4.11）优先展示 `api.ui.add_segment(id=..., provider=..., align=..., priority=...)` 工厂；`add_status_segment(StatusSegment(...))` 保留为“显式构造”变体，注明二者等价。
2. **新增章节**（编号顺延；每节含最小可运行示例）：
   - §4.12 `api.actions` 与快捷键重绑：`run(name) -> bool` / `names()` / `has(name)`；`api.bind_action(key_spec, action_name, keymap="vsc")`（重绑内建键到任意具名 action 的完整示例，含 “both”）；`api.unbind_key(key_spec, keymap="vsc")`；注明“先注册后绑定”、未知 action/keymap 只 warning 不绑定、A13 回滚语义。
   - §4.13 `api.theme` / `api.clipboard` / `api.docs`：set/active（只读返回主题名）、get/set、all/is_open（只读列出打开文档；注明变更类操作请走命令/`api.open_path`）。
   - §4.14 Lua 脚本过 IDE lint：`_yate.d.lua`（`---@meta`）与 `.luarc.json` 说明；用户项目配方两种——(a) `.luarc.json` 的 `workspace.library` 指向 yate 安装内的 `yate/extensions`（wheel/frozen 路径差异一句提示），(b) 把 `_yate.d.lua` 复制进项目（如 `.vscode/`）并配置 `Lua.diagnostics.globals: ["api"]`；推荐 VS Code “Lua” 插件（lua-language-server）。
   - §6（Lua 章节）成员总表更新：新增 yate.events / yate.ui / yate.theme / yate.clipboard / yate.docs / yate.actions / yate.bind_action / yate.unbind_key / yate.keymaps；注明与 Python API 同成员（点 3 闭环表述）。
3. 术语与行文风格对齐既有章节（en/zh 同构；zh 不是 en 的机翻腔）。语言切换链接保持不动。

### 2. yate/extensions/example_ext.py.example

1. `from yate.services.events import EditorEvent`（若存在）改为 `api.events.EditorEvent` 用法。
2. 状态栏段演示改用 `api.ui.add_segment(...)` 工厂（删除 `StatusSegment` 的内部 import，若该 import 因此不再需要）。
3. 增加一小段 `api.actions`/`bind_action` 演示（注册 action + 重绑一个键），保持模板精简（≤15 行增量）。
4. 注释语言与文件既有风格一致（英文）。

### 3. 一致性核查（必做）

- 手册提到的每个 `api.*` 成员必须在 wave-1 后的 ExtensionAPI 上真实存在（对照 `yate/services/extension_api.py`）。
- 手册提到的每个 `yate.*` 成员必须在 `_yate.lua` 中真实导出（对照 plan_b 的 LUA_SURFACE 清单；plan_b 并行进行，以其计划清单为准）。
- `docs/` 其余手册不触碰；`yate/resources/changelog.*` 不触碰（wave-3 由主控再生成）。

## 硬规则自检

- 双语成对同步（规则 109）；文件名不改；相对链接有效（不新增断链，可用既有校验脚本 `python -m tools.check_links`（若存在，名字以仓库为准）或手工核对）。
- 示例模板不加 emoji、不加超范围功能。

## 验收命令

```
python -m pytest tests/test_extension_examples.py -q
```

exit 0（示例模板仍被该测试覆盖与校验）。

## 回滚

单提交 `docs(extensions): document the widened api surface and lua lint setup`；revert 即可。
