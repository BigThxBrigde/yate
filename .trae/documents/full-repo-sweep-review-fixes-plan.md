# 全仓库扫描修复：评审/门禁修复计划

> **实施状态**：✅ 已实施 —— 2026-11-20（主代理门禁抓到一处回归；已修复并重新验证）

父计划：[full-repo-sweep-plan.md](full-repo-sweep-plan.md)。

## 触发原因

主代理的最终 `pytest tests/ -q -n auto` 门禁在 `tests/test_cli.py::test_diag_prints_report_without_running_tui` 处失败，发生在 R3 诊断快照改动之后：`_FakeEditor` 未暴露新的 L4 快照构造器读取的六个字段，因此 `cli.py` 抛出 `AttributeError: '_FakeEditor' object has no attribute 'config'`。这是测试替身中的真实回归，而非时序 flake。

## 发现项

- `[major]` `tests/test_cli.py:55-71,381-399` —— CLI `--diag` 契约
  从“将 Editor 传给 `format_report`”改为“从 Editor 构造 `DiagnosticsInput`”，
  但假编辑器和调用断言仍然钉住旧契约。
  证据：`PYTEST_AUTO=1`、`FAILED tests/test_cli.py::test_diag_prints_report_without_running_tui`、
  `yate/cli.py:521` 处的 `AttributeError: '_FakeEditor' object has no attribute 'config'`。

## 第二项发现项（自审）

- `[minor]` `yate/diagnostics.py:55`、`yate/cli.py:521`、`tests/test_diagnostics.py:52-59` ——
  `DiagnosticsInput` 虽被冻结，但 `lsp_states` 持有普通 `dict`，因此消费者
  可以篡改“快照”。已将该字段改为 `Mapping[str, ServerState]`，并在两处构造点
  将状态映射包装为 `MappingProxyType`；只读测试现在断言篡改会抛出 `TypeError`。

## 修复（单波次）

独占文件：`tests/test_cli.py`、`yate/diagnostics.py`、`yate/cli.py`、
`tests/test_diagnostics.py`。

1. 为 `_FakeEditor` 增加 `config`、`ext_dirs`、`ext_files`、`extension_loader.loaded`、
   `lsp.configs()` 和 `lsp.states()`（小型私有替身，不引入新的 Protocol）。
2. 断言 `format_report` 收到一个字段为冻结编辑器值的 `DiagnosticsInput`，
   同时保留现有检查，即扩展加载和 LSP 注册均已运行。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -q
.venv\Scripts\python.exe -m pyright tests/test_cli.py
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
```

两条针对性命令均 exit 0；全量门禁结果记录在父计划的执行日志中。
