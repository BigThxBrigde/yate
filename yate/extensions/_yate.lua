--[[
yate 内置 Lua API 库（_yate.lua）

这是 yate 随包提供的 Lua 扩展 API 库。每个 ``.lua`` 扩展脚本都有**独立的
Lua 运行时**，yate 在创建运行时时会编译本文件并做两件事：

1. 把本模块注册进 ``package.preload["yate"]`` —— 所以你可以
   ``local yate = require("yate")``；
2. 把同一个模块表设为全局变量 ``yate`` —— 不写 require 也能直接用。

两种形态拿到的是同一张表，按喜好二选一即可。

使用要点（lupa 桥接语义）：

* 文件名以 ``_`` 开头，因此本库**不会**被当作扩展自动加载；
* 全局变量 ``api`` 是 yate 的 Python 侧 ``ExtensionAPI`` 对象。本库是对它
  的薄封装；高级用法可以直接访问 ``yate.api``（原始桥直通）；
* Python 对象在 Lua 里直接用点号访问属性与方法：
  ``yate.api.buffer.get_text()``、``yate.api.doc.path`` 等；
* **Python 的列表/字符串索引从 0 开始**（Lua 表从 1 开始）：第一行是
  ``yate.buffer().lines[0]``；
* Lua 的长度操作符 ``#`` 对 Python 对象**不可用**；要取 Python 列表长度，
  用桥内置的 ``python.builtins.len(list)``；
* Lua 无法向 Python 传关键字参数（kwargs），所以本库全部函数都设计为
  **面向位置传参**，可选参数留空（nil）即用 Python 侧默认值；
* Python 的字符串就是 Lua 字符串，双向无损；返回的 Python 对象（如
  ``shell()`` 的结果）可以在 Lua 里继续读属性；
* 注册类调用都发生在加载期，注册过的命令/按键/动作在脚本出错时会被
  自动回滚，不会留下半成品。

导出的函数（详见各函数注释）：

  message(text)                          在消息栏显示提示
  register_command(name, fn, desc?)      注册 ``:`` 命令
  register_action(name, fn, desc?)       注册命名动作
  bind_key(spec, fn, keymap?)            绑定按键
  shell(cmd)                             静默执行 shell 命令
  open_path(path)                        在编辑器中打开文件/目录
  save()                                 保存当前文档
  buffer() / doc() / workspace()         取当前缓冲区/文档/工作区对象
  api / highlight / sprites / lsp / syntax   原始 Python 桥直通

完整示例见随包的 ``lua.example``；扩展手册见
``yate/docs/extensions.en.md``（中文 ``extensions.zh.md``）。
]]

local yate = {}

-- 在消息栏显示一条提示文本。
function yate.message(text)
  api.message(text)
end

-- 注册一个 ``:`` 命令。fn 接收命令名之后的原始参数字符串（可为空串）。
-- 命令会出现在命令面板（Alt+Shift+P）与 :help 列表里，支持 Tab 补全。
-- desc 可省略（默认 "extension command"）。
function yate.register_command(name, fn, description)
  api.register_command(name, fn, description)
end

-- 注册一个命名动作。动作可被键位表绑定，也可在命令面板中按名检索执行。
-- fn 的签名与键位回调一致（接收一个 ActionContext，可忽略）。
-- desc 可省略。
function yate.register_action(name, fn, description)
  api.register_action(name, fn, description)
end

-- 绑定一个按键。spec 使用 yate 的键记法，如 "<alt-h>"、"<ctrl-shift-u>"。
-- keymap 可省略（默认 "vsc"）；可选 "vsc" / "vim" / "both"（"both" 同时
-- 绑定两套键位）。Lua 无法传 kwargs，因此 keymap 以第 3 个位置参数传入。
function yate.bind_key(spec, fn, keymap)
  api.bind_key(spec, fn, keymap)
end

-- 同步执行一条 shell 命令（静默，不弹输出浮层）。
-- 返回 Python 的 ShellResult 对象（可读 .output / .returncode），失败为 nil。
function yate.shell(cmd)
  return api.shell(cmd)
end

-- 在编辑器中打开一个文件或目录（新标签）。
function yate.open_path(path)
  api.open_path(path)
end

-- 保存当前文档。
function yate.save()
  api.save()
end

-- 返回当前活动缓冲区（Python TextBuffer 对象）。注意 lines[0] 是第一行。
function yate.buffer()
  return api.buffer
end

-- 返回当前活动文档（Python Document 对象：path / filetype / modified / save）。
function yate.doc()
  return api.doc
end

-- 返回文件树工作区对象。
function yate.workspace()
  return api.workspace
end

-- 原始 Python 桥直通：高级用法的逃生门。
-- yate.api          -- ExtensionAPI 本体（本库就是它的薄封装）
-- yate.highlight    -- 注册声明式语法高亮（api.highlight.register(spec, ...)）
-- yate.sprites      -- 注册屏保精灵（api.sprites.register(...)）
-- yate.lsp          -- 注册语言服务器（api.lsp.register_server(...)）
-- yate.syntax       -- 注册 tree-sitter 语法（api.syntax.register_tree_sitter(...)）
yate.api = api
yate.highlight = api.highlight
yate.sprites = api.sprites
yate.lsp = api.lsp
yate.syntax = api.syntax

return yate
