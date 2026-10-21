# plan-c：恢复画布最外层细线边框

> 隶属 [总纲 overview.md](overview.md)，wave-1。执行者：主代理（理由见总纲 §三）。

## 一、输入

- 用户需求：恢复前一版设计中最外层的细线边框。
- 前置事实：该边框是 `yate/resources/canvas.tcss` 中 `CanvasScreen .grid`
  的 `border: round $primary;`，由提交 `bbe88ae`（2026-10-21 21:29
  "drop the canvas chrome"）移除；同提交为修"超大游戏滚动整屏"而加的
  `CanvasScreen { overflow: hidden }` 与边框无耦合，必须保留。

## 二、独占文件清单（只许改这个）

| 文件 | 动作 |
|---|---|
| `yate/resources/canvas.tcss` | `CanvasScreen .grid` 块恢复一行 `border: round $primary;` |

## 三、具体修改

`CanvasScreen .grid` 块，在 `height: auto;` 与 `padding: 0;` 之间插入
（恢复 `bbe88ae` diff 中的原位置）：

```css
CanvasScreen .grid {
    width: auto;
    height: auto;
    border: round $primary;
    padding: 0;
    overflow: hidden;
    background: $surface;
}
```

## 四、测试用例

无新增测试。理由：`border` 是 Textual CSS 层渲染，`tests/test_canvas_screen.py`
对网格数据、按键转发、时钟语义做断言，不触样式（已全文扫描，无
border/styles/tcss 断言）；网格内容与 `cols`/`rows` 属性均不受 CSS 边框
影响。CSS 渲染效果按 §五手工步骤目检。

## 五、验收命令与手工验证

```powershell
Set-Location D:/Programming/yate-games
.venv/Scripts/python.exe -m pytest tests/test_canvas_screen.py tests/test_lua_games_app.py -q
```

手工验证（退出码无法覆盖 CSS 渲染）：

1. 在开发会话中启动 `:game snake`：画布网格四周出现圆角细线边框
   （`$primary` 色），网格本身仍为 80x24，游戏内自带边框完整；
2. `escape` 退出后 `:game pacman`：迷宫四周有细线外框，迷宫自身蓝墙
   纹理不变，`overflow: hidden` 语义不变（小端子裁切、不滚动）。

## 六、风险与回滚

- 小端子（80x24）上边框先于网格被裁切：与前一版设计（用户点名恢复的
  版本）行为一致，见总纲 R3，不属回归；
- 回滚：单行 revert 本笔提交。

## 七、执行记录（回填区）

- 待回填：实测命令结果与退出码、手工验证结论。
