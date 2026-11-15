# IKU55P issue text (verbatim intake)

- URL: https://gitee.com/jermaine/yate/issues/IKU55P
- Title: ENH - which-key: yaterc gains an independent "auto trigger" switch, manual toggle stays usable
- State: open (待办的), label: enhancement, milestone: AI在哪里Vol.2
- Created: 2026-11-10 06:24:03 +08:00, deadline: 2026-11-14
- Comments: 0
- Intake scope: verbatim issue text only, no analysis and no design decisions (task-orchestration.md §二.1).

## Original body

### 一、背景与现状

- which-key 面板目前只有一个 yaterc 配置项 `which_key`（bool，默认 `True`），语义是**总开关**：
 `which_key = False` 时面板彻底不显示（挂起弦候选、`ctrl+w` 窗格组合、`<f9>` 钉住式速查页皆关闭），
 且 `toggle_whichkey` 变为空操作。见 `yate/config.py`、`yate/flows/whichkey_flows.py`、
 `yate/docs/yaterc.zh.md`。
- "自动触发"指：按键后存在挂起前缀（`pending_prefix()` / `ctrl+w` 组合）时，经每键
 `refresh_ui` 通道**同步立即**弹出候选面板；组合完成或取消随即隐藏。当前没有定时器、
 没有延时阈值，也没有任何独立开关。见 `yate/keymaps/base.py`、
 `yate/editor_dispatch.py`、`yate/docs/which-key.zh.md`。
- 手动显示入口是 `<f9>` → action `toggle_whichkey`（钉住整张按 category 分组的键位表，
 再按取消）。见 `yate/actions.py`、`yate/keymaps/vim.py`、`yate/keymaps/vsc.py`。

**痛点**：想关掉的只是"一敲前缀就弹面板"的打扰，但现有的唯一开关会把手动查表能力
一起关死；二者当前无法分开配置。

### 二、期望行为

1. 新增一个 yaterc 布尔配置项，专门控制**自动触发**（建议名 `which_key_auto`，
 命名沿用现有小写 snake_case bool 风格，最终名称可讨论），默认 `True`。
2. 该开关设为 `False` 时：挂起前缀 / `ctrl+w` 组合不再自动弹出面板；
 其余编辑行为、按键派发、候选计算逻辑均不变。
3. **无论自动触发开或关，手动 `<f9>` toggle 都保持可用且行为不变**——
 随时可以手动显示整张键位表、再按隐藏。这是本需求的核心。
4. 现有 `which_key` 保留为总开关且优先级更高，语义不变。

#### 行为矩阵（需完整覆盖）

| `which_key` | 自动触发开关 | 前缀挂起时自动弹出 | `<f9>` 手动 toggle |
| --- | --- | --- | --- |
| `True` | `True`（默认） | 是 | 可用 |
| `True` | `False` | **否** | **可用**（本次新增的目标态） |
| `False` | `True` | 否 | 不可用（no-op，维持现状） |
| `False` | `False` | 否 | 不可用（no-op，维持现状） |

### 三、验收标准

- [ ] yaterc 中设自动触发开关为 `False`（`which_key` 保持默认）后，vim 下按挂起前缀
 （如 `d`、`g`、`ctrl+w` 等）不再出现候选面板，且组合键本身仍正常完成。
- [ ] 同一配置下按 `<f9>` 仍能钉住全表、再按隐藏；隐藏后继续敲前缀键不会重新自动弹出。
- [ ] 不配置该开关或设为 `True` 时，自动弹出行为与现状完全一致，既有 which-key
 单测与冒烟场景（含 `which_key_toggle`、`which_key_ctrl_w_chord`）零回归。
- [ ] `which_key = False` 时，无论新开关取何值，面板一律隐藏、`<f9>` 仍为 no-op；
 重新启用总开关时可恢复原有钉住状态。
- [ ] 关闭自动触发时，已由 `<f9>` 钉住的面板不被清除、也不被前缀态覆盖（手动态与
 自动态互不干扰）；重新开启自动触发后行为恢复。
- [ ] 运行期切换该选项（与 `:set which_key=on|off` 同一套机制）即时生效；
 非 bool 值按现有约定记入配置错误且不改变当前状态。
- [ ] vsc 键位表仍不自动弹出（其本身无挂起前缀态），`<f9>` 手动查表不受影响。

### 四、边界与兼容性

- 默认 `True`，既有 yaterc 文件零迁移、行为零变化。
- 新开关只影响"是否自动推面板"，不影响候选内容、分组、渲染、溢出提示与主题样式。
- `which_key = False` 的既有文档描述（"面板彻底不显示、F9 变空操作"）保持成立，
 仅补充说明新开关与它的优先级关系。

### 五、非目标

- 不引入延时 / 阈值 / 定时器（当前是同步立即弹出，本需求不改变触发时机）。
- 不改动 `<f9>` 绑定与 `toggle_whichkey` 的既有语义。
- 不新增命令行 toggle 命令（"面板切换无命令行回退入口"为已知缺口，另案处理）。
- 不改动 vsc 既有行为，不重构 which-key 分层与渲染实现。

### 六、需同步的文档

双语同步硬约束：`yate/docs/which-key.{en,zh}.md`、`yate/docs/yaterc.{en,zh}.md`、
`yate/yaterc.example`、`yate/resources/manual.{en,zh}.md` 中的选项表与说明，
以及 `CHANGELOG.md` / `CHANGELOG.zh.md`、`FEATURES*.md`、`README*.md` 中
涉及 which-key 开关的条目。
