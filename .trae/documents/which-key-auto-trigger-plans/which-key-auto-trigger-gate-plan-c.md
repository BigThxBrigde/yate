# wave-2 / plan-c：WhichKeyFlows 自动态门控与注入接线

- 总纲：[overview.md](overview.md)；主计划：[../which-key-auto-trigger-plan.md](../which-key-auto-trigger-plan.md)
- 依赖：wave-1 `plan-a`（`YateConfig.which_key_auto` 字段已存在）；wave-1 两计划全绿后才进入
- 后继：wave-3 `plan-d` / `plan-e`

## 一、输入

- 主计划 §四设计契约（状态优先级）、§五交互图；方案 A（采纳）与 B/C/D/E（否决）理由。
- 现状：`yate/flows/whichkey_flows.py:1-14` 模块 docstring、`:30-35` `EnabledPredicate`、`:58-78` `__init__`、`:80-103` `refresh()`、`:105-115` `toggle()`；`yate/editor_compose.py:363-374`；`tests/test_whichkey_flows.py:53-69` `_make_flows`。

## 二、独占文件清单（只改这些）

1. `yate/flows/whichkey_flows.py`
2. `yate/editor_compose.py`
3. `tests/test_whichkey_flows.py` — **仅 `_make_flows`（`:53-69`）一段**，只做新参数透传；不得追加 / 修改用例（wave-3 `plan-d` 负责）。

## 三、具体修改（`文件:行号` 级）

1. `yate/flows/whichkey_flows.py:1-14` — 模块 docstring 补一句：构造注入两个谓词（`which_key` 总开关、`which_key_auto` 自动触发）；`refresh()` 的 pinned 分支不受 auto 开关影响，`toggle()` 只受总开关约束；`ctrl+w` 的 `on_chord_change` 与每键 `refresh_ui` 共用同一决策点。
2. `yate/flows/whichkey_flows.py:30-35` — `EnabledPredicate` 类型别名保持名字不变（`tests` 与既有代码不导入它，但避免无谓改名），`#:` 注释补充说明它同时用于两个开关、每次 `refresh()` / `toggle()` 读取。
3. `yate/flows/whichkey_flows.py:58-78` — `__init__` 增加**必填**关键字参数 `which_key_auto_enabled: EnabledPredicate`（置于 `which_key_enabled` 之后），新增 `self._auto_enabled = which_key_auto_enabled`；不设默认值（接线遗漏立即暴露，显式优于隐式）。docstring / 行内注释全 ASCII。
4. `yate/flows/whichkey_flows.py:80-103` — `refresh()` 分支顺序调整为：
   `if not self._enabled(): clear; return` → `if self._pinned: show sheet; return` → **新增** `if not self._auto_enabled(): self._panel.clear(); return` → `if self._window_pending(): ...` → `if pending := ...: ...` → `clear()`。
   docstring 写明 auto 闸门位于 pinned 之后，故钉住态不被清除、也不被前缀态覆盖；关闭自动态时只隐藏自动分支。不改 `_candidates` / `_sheet_entries` / `conflicts_report` / `clear()`。
5. `yate/flows/whichkey_flows.py:105-115` — `toggle()` 逻辑**不变**；docstring 补一句「auto 开关不参与 toggle 判定」。
6. `yate/editor_compose.py:363-370` — `WhichKeyFlows(...)` 构造在 `which_key_enabled=lambda: ed.config.which_key` 之后加 `which_key_auto_enabled=lambda: ed.config.which_key_auto,`。不得新增其它 import 或改动 `_build_pane_stack` 其它接线。
7. `tests/test_whichkey_flows.py:53-69` — `_make_flows` 增加参数 `which_key_auto_enabled: Callable[[], bool] = lambda: True`（放在 `which_key_enabled` 之后），并把它传入 `WhichKeyFlows(...)`；helper 的 docstring 相应补一句。保持所有既有调用点零改动（默认 `True` 复现旧行为）。

## 四、输出

- 自动触发两条链（每键 `editor._refresh_chrome`、和弦 `window_flows.on_chord_change`）都经同一 `refresh()` 闸门；`<f9>` / `toggle()` 与 pinned 状态不受影响；总开关短路位置不变。
- 既有 `tests/test_whichkey_flows.py` 全部用例（含 `:279,307,330,342` 总开关闭路）零回归。

## 五、可执行验收命令（worktree cwd，PowerShell）

```powershell
.venv\Scripts\python.exe -m pyright yate/flows/whichkey_flows.py yate/editor_compose.py tests/test_whichkey_flows.py
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py -q
git diff --check
```

判据：三条退出码 0。既有 9 个与开关 / 触发相关用例必须全绿；若因新必填参数导致任何构造期 TypeError，说明接线遗漏，修复后复跑，不得改成断言放宽。

**本波不新增用例**：新增用例的验证目标、arrange/act/assert 与验收命令见 `plan-d` §四；冒烟见 `plan-e` §四。架构侧：本改动不新增 import 连线、不新增模块 / 协议，故不新增 `tests/test_architecture.py` 守卫用例（依据主计划 §二末条与 §七）。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| auto 闸门放在 pinned 之前 → 钉住态被清除 | 固定分支顺序；wave-3 专门用例反向验证 | 调整顺序并复跑 `plan-d` 的 pinned 用例 |
| 只门控 `refresh_ui`，漏掉 `on_chord_change` | 门控在 `refresh()` 内部，两条链共用 | 同上 |
| `editor_compose` 漏注入 → 运行期 TypeError | 必填参数 + wave-3 冒烟启动 App 实证 | 补注入 |
| 默认行为漂移 | helper 默认 `True`、生产默认 `True`、分支顺序仅插入一个短路 | 回退三文件改动 |

## 七、报告格式

改动清单（文件 + 行号）、三条命令实测退出码、既有测试通过情况（以退出码表述）、未解决项。偏离计划（含参数默认值、分支顺序）须显式列出并给依据。

## 八、执行回填（F1，2026-11-10）

实际命令与退出码（主代理复核）：

- `.venv\Scripts\python.exe -m pyright yate/flows/whichkey_flows.py yate/editor_compose.py tests/test_whichkey_flows.py` → 退出码 0
- `.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py -q` → 既有 18 条用例全绿，退出码 0
- `git diff --check` → 退出码 0

偏离：无。auto 闸门按 §三.4 固定在 pinned 分支之后，`_make_flows` 默认 `True` 保持既有调用点零改动。
