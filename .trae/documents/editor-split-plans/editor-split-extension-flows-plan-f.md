# plan-f：抽取 ExtensionFlows（extension_flows.py）

> 前置：plan-b/c/d/e 已合入；行号基于 HEAD `07004a0`（editor.py 结构未变）。

## 一、职责与迁移清单

`extension_flows.py::ExtensionFlows` 承接 editor.py 的扩展启动流（:1347-1422）。

迁移成员（3 个）：

| 成员 | editor.py 行号 | 依赖取证 |
|---|---|---|
| `load_startup_services` | :1349-1364 | `load_startup_extensions`（loader, config, ext_dirs, ext_files）、`_register_configured_servers` |
| `trust_cwd_extensions` | :1366-1400 | `Path.cwd()`、`trust_workspace`（:1378）、`extension_loader.load_directory`（:1392）、`message` |
| `_register_configured_servers` | :1402-1422 | `extension_api.lsp` bridge、`config.language_servers` |

### 缓冲区归属裁定：`_ext_messages` 留在 Editor

它不是扩展私有状态，而是 **Editor 的前置挂载消息缓冲**：

- 种子是 yaterc 错误而非扩展消息（:304-306 `[f"yaterc: {err}" for err in self.config.errors]`）；
- `_report`（:407-412）为文档打开路径缓冲 pre-mount 告警（:499/:515 "not a text file"），
  plan-d 后这些调用在 DocumentFlows 内、经注入的 `report` 回调落回此缓冲；
- `on_mount` 统一冲刷（:371-372，`; `.join 后 kind="warn"）。

因此 `load_startup_services` 改为**返回** `load_startup_extensions` 的告警列表，
由调用方 extend 进缓冲——Editor 保留缓冲所有权，ExtensionFlows 不回写 Editor 私有状态。

headless 语义不变：`--diag` 只需 load 已发生。实证
`diagnostics.format_report` 读 `editor.config / ext_dirs / ext_files /
extension_loader.loaded / lsp`（diagnostics.py:243-375 grep 取证），**不读**
`_ext_messages`；headless 下缓冲本就永不冲刷，返回值被丢弃与现状等价。

## 二、构造签名与装配

```python
ExtensionFlows(
    ed.extension_loader, ed.extension_api, ed.config,
    ed.ext_dirs, ed.ext_files, message=ed.message,
)
```

- 装配点：`_build_models` 尾部（`extension_loader` :118 之后）；六个依赖当时全部就绪。
- `trust_cwd_extensions` 的 `message` 保留注入（`:trust` 是命令，只在挂载后可达）。
- `on_unmount` :388 `self.extension_loader.teardown_all()` **不动**——对具体协作者
  的 1:1 直调（§四交互表第 1 行），包一层 `extension_flows.teardown_all()` 反而是薄委托。

## 三、调用方改直调（grep 驱动，断言语义不变）

| 位置 | 改动 |
|---|---|
| editor.py on_mount :363 | `self.load_startup_services()` → `self._ext_messages.extend(self.extension_flows.load_startup_services())` |
| yate/cli.py:328 | `app.editor.load_startup_services()` → `app.editor.extension_flows.load_startup_services()` |
| yate/commands.py:128 | `editor.trust_cwd_extensions()` → `editor.extension_flows.trust_cwd_extensions()` |
| tests/test_diagnostics.py:36/258 | 同 cli 形态：`app.editor.extension_flows.load_startup_services()` |
| tests/test_cli.py:41-44/239 | 桩对象补 `extension_flows` 形状（`load_startup_services_called` 计数器移入桩 flows；cli 访问路径即 `editor.extension_flows.load_startup_services`） |
| tests/test_app_textual.py:2859 | → `app.editor.extension_flows.trust_cwd_extensions()` |
| tests/test_app_textual.py:2854/2887/2918/2941 | 读 `app.editor._ext_messages` **不变**（缓冲留在 Editor） |
| editor.py | 删 extensions 节 :1347-1422；import 清理：`load_startup_extensions`（:62）、`trust_workspace`（:65）移入新模块（`ExtensionAPI`/`ExtensionContext`/`ExtensionLoader` :58-63 保留——`_build_models` 与 `extension_context` 仍用） |

## 四、规则同步（总纲 §六矩阵）

- `architecture-boundaries.md` §一 L3 流程模块枚举补 `extension_flows.py`。
- `tests/test_architecture.py` `UI_FROZEN_FILES` **不增条目**——实证
  extension_flows 只 import `services.extensions` / `services.trust` / `config` /
  `pathlib`，零 editor_view 依赖（与 plan-d/e 不同，无需 R11 白名单）。

## 五、验收命令（全部退出码 0；探针退出码 1 = 通过）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
# 实测 --diag（headless 路径回归，[extensions] 节正常、退出码 0）
.venv\Scripts\python.exe -m yate --diag | Select-Object -First 20
# 探针：目标成员已离开 editor.py（退出码 1 = 无命中）
Select-String -Path yate/editor.py -Pattern "def load_startup_services|def trust_cwd_extensions" ; echo "exit=$LASTEXITCODE"
```

## 六、提交

`refactor(editor): extract extension startup flows`

## 七、风险与回滚

- 本波唯一非机械改动是 test_cli 桩形状——桩按 cli 实际访问路径重建，不改断言语义
  （`--diag` 路径被走到即可）。
- `load_startup_services` 返回值语义变化（None → list[str]）只影响 editor.py 内
  extend 调用点；cli/测试丢弃返回值，与现状行为等价（见 §一取证）。
- 回滚：单提交 `git revert`。
