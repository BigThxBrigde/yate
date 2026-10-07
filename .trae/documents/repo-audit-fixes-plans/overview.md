# repo-audit-fixes 子计划总纲

> 主计划：[`../repo-audit-fixes-plan.md`](../repo-audit-fixes-plan.md)（处置决策 / 选型论证 / 风险 / 就绪清单均以主计划为准）。
> 来源评审：[`../../reviews/2026-10-07-repo-architecture-audit.md`](../../reviews/2026-10-07-repo-architecture-audit.md)。

## 波次表（调度唯一依据，批准后不得执行中重排）

| 波次 | 子计划 | 执行者 | A 条目 | 串行依据 |
|---|---|---|---|---|
| wave-1 | plan-a 规则与 docstring 修订 | 主代理 | A3, A11, A18, A20 登记 | — |
| wave-1 | plan-b 测试守护与覆盖说明 | 子代理 | A6, A17 | — |
| wave-1 | plan-c 中文翻译清偿 | 子代理 | A5-① | — |
| wave-1 | plan-d 文档资产迁移 | 子代理 | A15 | — |
| wave-2 | plan-b re-export 成文例外与收敛 | 主代理 | A1 | 动 editor.py/flows import 面，先于 wave-3 |
| wave-2 | plan-b keyproto 层级收敛 | 主代理 | A2 | 与前者文件不重叠 |
| wave-3 | plan-c flows/ 迁移与命名统一 | 主代理 | A10, §六 | 依赖 wave-2 完成（editor.py import 面） |
| wave-3 | plan-c 用户文档分工成文 | 主代理 | A16 | 与迁移文件不重叠 |
| wave-4 | plan-d 配置域重构 | 主代理 | A8, A9, A20 复核 | 依赖 wave-3（prompt_completion.py 新路径） |
| wave-4 | plan-d 扩展半注册机制化 | 主代理 | A13 | 与配置域文件不重叠 |
| wave-5 | plan-e CI 门禁补齐 | 子代理 | A4, A14, A5-② | 依赖 wave-1 plan-c（清偿完毕才开 --require-zh） |
| wave-5 | plan-e 巨型测试拆分 | 子代理 | A7 | 与 CI 文件不重叠 |
| wave-6 | 收尾 | 主代理 | 全量门禁 + 回填 + 提交 | 全部子计划验收通过后 |

```mermaid
flowchart LR
    W1["wave-1: a∥b∥c∥d"] --> W2["wave-2: e∥f"] --> W3["wave-3: g∥h"] --> W4["wave-4: i∥j"] --> W5["wave-5: k∥l"] --> W6["wave-6 收尾"]
```

## 索引

- [repo-audit-fixes-rules-docstring-plan-a.md](repo-audit-fixes-rules-docstring-plan-a.md)（wave-1，主代理）
- [repo-audit-fixes-tests-guard-plan-a.md](repo-audit-fixes-tests-guard-plan-a.md)（wave-1，子代理）
- [repo-audit-fixes-changelog-zh-plan-a.md](repo-audit-fixes-changelog-zh-plan-a.md)（wave-1，子代理）
- [repo-audit-fixes-assets-plan-a.md](repo-audit-fixes-assets-plan-a.md)（wave-1，子代理）
- [repo-audit-fixes-reexports-plan-b.md](repo-audit-fixes-reexports-plan-b.md)（wave-2，主代理）
- [repo-audit-fixes-keyproto-plan-b.md](repo-audit-fixes-keyproto-plan-b.md)（wave-2，主代理）
- [repo-audit-fixes-flows-package-plan-c.md](repo-audit-fixes-flows-package-plan-c.md)（wave-3，主代理）
- [repo-audit-fixes-docs-split-plan-c.md](repo-audit-fixes-docs-split-plan-c.md)（wave-3，主代理）
- [repo-audit-fixes-config-options-plan-d.md](repo-audit-fixes-config-options-plan-d.md)（wave-4，主代理）
- [repo-audit-fixes-extension-rollback-plan-d.md](repo-audit-fixes-extension-rollback-plan-d.md)（wave-4，主代理）
- [repo-audit-fixes-ci-plan-e.md](repo-audit-fixes-ci-plan-e.md)（wave-5，子代理）
- [repo-audit-fixes-test-split-plan-e.md](repo-audit-fixes-test-split-plan-e.md)（wave-5，子代理）
