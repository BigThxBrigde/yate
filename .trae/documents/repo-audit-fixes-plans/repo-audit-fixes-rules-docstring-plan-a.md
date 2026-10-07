# 子计划 plan-a：规则与 docstring 修订（A3 / A11 / A18 / A20 登记）

> 所属波次：**wave-1**（与 tests-guard / changelog-zh / assets 三个子计划文件不重叠，可并行）。
> 执行者：**主代理**（涉及 `.trae/rules/` 权威规则与 `yate/` 源码 docstring）。
> 来源：评审 A3 / A11 / A18 / A20；调研事实 F3、F5（见主计划 §一）。

## 一、输入

- A3：`yate/registries.py:5-6` docstring 声称 "live in their own leaf module (below `keymaps` ...)"，但 `registries.py:19` `from yate.keymaps.base import ActionContext`，而 `keymaps/base.py:17` import `yate.session`——registries 实际在 keymaps 之上。（session.py 半条为评审误报，**不改**，见主计划 F3。）
- A11：8 个文件超 800 行阈值且规则无豁免名单与拆分判定标准；实测行数以 F5 为准（regex_backend 1225 / vim 1107 / diffview 1035 / config 924 / editor 907 / buffer 871 / emulator 856 / manager 818）。
- A18：新增 L3 流程模块接入步骤无文档（editor.py 30 个类属性声明 + `OverlayFlows` 16 参数手工注入）。
- A20：editor.py 907 行临界超标，`editor.py:769-840` 为 `:set` 后端 setter（约 70 行，wave-4 plan-d 将部分收敛）。

## 二、独占文件清单（本子计划只改这些）

1. `yate/registries.py`（docstring，第 1-12 行模块 docstring）
2. `.trae/rules/architecture-boundaries.md`（§一 L1 描述、新增 §二.5 或 §三.7 "文件体量阈值处置" 条款、新增 L3 流程模块接入清单条目）

## 三、具体修改

### 3.1 A3——registries.py docstring 如实描述层级

改 `registries.py:5-6`：把 "They live in their own leaf module (below `keymaps` and below
`yate.editor`) ..." 改为如实的表述——registries 是 L1 容器，依赖 `yate.keymaps.base`（`ActionContext`）、`yate.session` 之上的 `keymaps.base` 与 `yate.logs`；明确 "above `keymaps.base` (which imports `yate.session`), below `actions.py` / `commands.py` / `editor.py`"。不移动 `ActionContext`（评审方案①下沉真叶子属结构变更，本轮取最低成本方案②，理由：`ActionContext` 依赖 `EditorSession`/`KeyUi`，下沉需要把 `KeyUi` 一并搬动，牵连 keymaps 全链，收益仅是 docstring 措辞）。

### 3.2 A11——规则补"文件体量阈值处置"条款

在 `.trae/rules/architecture-boundaries.md` §二（分层职责表之后）新增小节，内容：
- 阈值：单文件 > 800 行触发处置评审；
- 拆分判定：多职责混合型必拆（判据：模块 docstring 无法用一句话概括、或含 ≥2 个互不引用的职责块）；单一职责长文件可登记豁免；
- 豁免名单（登记即合规，修改时须同步更新行数）：`editor_syntax/regex_backend.py`（LangSpec 数据表与 tokenizer 一体，拆分另行立项）、`keymaps/vim.py`（motion/operator/text-object 单一键映射域）、`editor_view/diffview.py`（diff 渲染管线单一职责）、`config.py`（wave-4 plan-d 拆分后复核）、`editor.py`（构造工厂约 300 行 + `:set` setter，wave-4 复核）、`editor_core/buffer.py`、`editor_term/emulator.py`（VT 状态机单一职责）、`editor_lsp/manager.py`（LSP 客户端单职责）；
- 负面清单：`logs.py` 明确不拆（三服务内聚，docstring 已论证）。

### 3.3 A18——L3 流程模块接入清单

在同一新增小节补"新增 L3 流程模块接入清单"（保持显式注入，不建共享 context 类型）：
1. 模块命名 `*_flows.py` / 类名 `*Flows`（`lsp_sync` 类按动词命名）；
2. `editor.py` 声明类属性（类型注解 + `None` 初值）；
3. 在对应 `_build_*` 工厂内构造，注入具体协作者与回调（不持 App 句柄，守卫 `test_flow_modules_hold_no_app_handle`）；
4. `editor.py` 的 `Editor.__init__` 组装顺序注释更新；
5. 如需 `editor_view` 导入，登记 `tests/test_architecture.py` 的 `UI_FROZEN_FILES`；
6. 同步规则 §一 L3 清单与本清单。

### 3.4 A20——豁免登记

A20 并入 3.2 豁免名单条目（`editor.py` 行，注明"wave-4 plan-d 落地后复核行数，仍 >800 则保留豁免"）。

## 四、测试与验证方案

本子计划为 docstring / 规则文本变更，无行为变化，不新增测试。守卫回归：`tests/test_architecture.py` 22 条不变全绿。

验证目标与命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/test_registries.py -q
```

手工验证：通读修订后的 `architecture-boundaries.md`，确认 A1（wave-2 plan-e 将改 §三.5）之外无未同步引用 §一 L1 清单的文本。

## 五、风险与回滚

- 风险：规则文本与后续波次（plan-e 改 §三.5、plan-g 改 §一/R11）在同文件连续修改，产生合并冲突——同执行者按波次串行，无实际冲突。
- 回滚：单提交 revert；docstring 还原为原文不影响行为。
