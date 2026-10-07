# 子计划 plan-g：flows/ 子包迁移与命名统一（A10 + 评审 §六）

> 所属波次：**wave-3**（与 docs-split-plan-c 文件不重叠，可并行；主代理执行；依赖 wave-2 全部验收通过）。
> 执行者：**主代理**（改 `yate/` 产品源码）。
> 来源：评审 A10 与 §六 结构建议；主计划 §四.2（采用迁移，否决仅改命名 / 否决拆 logs.py）。

## 一、输入

- 迁移对象（9 个根目录模块 → `yate/flows/`）：`document_flows.py`、`prompt_flows.py`、`window_flows.py`、`shell_flows.py`、`extension_flows.py`、`completion.py`、`overlays.py`、`lsp_sync.py`、`prompt_completion.py`；
- 命名统一（A10）：`completion.py → flows/completion_flows.py`、`overlays.py → flows/overlay_flows.py`（类名 `CompletionFlows` / `OverlayFlows` 不变，文件名对齐 `*_flows.py`）；`lsp_sync.py` 保留文件名（类 `LspSync` 动词命名合规，规则 §五 自检清单注明"同步适配器按动词命名"）；
- 引用面实测 24 处（主计划 §四.2）：
  - 生产 import：`yate/editor.py:31,33,50,57-60,65,66`（10 条，含 `prompt_completions` 函数导入）；
  - 同层互引：`window_flows.py:21`（document_flows）、`document_flows.py:26`（completion）；
  - 文档/docstring 引用：`yate/editor_view/diffview.py:68`、`yate/shell_flows.py:6`、`yate/prompt_flows.py:5`、`yate/overlays.py:7`、`yate/lsp_sync.py:7`、`yate/document_flows.py:7,14,220`、`yate/window_flows.py:8`、`yate/editor.py:490`；
  - tests：`test_prompt_completion.py:17`、`test_changelog_view.py:23`、`test_app_textual.py:28,2313`（patch 目标 `yate.shell_flows.run_shell`）、`test_explorer.py:31`；
  - tools 注释：`tools/smoke_test/scenarios/workspace_nav.py:12`、`screensaver.py:14`；
- 规则同步面：`architecture-boundaries.md` §一 L3 清单（`:17-20`）、R11 冻结清单（`:50-56`）、§六 守卫描述（`:216`）；`tests/test_architecture.py` `UI_FROZEN_FILES`（`:114-160`，键为 `yate/` 下相对路径）。

## 二、独占文件清单

1. 新增 `yate/flows/__init__.py`（**惰性**：仅 docstring，零 import）
2. git mv 9 个模块入 `yate/flows/`，其中 2 个改名（`completion_flows.py` / `overlay_flows.py`）
3. `yate/editor.py`（10 条 import 改 `yate.flows.*`；docstring 内 1 处引用）
4. `yate/flows/window_flows.py:21`、`yate/flows/document_flows.py:26`（同层互引改路径）；其余 6 个迁移文件的 docstring 引用同步
5. `yate/editor_view/diffview.py:68`（docstring）
6. `tests/` 4 个文件（§一列表）
7. `tools/smoke_test/scenarios/` 2 处注释
8. `tests/test_architecture.py`（`UI_FROZEN_FILES` 键改为 `flows/completion_flows.py` 等）
9. `.trae/rules/architecture-boundaries.md`（§一 / R11 / §六）

## 三、执行步骤（纯移动 + import 调整，行为零变化）

1. `git mv` 9 文件 → `yate/flows/`（2 个同时改名）；
2. 新 `yate/flows/__init__.py`：模块 docstring 说明"L3 流程模块子包；`__init__` 保持惰性（§三.5），各模块经完整路径导入"；
3. 批量更新 §一清单全部引用（生产 12 处 + tests 5 处 + tools 2 处 + 规则与守卫面）；
4. `test_architecture.py` 的 `UI_FROZEN_FILES` 键路径迁移；确认 `test_flow_modules_hold_no_app_handle` 的扫描根 `yate/*.py` 扩为 `yate/*.py` + `yate/flows/*.py`（顶层平铺扫描覆盖不到子包）；
5. `test_app_textual.py:2313` 的 `patch("yate.shell_flows.run_shell", ...)` 改为 `yate.flows.shell_flows.run_shell`。

## 四、测试与验证方案

不新增行为测试（纯移动）。既有守卫面迁移后必须全绿：

- `test_collaborators_keep_widget_coupling_frozen`（R11 冻结面）
- `test_flow_modules_hold_no_app_handle`（能力注入）
- `test_editor_does_not_import_action_tables`（R5，editor.py 改动回归）

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_app_textual.py tests/test_explorer.py tests/test_changelog_view.py tests/test_prompt_completion.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
Get-ChildItem yate\*.py | Measure-Object   # 根目录 .py 数量应降至 ~15
```

手工验证：`python -m yate --help` 正常启动（CLI 路径不触 flows，做冒烟基线）；`Get-ChildItem yate\flows\__init__.py` 内容仅 docstring。

## 五、风险与回滚

- 风险 R1（主计划）：外部以 `yate.overlays` 等路径 import 的破坏面——0.2.9 阶段生态最小；CHANGELOG 破坏性变更条目（wave-6）。
- 回滚：整波单提交 revert（git mv 保留历史，revert 干净）。
