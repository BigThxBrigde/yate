# 2026-11-20 全仓库扫描修复：评审记录

- 范围：`master` `ebe8fee6` -> 分支 `feature/fix-full-repo-sweep` HEAD `8a247d98`，涵盖 [../documents/full-repo-sweep-issue-brief.md](../documents/full-repo-sweep-issue-brief.md) 的全部 14 个发现项。
- 计划：[../documents/full-repo-sweep-plan.md](../documents/full-repo-sweep-plan.md) 与 [../documents/full-repo-sweep-plans/overview.md](../documents/full-repo-sweep-plans/overview.md)。
- 评审者 spawn：`code-review-expert` 在三次进度探活中超过 30 分钟既未产出报告也未写文件；按 `subagent-workflow.md` §五 判定为零产出并关闭。此处记录的自审由主代理执行，全部门禁均独立重跑。

## 发现项与处置

| # | 严重程度 | 位置 | 发现项 | 处置 |
|---|---|---|---|---|
| 1 | `[major]` | `../../tests/test_cli.py:55-71,381-399`（已修复） | R3 将快照构造移到 `cli.py` 后，`--diag` 测试替身缺少 `config`，导致全量套件门禁在 `../../yate/cli.py:521` 处以 `AttributeError: '_FakeEditor' object has no attribute 'config'` 失败。 | 在 `7b59eccd` 中修复：假编辑器暴露六个冻结字段；断言现检查 `DiagnosticsInput` 内容。针对性 pytest 与 pyright 退出码 0；全量门禁全绿。 |
| 2 | `[minor]` | `../../yate/diagnostics.py:55`、`../../yate/cli.py:521`（已修复） | `DiagnosticsInput` 已冻结，但其 `lsp_states` 字典仍可变，与"只读快照"矛盾。 | 在 `8a247d98` 中修复：字段类型改为 `Mapping[str, ServerState]`，两处构造点均用 `MappingProxyType` 包装状态；只读测试断言修改时抛出 `TypeError`。 |
| 3 | `[minor]` | `../../yate/editor_core/diff.py`、`../../tests/test_editor_core_diff.py`（波次 2 修复） | P2 执行者引入了私有导入并加了 `pyright: ignore` 抑制。 | 已替换为有文档说明的公开测试接缝及 `getattr`/`cast` spy；strict pyright 零诊断且无抑制。 |
| 4 | `[minor]` | `../../yate/services/extensions/bridges.py`（波次 4 修复） | R1 执行者在波次中途停止，遗留旧模块仍在且无兼容性测试。 | 主代理删除旧文件，新增 `../../tests/test_extension_bridges_package.py`，并验证全部四个直接导入的测试模块及冻结的门面。 |

无阻塞项或严重项残留。该 issue 的四个 P3 疑点仍未修复，子计划 overview 中给出了明确的 profiler/真实负载理由。

## 自我批评

上述每一项在记录前都在引用位置重读；发现项 1 的严重程度确认为 major，因为它破坏了全量套件门禁；发现项 2 从 major 降为 minor，因为它只影响内部快照的防御质量；没有候选被删除。对正确性、边界、异常处理、并发、性能、类型与覆盖率的反向扫描未发现额外项：P1 等价性、P2 零长度插入、B1/B2 错误路径、B3 双模式覆盖、R14 门面名称、headless 诊断导入与 ignore-cache 语义均已由测试钉定。

## 门禁（主代理实测）

| 门禁 | 结果 / 退出码 |
|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations / 0 |
| `pytest tests/ -q -n auto` | 退出码 0 |
| `pytest tests/test_architecture.py -q` | 46 tests / 退出码 0 |
| coverage `--cov-fail-under=75 -n auto` | 3981 passed / 10 skipped, 93.15% / 退出码 0 |
| coverage `--cov-fail-under=75 -n 1` | 3981 passed / 10 skipped, 93.15% / 退出码 0 |
| `tools.smoke_test run --jobs 4` | 124/124 scenarios, 1511/1511 checks, 82.09 s / 退出码 0 |
| `tools.changelog check` | 退出码 0（`unreleased` 滞后 174 笔提交是生成器行为） |

两次中间的 `-n 1` 覆盖率运行退出码为 1，仅因本地 safe-delete 钩子拦截了 pytest 的批量清理（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`）；使用唯一 `COVERAGE_FILE` 的复跑干净，即为记录的最终结果。
