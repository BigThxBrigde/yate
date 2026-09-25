# SP7 — services 与日志（N27 N28 N31）

> 波次二 · 规模 S · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/services/extensions.py`（N27，导入排序）
- `yate/services/trust.py`（N28，`Path | None` → `Optional[Path]`）
- `yate/logs.py`（N31，`warn()` stderr 为 None 时静默丢弃）

**测试：** `tests/test_extensions.py`、`tests/test_trust.py`、`tests/test_tracing.py`（仅新增；
N27 纯排序无测试）

不许动其它任何文件；范围外发现上报主代理。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N27: extensions.py 内部导入组非字母序——已核实 `yate.registries`
错位于 `yate.services.trust` 之后；N28: trust.py:45/68/115 三处 `Path | None`；N31: logs.py
`warn()` 在 `sys.stderr is None` 时 `print(file=None)` 回退 stdout）。P1 已改过 trust.py
（S39 最小加固 + 返回 bool）与 logs.py（S36 文件名 pid），以当前代码为基准。

## 条目执行

### N27 — extensions.py 导入排序

1. **输入**：P2 原文 N27 行。
2. **步骤**：仅调整组内顺序为字母序（`yate.registries` 提到 `yate.services.trust` 前）；
   不合并组、不增删导入。
3. **验收**：pyright 0 诊断；`test_extensions.py` 全绿；diff 仅导入顺序。

### N28 — trust.py 统一 `Optional[X]`

1. **输入**：P2 原文 N28 行（规范 §3.2：用 `Optional[X]` 而非 `X | None`）。
2. **步骤**：三处签名（`load_trusted_workspaces` / `trust_workspace` / `is_trusted`）替换；
   `Optional` 已在导入内则不新增 import。
3. **验收**：pyright 0 诊断；`test_trust.py` 全绿（含 S39 回填的 `is True` / `is False` 契约断言）。

### N31 — `warn()` 在 stderr 不可用时静默丢弃

1. **输入**：P2 原文 N31 行（`if sys.stderr is not None:` 再 print，与 docstring「Never raises」一致）。
2. **步骤**：读 `warn()` 现实现与 docstring 承诺；加守卫分支；docstring 补一句 stderr 不可用时的行为。
3. **输出**：`sys.stderr = None`（pythonw 场景）下 `warn()` 不抛、不写 stdout。
4. **验收**：`test_tracing.py` 新增用例——monkeypatch `sys.stderr = None` → 调 `warn()`
   断言不抛且 capsys 无 stdout 输出；既有 tracing 用例全绿。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/services/extensions.py yate/services/trust.py yate/logs.py tests/test_extensions.py tests/test_trust.py tests/test_tracing.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_extensions.py tests/test_trust.py tests/test_tracing.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + 校准记录

## 校准记录

（2026-09-25 实施）

- N28 行号漂移：P2 原文锚点 `trust.py:27,50,71` 为 P1 改前旧号，实测三处 `Path | None`
  在 45/68/115（实施后签名位于 46/69/116）；补 `from typing import Optional` 导入。
- N27 排序幅度扩为全组字母序：仅把 `registries` 提到 `trust` 前会留下 `services.trust`
  在 `services.shell` 之前的次生乱序；最终顺序 `paths → registries → shell → trust →
  workspace → session`，diff 仅导入顺序。
- N31：`warn()` 入口 `if sys.stderr is None: return` + docstring 补 pythonw 行为；
  守卫 `test_warn_silently_drops_output_when_stderr_is_none`（monkeypatch，capsys 双空断言）。
