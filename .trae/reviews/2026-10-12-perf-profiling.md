---
title: enh/perf-profiling 分支 pre-review（issue IKKSHY 性能修复分支）
date: 2026-10-12
scope: branch-review
status: pass
---

# enh/perf-profiling 分支 pre-review（2026-10-12）

> 评审对象：分支 `enh/perf-profiling`（issue IKKSHY 性能分析与修复），merge-base
> `4342b2c`，7 文件 +427−44（4 代码 / 2 测试 / 1 计划文档）；master 合入
> （`a0fc004`）未触碰同批文件，评审 diff 即最终状态。
> 评审方式：`pr-review` skill（Gitee PR Review Bot 六维框架），全部门禁实测取
> 退出码，不采信文档记录。
> 修复处置：见 [perf-review-fixes-plan.md](../documents/perf-review-fixes-plan.md)
> （记录与方案互相链接，本文只记事实，不放排期）。

## 一、门禁实测

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations | 0 |
| `python -m pytest tests/ -q` | 全绿（含 28 架构用例；另有多轮压测 4/4 稳定绿） | 0 |
| 覆盖率 | 92%（≥75% 闸门） | — |
| 冒烟 | pilot 驱动的应用级测试（test_app_render / test_app_palette / test_app_explorer 等）全绿 | — |

## 二、结论

**Overall: APPROVE**（AI pre-review；合并决定归人工）。

无 BLOCKER / MAJOR。2 项 MINOR（下节），行为等价均有守卫测试锁定，不阻塞合并。

## 三、发现

### M1（MINOR）`yate/editor_view/cells.py` — `_WIDTH_CACHE` 无上界模块字典

`cell_width` 的记忆化字典（`../../yate/editor_view/cells.py:35`）无淘汰策略，
病理输入（超大去重字符流）可无界增长。缓解事实：unicodedata 分类随解释器
Unicode 表固定，映射是纯函数；实际有界于会话出现过的不同字符集合（数千级），
注释已文档化。定性为信息级——本评审仍登记，由用户指令转入闭环修复
（有界化，见方案 M1）。

### M2（MINOR）`yate/editor_view/palette.py` — `refilter` 命中分支读感变化

预降级优化把 hint 分支从 `elif` 平铺改为 early-continue 嵌套
（`../../yate/editor_view/palette.py:291-303`）。行为等价由
`_match_lowered` ≡ `fuzzy_match` parity 测试与既有 palette 回归锁定，
纯可读性问题（见方案 M2）。

## 四、正面认定

- 三处优化均以 cProfile/timeit 实测定位与验收（渲染几何 24.1→0.7 ms/帧、
  palette refilter 15.2→7.6 ms/键击），等价性守卫测试先行锁死算术契约；
- 三笔 perf 提交相互独立可单独回退；压测中暴露的预存测试竞态
  （`test_new_file_and_folder_from_explorer`）单独修复且归因清晰
  （master detached 对照取证，非本分支引入）；
- 架构边界零触碰（改动全部落在 `editor_view/*` L2 内部，R1–R13 守卫面全绿）。
