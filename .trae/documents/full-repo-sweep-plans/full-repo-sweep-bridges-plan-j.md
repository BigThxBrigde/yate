# R1：拆分扩展 bridges 模块（计划 j）

> **实施状态**：✅ 已实施 —— 2026-11-20（`dd61c63f`，子包兼容面全绿）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/services/extensions/bridges.py` 有 679 行，自述了十一个领域；`api.py:33-47` 导入 13 个名字，门面 `__init__.py:67-79,81-96` 再导出冻结的 14 个名字。直接内部导入存在于 `../../../tests/test_extension_bridges.py:32`、`test_extension_api.py:29`、`test_ui_contributions.py:25`、`test_ts_backend.py:30,429`。目前不存在真正的导入循环。

## 独占文件

- 新包 `../../../yate/services/extensions/bridges/`，含 `__init__.py` 加 3-4 个内部模块
- 删除 `../../../yate/services/extensions/bridges.py`
- 新测试 `../../../tests/test_extension_bridges_package.py`（不编辑任何现有测试文件）

不要修改 `api.py`、门面 `__init__.py` 或现有测试：包的 `__init__` 必须保留所有旧的模块级名字和导入路径。如果必须修改现有测试，则停下并上报。

## 设计

1. 拆分前根据实际导入构建依赖分组。预期分组：`ui.py`（StatusSegment、CanvasHandle、CanvasControls、CanvasOpener、UiExtensionBridge）、`syntax_lsp.py`（Lsp/Syntax/Highlight/Sprite/Theme bridges）、`data_event.py`（Event/Data/Clipboard/Docs/Action bridges）。若某组中的类引用了另一组，则将两者保留在同一模块中，并在 docstring 中记录原因；正确性优先于目标分组数。
2. `bridges/__init__.py` 再导出**所有**旧的公开名字：上述 13 个类加上别名 `SegmentAlign`、`CanvasControls`、`CanvasOpener`；若任何 caplog 测试依赖模块级 logger 名字，则将 `tracing.get_logger(__name__)` 冻结为旧的门面级名字（用 `../../../tests/test_extension_bridges.py` 验证；如需则使用 `../../rules/architecture-boundaries.md` R12 中登记的子包 logger 例外，并用结构性测试守卫它）。
3. 除导入行外，保持每个类体逐字节不变：无行为变更、无重命名、无新协议。所有包内导入保持绝对形式（`from yate.services.extensions.bridges.<module> import ...`），遵循 R6/绝对导入规则。
4. R14 得到满足：所有机制都留在 `services/extensions/` 下；冻结的 14 名字门面和插件导入路径未受影响。没有新增 `editor_components` 导入。

## 测试

- 现有直接导入测试必须原样通过：`test_extension_bridges.py`、`test_extension_api.py`、`test_ui_contributions.py`、`test_ts_backend.py`。
- `test_bridges_package_reexports_every_legacy_name`（新增，仅当 `../../../tests/test_extension_bridges.py` 可编辑时放入该文件——否则加到新的 `tests/test_extension_bridges_package.py`）：导入包并断言 13 个类名字中的每一个以及 `SegmentAlign`、`CanvasControls`、`CanvasOpener` 都与通过 `yate.services.extensions.api` / 门面（在导出处）导入的对应属性是同一对象；断言门面的 `tuple(__all__)` 未变。
- 导入循环冒烟：`python -c "from yate.services.extensions.bridges import UiExtensionBridge; from yate.services.extensions import UiExtensionBridge as B; assert UiExtensionBridge is B"`。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_extension_bridges.py tests/test_extension_api.py tests/test_ui_contributions.py tests/test_ts_backend.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/services/extensions/ tests/test_extension_bridges.py
```

每个新内部模块必须保持在 800 行以内（用 `splitlines()` 验证）；不得新增豁免。

## 风险 / 回滚

风险：循环导入或 caplog logger 名字漂移。回滚：恢复单一的 `bridges.py` 文件并删除包目录；其他所有文件保持不变。
