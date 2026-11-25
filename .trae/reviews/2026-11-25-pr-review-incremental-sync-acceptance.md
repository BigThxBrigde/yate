# 2026-11-25 pr-review · `feature/enh-lsp-incremental-sync`（IKXQFK）

> AI 预评审，人工决策；本记录不代替合并决定。
> 主计划：[`../documents/lsp-incremental-sync-acceptance-plan.md`](../documents/lsp-incremental-sync-acceptance-plan.md)
> 子计划总纲：[`../documents/lsp-incremental-sync-acceptance-plans/overview.md`](../documents/lsp-incremental-sync-acceptance-plans/overview.md)

Overall: **APPROVE**（0 BLOCKER / 0 MAJOR；主代理自审 1 MINOR 已修，迟到交付的 `pr-b` 报告 8 MINOR 经复核 3 修 5 登记）

## 一、范围与基线

- 模式：`pr-review` skill `review`（默认），base 回退 `master`。
- merge-base `1f0ee5a0`；评审起点 HEAD `1f967488`（7 文件 +905−5），修复后终态 HEAD `e67f5f23`（追加 2 行删除）。
- 提交：`b12e0598` → `783c31c3` → `573e9846` → `ab6a87ea` → `64d3f306` → `1f967488` → `e67f5f23`。
- `git diff --check master...HEAD` 退出码 0；`git merge-tree <base> master HEAD` 无冲突输出；`yate/` 零 diff。
- `pr-a`（功能/门禁）在约 32 分钟窗口内无报告，仅 shutdown ack，按 `task-orchestration.md` §三 记**零产出**；`pr-b`（文档/合并就绪）在团队删除后**迟到交付完整报告**（APPROVE / 0 blocker / 0 major / 8 minor），已逐条回读复核。团队已 shutdown + delete，未遗留临时文件。主代理按 skill 六维度亲自复核并实测门禁。

## 二、六维度核对

| 维度 | 结论 |
|---|---|
| 功能与正确性 | [`tests/test_lsp.py`](../../tests/test_lsp.py) 的 wire 帧捕获走生产 `_write_raw`/`protocol.encode_message`；增量断言 `range`/`rangeLength`/`text` 且排除全文；体积用例用同一 URI 对比 200/4000 行帧长相等且 `<1024`；astral/跨行重放与 Full 模式逐字节一致；`LspError` 重试与 Full 关闭竞态独立覆盖。未见恒真断言、错误 UTF-16 列假设或资源泄漏。 |
| 安全 | 无新增外部输入、无 subprocess/shell、无序列化不可信数据；测试仅用 `tmp_path`。 |
| 性能 | 4000 行字符串一次性构造、不进渲染；wire 轮询有界 2s；无 O(n²) 热路径。 |
| 可维护性 | [`tests/test_lsp_diff.py`](../../tests/test_lsp_diff.py) 新增 2 条直接单测；docstring 与类型注解齐全；发现 1 处冗余列表（下节），已修。 |
| 架构边界 | 产品源码零 diff；测试夹具可选参数不属于产品 API；47 个架构守卫全绿；无新增 `Protocol`/`TYPE_CHECKING`/绝禁命名。 |
| 硬门禁 | 终态 HEAD 六项全部退出码 0，见第四节。 |

## 三、发现与处置

### MINOR（当轮闭环）

**[MINOR] [`tests/test_lsp.py`](../../tests/test_lsp.py):3018 — wire 助手中的冗余 `managers` 列表**
Problem: `_drive_manager_with_harness` 创建 `managers: list[LspManager] = []` 并 `append(mgr)`，但读取路径不存在（与既有 `_sync_session` 的 `managers[0]` 回调用法不同），属死代码，增加维护噪声。
Fix: 删除 `managers` 声明与 `managers.append(mgr)` 两行，提交 `e67f5f23`；随后 targeted pytest（2/2）+ pyright（0）复验通过。

### 登记项（非代码缺陷）

