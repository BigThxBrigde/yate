# plan-f：抽取 ExtensionFlows（extension_flows.py）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 实测 grep 复核并更新（成员集与依赖取证不变，仅行号偏移）。

## 一、职责与迁移清单

`extension_flows.py::ExtensionFlows` 承接 editor.py 的扩展启动流（:1243-1316 附近，实测 def 起点 :1243/:1260/:1296）。

迁移成员（3 个）：

| 成员 | editor.py 行号 | 依赖取证 |
|---|---|---|
| `load_startup_services` | :1243-1258 | `load_startup_extensions`（loader, config, ext_dirs, ext_files）、`_register_configured_servers` |
| `trust_cwd_extensions` | :1260-1294 | `Path.cwd()`、`trust_workspace`、`extension_loader.load_directory`、`message` |
| `_register_configured_servers` | :1296-1316 | `extension_api.lsp` bridge、`config.language_servers` |

### 缓冲区归属裁定：`_ext_messages` 留在 Editor

它不是扩展私有状态，而是 **Editor 的前置挂载消息缓冲**：

- 种子是 yaterc 错误而非扩展消息（:315-317 `[f"yaterc: {err}" for err in self.config.errors]`）；
- `_report`（:423-428）为文档打开路径缓冲 pre-mount 告警，
  plan-d 后这些调用在 DocumentFlows 内、经注入的 `report` 回调落回此缓冲；
- `on_mount` 统一冲刷（:387-388，`; `.join 后 kind="warn"）。

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

- 装配点：`_build_models` 尾部（`extension_loader` :114 之后）；六个依赖当时全部就绪。
- `trust_cwd_extensions` 的 `message` 保留注入（`:trust` 是命令，只在挂载后可达）。
- `on_unmount` :404 `self.extension_loader.teardown_all()` **不动**——对具体协作者
  的 1:1 直调（§四交互表第 1 行），包一层 `extension_flows.teardown_all()` 反而是薄委托。

## 三、调用方改直调（grep 驱动，断言语义不变）

| 位置 | 改动 |
|---|---|
| editor.py on_mount :379 | `self.load_startup_services()` → `self._ext_messages.extend(self.extension_flows.load_startup_services())` |
| yate/cli.py:329 | `app.editor.load_startup_services()` → `app.editor.extension_flows.load_startup_services()` |
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

## 八、执行记录（wave-5 实测回填，2026-09-29）

**结果：全部门禁绿，已按 §六 提交。**

| 门禁 | 命令 | 实测结果 |
|---|---|---|
| pyright strict | `python -m pyright yate/ tests/ tools/` | **0 errors**（首跑即 0） |
| pytest 全量 | `python -m pytest tests/ -q --cov=yate --cov-fail-under=75` | 全绿，**覆盖率 90.72%** |
| 架构守护 | `python -m pytest tests/test_architecture.py -q` | **20 passed** |
| `--diag` 实测 | `python -m yate --diag` | 退出码 0，`[extensions]` 节正常渲染 |
| 冒烟 | `python -m tools.smoke_test run` | **932/932 checks，89/89 scenarios，exit 0**（82.3s） |
| 探针 | `Select-String -Path yate/editor.py -Pattern "def load_startup_services|def trust_cwd_extensions|_register_configured_servers"` | 无命中（成员已离开 editor.py） |

**行数**：editor.py 958 → **882**（numstat +12/-88）；新建 `extension_flows.py` **125** 行。

**偏离与实施要点**（相对计划文本）：

1. **行号锚点**：wave-4 后再次漂移，实测 def 起点 `load_startup_services` :882 /
   `trust_cwd_extensions` :899 / `_register_configured_servers` :935、on_mount 调用点 :414、
   cli.py :329、commands.py :128（成员集与依赖取证与计划一致）。
2. **extensions 节即文件尾**：删除该节时连带清理了文件尾 3 行历史空行，editor.py 以
   `sync_explorer_visibility` 收尾（单换行，PEP 8）。
3. **`load_startup_services` 返回 `list[str]`**：按 §一 裁定实现——loader 告警 return 给调用方，
   on_mount 内 `self._ext_messages.extend(...)`，缓冲所有权留在 Editor；headless `--diag` 丢弃
   返回值，行为与迁移前等价（实测通过）。
4. **test_cli 桩**：按计划新增 `_FakeFlows`（`load_startup_services` 返回 `[]` 并计数），
   `_FakeEditor.extension_flows` 持有之；断言改 `editor_arg.extension_flows.load_startup_services_called`，
   断言语义不变。
5. **`message` 注入为 `Callable[[str, str], None]`**：`trust_cwd_extensions` 内 4 处消息调用
   改 2 参位置形式（`"error"` / `"info"`），与 window_flows/document_flows 约定一致。
6. **规则同步**：§一 L3 枚举补 `extension_flows.py`；R11 的 editor_view 冻结清单**不含**它
   （零 editor_view 依赖，计划 §四 明确不做 R11 登记）；`UI_FROZEN_FILES` 不增条目。
