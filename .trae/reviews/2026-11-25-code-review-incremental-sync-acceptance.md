# 2026-11-25 code-review · `feature/enh-lsp-incremental-sync`（TRAE-code-review 轮）

> 通用代码审查轮（TRAE-code-review skill），与同日的 pr-review 轮（见
> [`2026-11-25-pr-review-incremental-sync-acceptance.md`](2026-11-25-pr-review-incremental-sync-acceptance.md)）相互独立；
> 本记录只陈述事实，不代替合并决定。
> 主计划：[`../documents/lsp-incremental-sync-acceptance-plan.md`](../documents/lsp-incremental-sync-acceptance-plan.md)

Overall: **APPROVE**（0 BLOCKER / 0 MAJOR / 1 MINOR，当轮闭环）

## 一、范围与基线

- 审查对象：分支 `feature/enh-lsp-incremental-sync` 对 `master` 的 merge-base diff；
  merge-base `b97a695c`（即当时 `master` HEAD，分支无落后）；起点 HEAD `986e0861`。
- 改动面：11 笔提交，10 文件 +1001−41；代码改动仅 `tests/test_lsp.py`（+397）与
  `tests/test_lsp_diff.py`（+39−4 有效行），其余为计划/评审文档与规则文本（`.md` 按 skill 规则跳过）。
- 意图归纳：为 LSP 增量同步补验收级测试——wire 级帧捕获（生产 `_write_raw` 边界）、
  体积解耦（同 URI 200/4000 行帧长相等）、astral/跨行重放与 Full 模式逐字节对比、
  `LspError`/`OSError` 参数化重试、Full 关闭竞态。

## 二、方法与实证

- 主审查：通读两份测试 diff 全文并对照生产实现
  （`yate/editor_lsp/sync.py`、`yate/editor_lsp/diff.py`、`yate/editor_lsp/manager.py`、
  `yate/editor_lsp/client.py`），手工推演 UTF-16 列计算、纯插入锚点、锁竞态与 `_close_uri` 清理顺序。
- 交叉验证：2 个独立子代理并行复核全部候选 issue，共识计分（2/2 采纳、0/2 剔除）。
- 定向实测（worktree 自有 `.venv`，`import yate` 自证指向本工作树）：
  `pytest tests/test_lsp.py tests/test_lsp_diff.py`（97 passed）、
  `pyright tests/test_lsp.py tests/test_lsp_diff.py`（0 诊断）、
  修复后 `pytest tests/test_lsp.py tests/test_lsp_real_server.py tests/test_lsp_diff.py`（99 passed）。

## 三、发现与处置

| # | 级别 | 发现 | 处置 |
|---|---|---|---|
| 1 | MINOR | [`tests/test_lsp.py`](../../tests/test_lsp.py):284 `_capture_wire_frames` 的 `# noqa: Any` 注释独立成行、脱离 `cast(Any, client)` 所在行，偏离 [`python-coding-style.md`](../../rules/python-coding-style.md) §3.3「行内 `# noqa: Any - <reason>`」约定；master 既有先例 [`tests/test_lsp_real_server.py`](../../tests/test_lsp_real_server.py):109 同病 | 按「修同族不修单点」两处一并改为行尾注释，提交 `94174a6f`；定向 pyright 0 / pytest 99 passed 复验 |
| — | 剔除 | 「Full 关闭竞态用例 `release.set()` 后固定 `for _ in range(10): asyncio.sleep(0)` 属时序敏感写法」 | 0/2 验证员确认：FakeClient 纯内存、协作式调度确定性充分（实测仅需 2 个事件循环周期，10 次有 5 倍裕量），且为仓库既有惯例；不落入时序纪律条款，排除 |

## 四、结论

- 0 BLOCKER / 0 MAJOR / 1 MINOR（当轮修复）。修复后全量门禁由主代理亲跑，见主计划 §10.6。
- 未推送、未合入 `master`（按规则须用户显式要求）。
