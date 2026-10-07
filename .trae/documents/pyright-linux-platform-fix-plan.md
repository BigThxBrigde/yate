# pyright Linux 平台报错修复计划（pipeline-145）

分支：`fix/pipeline-145`。状态：**已实施**（本文档为最终执行记录）。

## 一、背景与根因（调研结论）

CI 的 `lint` job（`.github/workflows/test.yml`，`runs-on: ubuntu-latest`）跑
`pyright`（strict 零诊断门禁）报 **315 errors**；本地 Windows 同命令 0 错误。
根因：pyright 对 **Windows 专属 stdlib 存根**（`ctypes.WinDLL` / `wintypes` /
`winreg`，typeshed 侧仅 Windows 会话可见）的解析按**会话平台**判定，会话平台
未显式指定时跟随**宿主 OS**——CI 宿主是 Linux，于是：

1. `yate/editor_term/pty_proc.py`（约 280 错）：模块级 `_ConPty` 类引用
   `if os.name == "nt":` 块内绑定的 `ctypes` / `wintypes` / `_COORD` 等，
   Linux 分析下按未定义处理（基线规则分布：reportUndefinedVariable 111、
   reportUnknownMemberType 154、reportUnknownVariableType 30、
   reportAttributeAccessIssue 13、reportUnknownArgumentType 6、
   reportRedeclaration 1）；
2. `yate/services/fonts.py`（约 31 错）：函数内 `import winreg` 在 Linux
   会话下成员不可见，逐处 Unknown / attribute 级联；
3. `yate/keyproto/driver_windows.py`（4 错）：textual `drivers/win32.py` 的
   `KERNEL32` / `GetStdHandle` 源自 `ctypes.WinDLL`，Linux 会话下 Unknown。

本地复现：`python -m pyright --pythonplatform Linux` → 315 errors，与 CI
逐条一致。Gitee 管道只跑 pytest，不受影响。

## 二、目标与非目标

**目标**：CI lint 在 ubuntu 上恢复零诊断；最小修改、不触碰代码与架构分层。

**非目标**：本轮不改 `yate/` 源码；Linux 会话下的 lint（POSIX 分支静态检查）
列为后续工作（已备注在 workflow 注释中）。

## 三、方案决策（含两轮往返的实证）

- **最终采用：方案 D——CI lint 步骤显式 `pyright --pythonplatform Windows`**。
  一行管道改动；旗标对存根门控的裁决力已被实证——在 Windows 宿主上加
  `--pythonplatform Linux` 即完整复现 CI 的 315 错（旗标 > 宿主），对称地
  在 Linux 宿主上加 `--pythonplatform Windows` 即得到与本地一致的全绿语义。
  workflow 注释中备注：**Linux 平台 lint 为将来工作**，前提是 Windows 专属
  模块先能在 POSIX 分析会话下干净过检。
- **方案 A（代码级双平台收口）——已实施后整体撤回**：`_ConPty` 迁入 nt 块
  （311 行机械重缩进）、fonts.py 三处 `import winreg` 改
  `importlib.import_module`（并登记 `tests/test_pack_spec.py` 的
  `_REVIEWED_DYNAMIC_IMPORTS` 治理表）、`ctypes.windll` 与
  `win32.GetStdHandle` / `win32.KERNEL32` 改 `getattr` 字面量。实测双平台
  pyright 均 0 错误，手法全部经探针验证（`import_module`→ModuleType、
  `getattr(literal)`、`cast(ModuleType)` 三种形态在两个会话平台下均零诊断；
  注意 `cast(ModuleType, win32.KERNEL32)` 无法抑制 cast 实参内部的
  Unknown 诊断，须用 `getattr`）。**按用户决定撤回**，留作 Linux lint
  后续项的成熟路线图（可直接按上述手法重做）。
- **方案 B/C/E/F（否决，实证见第一轮记录）**：`[tool.pyright]` 顶层 /
  `executionEnvironments` 的 `pythonPlatform` 只影响 `sys.platform` /
  `os.name` 分支裁剪，**钉不住 typeshed 存根可见性**；lint job 迁
  `windows-latest` 徒增成本且同样收缩检查面。

## 四、实施内容（最终 diff）

仅改 `.github/workflows/test.yml` 的 lint 步骤一行（附机制注释与
Linux 后续项备注）：

```yaml
run: pyright --pythonplatform Windows
```

`pyproject.toml` 与 `yate/`、`tests/` 无净变更（方案 A 已整体还原）。

## 五、验收结果

| 门禁 | 命令 | 结果 |
|---|---|---|
| 复现基线 | `pyright --pythonplatform Linux` | 315 errors（与 CI 一致） |
| 修复后（CI 同义命令） | `pyright --pythonplatform Windows`（全仓 include 集） | **0 errors** |
| 本地门禁（方案 A 验证期实测后撤回） | `pyright --pythonplatform Linux` + `pyright` | 均 0 errors |
| 测试套件 | 未重跑：最终净变更为纯管道+文档（方案 A 期间的代码改动已全部还原，代码与 master 零差异） | 不适用 |

## 六、风险与回滚

- 风险：POSIX 分支从此无静态检查（CI 与本地均按 Windows 语义分析）。缓解：
  这些分支本来只在 Linux 运行时执行，Linux pytest leg（ubuntu 矩阵，
  3.12/3.13）继续运行时覆盖；Linux 静态检查作为后续项单独立项。
- 风险：pyright 旗标大小写敏感（`linux` 小写被拒），值必须用首字母大写
  `Windows`（与 CLI 报错文案一致）。
- 回滚：单 commit，`git revert` 即恢复原管道。