### 迟到交付的 `pr-b` 报告：8 MINOR 分流

| # | 发现 | 处置 |
|---|---|---|
| 1 | `wire-shape-plan-b.md:10` 把测试侧断言写成 `diff.py:245-252` | ✅ 改为 `tests/test_lsp_diff.py:245-252` 并注明 diff.py 只构造 patch |
| 2 | `LspError` 与 `OSError` 重试用例近乎重复 | ➖ 登记：断言侧重不同且 `sync.py:148` 单分支，参数化留作后续维护 |
| 3 | 差分重放用例与既有护栏脚手架重复约 60 行 | ➖ 登记：增量断言有独立价值，抽 helper 留作后续维护 |
| 4 | `_drive_manager_with_harness` 死变量 `managers` | ✅ 与上文主代理发现重合，`e67f5f23` 已修 |
| 5 | 4 笔 `test(lsp):` 不在规则允许值内（master 已有 14 处先例） | ➖ 登记：规则文本滞后，不改历史提交，建议另案追加 `test` 类型 |
| 6 | 分支落后 master 1 笔（`b97a695c`），门禁数字基于旧树 | ✅ `1098c28e` 已合并 master，合并后六门禁全部复跑通过 |
| 7 | 评审索引缺本次条目（报告时点成立） | ✅ 报告送达前已落盘记录并登记 README（本文件） |
| 8 | plan-c 跨行补丁预期与实测零宽插入不符且未登记 | ✅ 改写 plan-c §2.2 并在主计划 §九第 4 条登记偏差 |

规划阶段零产出见主计划 §〇/§十；`pr-a` 零产出见第一节。无 BLOCKER / MAJOR；`pr-b` 自审撤回的第 9 条（提交表可读性挑刺）未被采纳。

## 四、硬门禁（合并 master 后终态 `1098c28e`，主代理亲跑）

| 命令 | 实测结果 | 退出码 |
|---|---|---|
| `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ -q -n 4` | 全绿（10 skipped） | 0 |
| `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 47 passed | 0 |
| `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-report=term --cov-fail-under=75 -n 4` | Total coverage 92.74%；4060 passed, 10 skipped | 0 |
| `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | 128/128 scenarios passed（82.06s） | 0 |
| `.venv\Scripts\python.exe -m tools.changelog check` | released sections up to date；unreleased 为发布时刷新惯例 | 0 |

注：`-n auto` 在本机两次因工具空闲超时被取消，改用等价的 `-n 4` 采样完成同一全量套件；此前在 `1f967488` 上 `-n auto` 已实测退出码 0。未把工具超时记成测试失败。

## 五、自我批判

- 逐条反证：wire 帧断言确实经过生产编码器而非测试自造 dict；体积断言比较的是完整通知帧字节数且 URI 相同；重放断言每步与 Full 模式交叉核对；关闭竞态断言关闭后编辑未上线。
- 误报排查：初拟将「评审员零产出」「覆盖率小数波动」列为缺陷，复核后归为过程登记/非缺陷；`pr-b` 迟到报告中的提交类型项实证 master 已有 14 处先例，按观察项登记而非要求改历史。
- 迟到报告复核：逐条回读 `pr-b` 8 条发现，3 条确属实并修（引用错文件、plan-c 预期、合并前同步），2 条重复测试属维护成本只登记，1 条死变量与自审重合，1 条索引报告时点已失效，1 条规则滞后另案。
- 漏报自查：重扫 `yate/` diff 为空、计划文档相对链接全部可解析、无本机绝对路径、changelog 未手改。
- 结论登记：APPROVE，合并决定仍归人工。

## 六、Strengths

- 以纯测试补强达成 issue 五条协议级验收，产品行为零风险。
- 帧级证据而非 mock 层自证，体积解耦用同 URI 对照，避免全文断言被 JSON 转义绕过。
- 子计划拆分与波次边界清晰，门禁数字、子代理零产出与自审 minor 全部回填可追溯。
