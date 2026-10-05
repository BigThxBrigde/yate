# plan_D：L2 ScreensaverScreen + L3 动作/键位 + L4 空闲接线

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
  editor.handle_key 全局 chord、toggle 逻辑移入 `Editor.toggle_screensaver`、
  `_check_idle` 加屏保激活守卫，见主方案 §八）**
- 上级：[README](overview.md) / 主方案 §0 §2.1 §2.2 §4.1 §4.2 §4.5
- 工作量：**中**｜依赖：plan_A（精灵包）、plan_C（配置）
- v6.1（master 合并后复核）：接线方式按实测修正——空闲探针用
  `YateApp.on_event`（原 `message_hook` 不存在）、推送走既有
  `Editor.push_overlay`、组件按 R13 自持主题。

## 目标

1. 全终端屏保 Screen：10fps 半格块动画、行走、switch 秒切换、
   shuffle 轮播；任意输入退出并恢复编辑现场。
2. `Alt+Shift+S` toggle + 空闲自动触发（interval 秒，0=禁用）。

## 改动文件清单（只改这些）

| 文件 | 动作 | 层 | 内容 |
|---|---|---|---|
| `yate/services/idle_tracker.py` | 新 | L0 | `IdleTracker` 纯数据类：`poke()` 记 monotonic、`due(now, threshold) -> bool`；无计时器/无 UI/无线程（主方案否决 E 的结论） |
| `yate/editor_view/screensaver.py` | 新 | L2 | `ScreensaverScreen(ModalScreen[None])`：构造注入 `characters: tuple[str, ...]`、`switch_seconds: int`（退出自持：`on_key`/`on_mouse_move` 里 `event.stop()` + `self.app.pop_screen()`，无需 on_exit 回调）；`DEFAULT_CSS` 用主题变量自持着色（`background: $background;`，提示行 `color: $text-muted;`——R13：颜色经 L4 主题桥自动生效，不从 L3/L4 注入）；`on_mount` 设 `set_interval(1/10)`；整屏 `Static` 每 tick 用 L0 `render_cells` 重建；精灵随机出生行、左→右行走、出屏或 switch 秒到切下一只（`shuffle_order`）；左下角暗淡提示行（R10：消费按键不冒泡） |
| `yate/actions.py` | 改 | L3 | `reg("toggle_screensaver", ...)`（新增 `from yate.editor_view.screensaver import ScreensaverScreen`；无架构守卫阻碍——R5 只禁 editor.py→actions 反向）：`isinstance(editor.app.screen, ScreensaverScreen)` → `editor.app.pop_screen()`，否则 `enable=False` 时 prompt 提示，enable 时装配过滤阵容并 `editor.push_overlay(...)`（editor.py:1390，自带消息行复位） |
| `yate/keymaps/vsc.py` | 改 | L0 | `"alt-shift-s": "toggle_screensaver"`（复核确认无占用） |
| `yate/keymaps/vim.py` | 改 | L0 | 同上 |
| `yate/app.py` | 改 | L4 | ① `YateApp.__init__`：`config.screen_saver.enable` 时建 `IdleTracker`；② 覆写 `async def on_event(event)`：`isinstance(event, events.InputEvent)` 时 `idle.poke()` 再 `await super().on_event(event)`（实测 Textual 8.2.8 textual/app.py:4060——分发前收到全部 Key+Mouse 含已消费的，唯一可靠探针）；③ `set_interval(1)` 轮询 `due` 到期 → `self.editor.execute_action("toggle_screensaver")`（与 app.py:244 `action_quit` 同款注册表分发，isinstance 判定天然防重入）；④ `character_names()` 比对白名单，未知名进 message line |
| `tests/test_screensaver.py` | 新 | — | pilot 用例（见验收） |
| `tests/test_idle_tracker.py` | 新 | — | 纯数据用例：poke 重置、未到期/到期、threshold=0 恒到期 |

## 实施步骤

1. `IdleTracker` + 测试（独立，先行）。
2. `ScreensaverScreen`：先静态一帧（复用 L0 渲染）→ 动画循环 → 行走/
   切换/shuffle → 退出路径。
3. L3 动作 + 双键位表。
4. L4 接线（`on_event` 探针 + 轮询 + 白名单校验）。
5. pilot 测试 + textual-pilot-smoke 冒烟。

## 架构自检（对照 §五清单）

- 依赖全向下：screensaver.py 只收具体对象/Callable；services/idle_tracker
  与 editor_sprites 无 Textual；无新 Protocol/`TYPE_CHECKING`/`Any`；
  无 `self.log`（R12）；**R13**：颜色全部由 ScreensaverScreen 的
  DEFAULT_CSS 主题变量自持，L3/L4 不碰 widget `.styles.*`（T2 断言不误伤：
  app.py 既有 `self.screen.styles.background` 属 L4 外壳自有屏幕）；
  无新 widget id（R9 不涉）；屏保消费按键 `event.stop()`（R10）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_screensaver.py tests/test_idle_tracker.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q   # 20 passed
.venv\Scripts\python.exe -m pyright yate/
```

pilot 断言：push 后 `app.screen` 类型为 ScreensaverScreen；任意键 pop
且编辑器 buffer 文本不变（按键未泄漏）；`toggle` 二次执行回编辑屏；
`enable=False` 时动作只提示不 push；20x6 窄终端 push 不抛异常。

## 回滚

新增 2 模块 + 4 处装配点（actions/vsc/vim/app），revert 即除。
