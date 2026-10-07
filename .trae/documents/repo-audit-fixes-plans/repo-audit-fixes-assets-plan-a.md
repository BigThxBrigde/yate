# 子计划 plan-d：文档资产迁移（A15）

> 所属波次：**wave-1**（与 rules-docstring / tests-guard / changelog-zh 文件不重叠，可并行）。
> 执行者：**子代理**（`.trae/`、`tools/`、tests 注释，不改产品源码逻辑）。
> 来源：评审 A15。

## 一、输入

- `.trae/documents/fancy-sym-plans/roster.svg`（633 KB，外围最大单文件，为 `.trae/documents` 内非文档资产）；
- `.trae/documents/keybinding-fix-wt-plans/pb6_real_input_harness.py`（13.87 KB）、`verify_matrix.ps1`（6.1 KB）、`win32im_probe.py`（2.24 KB）；
- 引用面实测（主计划 §一）：**无任何文档引用**这 4 个文件的当前路径；唯一代码引用是 `tests/test_keyproto.py:117` 注释提到 `keybinding-fix-wt-plans/win32im_probe.py`（作为数据来源说明）；`tools/pack` 相关的 `roster.svg` 引用（`tools/pack/rosters.py:24`、`yate/docs/yaterc.*.md`）指的是**工具输出到仓库根的产物**，与本次迁移无关，不得改动。

## 二、独占文件清单

1. 迁出（git mv）：`.trae/documents/fancy-sym-plans/roster.svg` → `.trae/assets/fancy-sym/roster.svg`（`.trae/assets/` 为新建目录）
2. 迁出（git mv）：`.trae/documents/keybinding-fix-wt-plans/pb6_real_input_harness.py` → `tools/probes/pb6_real_input_harness.py`
3. 迁出（git mv）：`.trae/documents/keybinding-fix-wt-plans/verify_matrix.ps1` → `tools/probes/verify_matrix.ps1`
4. 迁出（git mv）：`.trae/documents/keybinding-fix-wt-plans/win32im_probe.py` → `tools/probes/win32im_probe.py`
5. 更新：`tests/test_keyproto.py:117` 注释中的路径 → `tools/probes/win32im_probe.py`
6. 新建：`tools/probes/` 目录说明（若该目录以包形式存在需 `__init__.py`；这 3 个文件是一次性探针/harness 脚本，不参与 pyright strict 门禁——若 pyright 配置 include `tools` 全量导致探针文件报诊断，在 `pyproject.toml` `[tool.pyright]` `exclude` 追加 `"tools/probes/**"` 并在本文件记录该偏离）

注意：`pyproject.toml` 归主代理管辖，子代理如需修改 exclude，先在报告中申请，由主代理落改（subagent-workflow §一.3）。

## 三、执行步骤

1. `git mv` 逐项迁移（保留历史）；
2. 更新 `tests/test_keyproto.py:117` 注释路径；
3. 全仓 grep 旧路径确认零残留：
   ```powershell
   Select-String -Path **\*.md,**\*.py -Pattern "fancy-sym-plans/roster.svg","keybinding-fix-wt-plans/pb6_real_input_harness","keybinding-fix-wt-plans/verify_matrix","keybinding-fix-wt-plans/win32im_probe"
   ```
   （历史计划文档中提及这些脚本**文件名本身**的叙述可保留；仅当前路径引用必须迁移。）
4. 在 `.trae/assets/` 不需要 README（目录自明）；`tools/probes/` 三个文件保留原样不改造。

## 四、验证方案

- 验证目标：文档树纯度（`.trae/documents/` 只含 `.md`），资产可追溯（git mv 保留历史）。
- 命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
git status --short
```

- 手工验证：`Get-ChildItem .trae/documents -Recurse -Include *.svg,*.ps1,*.py` 零结果；`git log --follow tools/probes/win32im_probe.py` 可追溯到原位置。

## 五、风险与回滚

- 风险：极低——引用面已实测为空。若未来有计划文档需要引用 roster.svg，以新路径 `.trae/assets/fancy-sym/roster.svg` 为准。
- 回滚：`git mv` 反向迁移即可。
