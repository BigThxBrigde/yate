# pr-review 记录：fix/lsp-uri-canonical（2026-11-24）

- 范围：`fix/lsp-uri-canonical` vs `master`（merge-base），代码 diff 共
  2 文件 +38/−7（`yate/editor_lsp/protocol.py`、`tools/smoke_test/cli.py`）；
  `.trae/documents/lsp-uri-canonical-fix-plan.md` 为配套计划文档（noise
  filter 外的行为无关文档，按事实核对不逐行评审）。
- 模式：pr-review `review`（AI 预审，人工决策）。

## 结论

**Overall: APPROVE**（无 blocker / major；minor 3 条，2 条已在本轮处置，
1 条为已登记待办）。人工仍拥有合并决策权。

## 门禁实测（主代理本会话真实运行，非推断）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings | 0 |
| `pytest tests/ -q -n auto` | 全过（仅既有 skip） | 0 |
| `pytest tests/test_architecture.py -q` | 47 例全过 | 0 |
| `python -m tools.smoke_test run --jobs 4` | 1554/1554 checks，128/128 scenarios | 0 |
| junction 复现条件 `--tag lsp-navigation` | 修复前 20/23 → 修复后 43/43 | 0/1→0 |

（全量 pytest/冒烟运行于 afb3603d；其后仅 f20b7592 与本轮 docs 改动，
不触代码。）

## 维度结论（六维全查，无空转）

1. **功能与正确性**：切片式盘符判定对空串/短串安全（`s[:1]` 恒不越界）；
   canonical 形式变化（小写盘符 → 大写）的两类调用方（manager URI 键两侧
   均 canonical 化、smoke 场景 fixture URI）已实测一致；`_resolved_tmp`
   对 run/snapshot/compare 三站点全覆盖，基线不含绝对路径故 snapshot/
   compare 无副作用。
2. **安全**：无新增输入面/密钥/注入路径；路径仅来自 `TemporaryDirectory`。
3. **性能**：`resolve()` 每场景一次、O(路径长度)，可忽略。
4. **可维护性**：docstring 完整；见 minor-1。
5. **架构边界**：无新 import、无 Protocol/Any/TYPE_CHECKING/type-ignore、
   依赖方向合规（tools 层不反向依赖 yate 运行时）。
6. **硬门禁**：见上表，全绿。

## 发现清单

- **[MINOR] 计划文档含真实机器路径（已修复）**：第 34/88/144 行的
  `RUNNER~1` 家目录示例与 junction 探针绝对路径违反「文档不得含本地
  物理路径」规则；已改写为可移植措辞（见本轮 docs 提交）。
- **[MINOR] 盘符判定谓词在 protocol.py 内 4 处重复（已登记待办）**：
  `_url_path_to_pathname` / `uri_to_path` / `canonical_uri` 两分支各自
  内联同一「单 ASCII 字母 + 冒号」判定；建议后续抽 `_is_ascii_drive_at`
  私有助手统一。非阻塞，本 PR 不扩散重构。
- **[MINOR] canonical 透传边界无钉死用例（已登记待办）**：`untitled:`
  透传、POSIX 非盘符路径透传、空 URI 目前靠 CI 双平台矩阵隐式覆盖；
  建议后续补 3 个确定性单测。非阻塞。

## Strengths

- 两处修复均为最小对症改动：`canonical_uri` 对非 `file` scheme 与普通
  POSIX 路径零影响面；`_resolved_tmp` 单点根修所有现存与未来场景。
- `_resolved_tmp` docstring 完整记录了 CI 失败根因链（8.3 短 TEMP vs
  `path_to_uri` 的 `resolve()` 展开），后人可直接理解为何必须 resolve。
- `canonical_uri` 注释显式登记 POSIX `/d:/` 固有取舍，避免被误当疏漏。
