# yate 代码评审报告：UI refine 实现（2026-09-27）

> 生成时间：2026-09-27 +08:00
> 评审对象：分支 `enh/ui-refine`（`b21afe7..0221ffa` + 合并 `5b99c3c`），worktree `D:/Programming/yate-ui-refine-wt`
> 关联 issue：[IKINF3](https://gitee.com/jermaine/yate/issues/IKINF3)
> 评审范围：`yate/editor_view/{explorer,icons,scrollbars,panes,editor}.py`、`yate/app.py`、`yate/editor.py`、`tests/{test_explorer,test_scrollbars,test_app_textual}.py`
> 评审方式：主代理逐文件 diff 评审 + 上游源码取证（textual `_tree.py` / `scrollbar.py`）
> 计划文档：[ui_refine_plan.md](../documents/ui_refine_plan.md)

---

## 一、门禁（实测）

| 门禁 | 结果 |
|---|---|
| `pyright` strict（yate/ + tests/ + tools/） | **0 errors**（每轮提交前实测） |
| `pytest tests/` | **全绿**（仅平台性 skip） |
| 架构守护 `tests/test_architecture.py` | **18 用例全过**（含合并进来的 R12 用例） |
| pilot 冒烟 | SVG 文本断言：无 `▶/▼`、`\uf07c` 翻转、轨道/滚动条渲染正确 |

## 二、整体质量评分

| 维度 | 得分 | 依据 |
|---|---|---|
| 架构合规 | A | R1–R11 逐条核过；改动全部落在 L2 组件 + L4 CSS；新增叶子 `icons.py`/`scrollbars.py` 零 yate 依赖 |
| 健壮性 | A- | 滚动条渲染保留鼠标元数据；9 个 guide 状态选择器全覆盖；render_bar 有 4 个行为测试钉住 |
| 可维护性 | A- | `#:` 常量文档、docstring 完整；一处自造重复已修复（`df631e6`） |
| 可扩展性 | B+ | 两条已评估的架构张力待治理（见 §四） |

## 三、核心问题清单

| # | 位置 | 等级 | 状态 |
|---|---|---|---|
| 1 | `icons.py` 后缀解析逻辑重复（本轮自造） | 建议 | **已修** `df631e6`：`extension_of()` 提前，`icon_for_path` 复用 |
| 2 | `scrollbars.py::render_bar` 复刻上游 1/8 粒度算法 | 记录 | 保留；Textual 升级需回归 `tests/test_scrollbars.py` |

## 四、架构张力（非违规，已评估 → 待重构）

### T1 `install_slim_scrollbars()` 是进程级全局变更

- **位置**：[scrollbars.py](../../yate/editor_view/scrollbars.py) `install_slim_scrollbars()`，调用点 L4 `YateApp.__init__`。
- **现状**：`ScrollBar.renderer = SlimScrollBarRender` 类属性 monkey-patch，进程内所有 Textual App 的滚动条全部生效。
- **合法性**：Textual 官方文档化钩子（`scrollbar.py` docstring 自带示例）；L4 顶层发起、方向合法；yate 单 App 进程下成立。
- **风险**：若未来单进程多 App（测试嵌套、嵌入场景），无法按 App 粒度区分；隐式全局状态，新读者不易发现生效路径。
- **整改方向**：改为 per-widget 注入（上游原生支持 `widget.horizontal_scrollbar.renderer = ...`），由各滚动组件自持。

### T2 `apply_theme`（L3 Editor）直改 widget 内部状态

- **位置**：[editor.py](../../yate/editor.py) `Editor.apply_theme`：直写 `tree.styles.scrollbar_*`、`view.apply_scrollbar_theme()`、`prompt_bar.styles.background`、`status_bar.refresh_status()` 等。
- **现状**：L3 调度层伸手进 L2 组件内部样式——严格说撞"Editor 不直接持有 widget 内部状态"。属存量模式（本轮仅改色值，未扩大战果）。
- **风险**：组件主题表现散落在 L3，新增组件时容易漏改；组件无法独立测试主题行为。
- **整改方向**：组件自持主题——主题变化以回调广播（规则四"1:N 低频广播 → 回调列表"），各组件在 `on_mount` 订阅、`on_unmount` 退订，自己读 `theme.active()` 给自己上色；`Editor.apply_theme` 收缩为触发广播。

## 五、优先整改项

1. T1 + T2 一起治理：两者同属"组件自持"主题/外观，一条分支 `ref/theme-ownership` 完成（已立项）。
2. T2 治理时注意 L0 叶子（`editor_term`）不能 import L2 `theme`，颜色注入走构造回调（N30 模式先例）。

## 六、长期优化建议

- 升级 Textual 依赖时，把 `tests/test_scrollbars.py` 列入必回归清单。
- 若后续出现"单进程多 App"需求，T1 的 per-widget 注入方案需覆盖动态创建的 widget（pane 分屏、弹层）。
