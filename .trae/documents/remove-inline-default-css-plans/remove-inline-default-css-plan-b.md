# remove-inline-default-css plan-b：12 个组件 CSS 外置为打包 tcss（wave-1）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 10 个 `yate/editor_view/*.py`、`.trae/rules/architecture-boundaries.md`。
> 与 plan-a 文件不重叠，可并行。

## 一、目标

issue 第 1、2 点：py 文件零内联 CSS 字面量；每个 widget 类的 `DEFAULT_CSS`
改为 `load_tcss("<class>.tcss")`，与 `screensaver.py` 先例
（`yate/editor_view/screensaver.py:101`）同构。

## 二、搬运映射表（12 项）

| # | 类 | 源（内联块起点） | 新资源文件 | 加载落点 |
|---|---|---|---|---|
| 1 | `CommandInput` | `yate/editor_view/commandline.py:74` | `command-input.tcss` | 同文件 `DEFAULT_CSS` |
| 2 | `PromptBar` | `yate/editor_view/commandline.py:207` | `prompt-bar.tcss` | 同文件 |
| 3 | `CompletionPopup` | `yate/editor_view/completion.py:80` | `completion-popup.tcss` | 同文件 |
| 4 | `EditorView` | `yate/editor_view/editor.py:142` | `editor-view.tcss` | 同文件 |
| 5 | `ExplorerTree` | `yate/editor_view/explorer.py:64` | `explorer-tree.tcss` | 同文件 |
| 6 | `MarkdownDocScreen` | `yate/editor_view/manual.py:179` | `markdown-doc-screen.tcss` | 同文件 |
| 7 | `_OverlayScreen` | `yate/editor_view/modals.py:30` | `overlay-screen.tcss` | 同文件 |
| 8 | `PaletteScreen` | `yate/editor_view/palette.py:81` | `palette-screen.tcss` | 同文件 |
| 9 | `PaneHost` | `yate/editor_view/panes.py:424` | `pane-host.tcss` | 同文件 |
| 10 | `StatusBar` | `yate/editor_view/statusbar.py:57` | `status-bar.tcss` | 同文件 |
| 11 | `TerminalView` | `yate/editor_view/terminal.py:77` | `terminal-view.tcss` | 同文件 |
| 12 | `TerminalPanel` | `yate/editor_view/terminal.py:389` | `terminal-panel.tcss` | 同文件 |

## 三、搬运规则（机械、逐块执行）

每个内联块：

1. **tcss 文件内容** = 原字符串字面量**去 4 空格类体缩进**后的文本，
   文件头加一行注释（追踪归属，参照 `app.tcss` 头注释惯例）：

   ```css
   /* <ClassName> widget stylesheet (class-scoped DEFAULT_CSS) --
      loaded by editor_view/<module>.py via yate.paths.load_tcss. */
   ```

   除此之外**逐字节等价**：不改规则、不重排、不补空行。
2. **py 侧替换**：字面量 → `DEFAULT_CSS = load_tcss("<name>.tcss")`；
   导入区项目组（字母序）新增 `from yate.paths import load_tcss`；
   若该类原有 `#:` 说明注释（如 screensaver.py:98-101 形态），保留并改写为
   指向资源文件；无则不加。
3. 导入 `yate.paths` 为 L0 向下依赖，R3/R4 不受影响。

## 四、文档同步（R9 行号引用）

`.trae/rules/architecture-boundaries.md` R9 条目中
`editor_view/statusbar.py:57` 的 `DEFAULT_CSS` 用类选择器 `StatusBar`"
改为指向新资源并概括约定：

> 其中 `#statusbar` 只是 widget id（其样式由组件自持：
> `yate/resources/status-bar.tcss`——组件 `DEFAULT_CSS` 均为打包 tcss 资源、
> 经 `yate.paths.load_tcss` 装载，issue IKJHPH；类选择器 `StatusBar` 不变），
> 其余 id 均被外壳 CSS 直接引用

（保持该条目其余文字不动；行号引用自本计划起不再漂移。）

## 五、新增测试

无（plan-c 落 AST 守卫；既有 `tests/test_explorer.py:370-379` 内容子串断言
在本计划完成后必须仍然全绿——它就是本次搬运的等价性回归）。

## 六、验收命令（worktree 根执行）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -c "from yate.editor_view.panes import PaneHost; from yate.editor_view.statusbar import StatusBar; from yate.editor_view.commandline import PromptBar; print(all(t in s for t in ('PaneHost',)) or PaneHost.DEFAULT_CSS.index('PaneHost'), StatusBar.DEFAULT_CSS.index('StatusBar') >= 0, PromptBar.DEFAULT_CSS.index('CommandInput') >= 0)"
```

- pyright 零诊断、pytest 全绿（exit 0）；
- 探针验证三个依赖作用域最重的类加载出的样式文本仍含自身规则；
- 全仓检查无残留：`yate/editor_view/` 下 `DEFAULT_CSS = """` 字面量应为 0
  （plan-c 的守卫用例将其固化为永久断言）。

## 七、提交

`refactor(view): externalize widget DEFAULT_CSS to bundled tcss resources`
