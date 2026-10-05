# Textual 框架钩子：`YateApp` 中"零引用"成员的由来

> 对应源码：`yate/app.py`
>
> `YateApp` 里有若干成员在文件内部（甚至整个 yate 代码库内）**没有任何调用点**，
> 例如 `get_theme_variable_defaults`、`action_quit`、`ENABLE_COMMAND_PALETTE`、
> `get_driver_class`、`on_event`。
> 它们并非死代码，而是 Textual 框架的**内置扩展点（模板方法模式）**：
> 子类覆写，框架反向回调。因此在这个文件里 grep 不到调用是正常的。
>
> 行号于 2026-10-05 按当前 `yate/app.py` 重新核对（文件已增长，旧行号全部失效）。

## 1. `get_theme_variable_defaults()`（app.py:282）

### 是什么

Textual `App` 的内置方法，基类默认实现返回 `{}`。框架在构建样式表时通过
`App.get_css_variables()` 调用它，把返回的自定义变量与主题变量合并后传给
`Stylesheet` 做 CSS 变量解析。

### yate 覆盖它的原因

`yate/editor_view/manual.py:183` 的 `DEFAULT_CSS = load_tcss("markdown-doc-screen.tcss")`
装载的样式表（即资源文件 `yate/resources/markdown-doc-screen.tcss`，
变量引用不在 `manual.py` 内）引用了两个自定义变量：

```css
background: $doc-hit-background;          /* resources/markdown-doc-screen.tcss:51 */
background: $doc-hit-current-background;  /* resources/markdown-doc-screen.tcss:54 */
```

正常情况下，桥接主题（`yate/editor_view/theme.py:645-646`）会定义这两个变量。
但如果某个主题的桥接失败、或 fallback 到未定义这两个变量的主题，Textual 的
CSS 解析器在启动时会因变量缺省而**直接解析失败**。这个 override 提供兜底
默认值，取自当前 yate 主题的黄色高亮：

```python
{
    "doc-hit-background": f"{t.yellow} 12%",
    "doc-hit-current-background": f"{t.yellow} 40%",
}
```

### 相关约束

`tests/test_theme_palettes.py:321-322` 断言桥接主题中这两个变量的值与
`app.py` 中的兜底值保持一致。若调整其一，需同步另一处。

**删除后果**：特定主题状态下启动会因 CSS 变量缺失而崩溃。

## 2. `action_quit()`（app.py:298）

### 是什么

Textual `App` 内置 `ctrl+q` 优先级绑定（见 `textual/app.py` 的 `BINDINGS`）：

```python
Binding(
    "ctrl+q",
    "quit",
    "Quit",
    tooltip="Quit the app and return to the command prompt.",
    show=False,
    priority=True,
)
```

触发时框架通过 action 机制调用 `action_quit`。

### yate 覆盖它的原因

把 Textual 自带的 `ctrl+q` 退出路径重定向回注册表：实现是
`self.editor.execute_action("quit")`（app.py:306，与 palette / 扩展走同一条
分发路径），而不是直接调 `Editor.quit()`，因此仍经过 yate 自己的退出守卫
（例如有未保存修改时的确认流程）。yate 代码库内没有任何地方
绑定 `ctrl+q`，正是依赖 Textual 的这个内置绑定。

**删除后果**：`ctrl+q` 会绕过退出守卫直接强退。

## 3. `ENABLE_COMMAND_PALETTE = False`（app.py:46）

### 是什么

Textual `App` 的类属性，框架启动时读取。设为 `False` 禁用 Textual 内置的
`ctrl+p` 命令面板。

### yate 设置它的原因

`ctrl+p` 是 yate 自己的命令提示（command prompt），需要让位，避免按键冲突。

## 4. `get_driver_class()`（app.py:65，2026-10-05 复核）

### 是什么

Textual `App` 的内置方法，框架在启动时调用它决定用哪个输入驱动类。

### yate 覆盖它的原因

Windows 上原驱动的按键记录会退化成字符，虚拟键码与修饰位丢失，`ctrl+数字`、
`ctrl+\`` 之类根本到不了键位层。覆写在 `sys.platform == "win32"` 且 yaterc
`key_protocol != "legacy"` 时返回 `yate/keyproto/driver_windows.py::YateWindowsDriver`
（从控制台记录合成规范键名）；headless / pilot 运行显式请求 `HeadlessDriver`，不受影响。

**删除后果**：Windows 下键弦失效，`ctrl+数字` 等绑定不可达。

## 5. `on_event()`（app.py:224，2026-10-05 复核）

### 是什么

Textual `App` 的事件总入口，`App.on_event` 在焦点 widget 之前看到每一条
Key / Mouse 记录。

### yate 覆盖它的原因

它是唯一可靠的"用户仍在活动"探针：屏保空闲跟踪（`IdleTracker.poke()`）挂在这里；
无论事件是否被 widget 消费，都会继续走 `super().on_event(event)` 正常分发。

**删除后果**：被 widget 消费掉的按键不再重置空闲计时，屏保会在用户正在输入时弹出。

## 总结：识别模式

| 成员 | 类型 | 调用方 | 删除后果 |
| --- | --- | --- | --- |
| `get_theme_variable_defaults` | 方法覆写 | Textual 构建 stylesheet 时 | 特定主题下启动崩溃 |
| `action_quit` | 方法覆写 | Textual `ctrl+q` 内置绑定 | `ctrl+q` 绕过退出守卫 |
| `ENABLE_COMMAND_PALETTE` | 类属性覆写 | Textual 启动/按键路由 | `ctrl+p` 冲突 |
| `get_driver_class` | 方法覆写 | Textual 启动选驱动 | Windows 键弦失效 |
| `on_event` | 方法覆写 | Textual 事件总入口 | 空闲计时失真，屏保误触发 |

> 注：yate 对基类成员的覆写统一加 `@override`（`typing.override`），
> 可作为"这是框架钩子而非自有方法"的可检索标记。

判断一个"零引用"成员是否为框架钩子的方法：

1. 在框架源码（如 `site-packages/textual`）中搜索该成员名，确认基类是否有
   同名定义及调用点；
2. 若基类有定义，即模板方法——子类覆写后由框架回调，项目内无引用属正常；
3. 注意此类覆写与框架行为强耦合，升级 Textual 版本时应检查基类签名与调用
   时机是否变化。
