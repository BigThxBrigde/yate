# Gitee PR !62 AI 队友评审（callable-aliases）— 2026-10-07

> 来源：[PR !62 评论 note 51465923](https://gitee.com/jermaine/yate/pulls/62#note_51465923_conversation_191474743)
> （AI 队友"PR观察者"，响应 `jermaine` 的 `/review` 指令，2026-10-07 19:45 触发 / 19:53 完成，
> 正文经 Gitee API 取回；PR !62 即 worktree 分支 `ref/callable-aliases`，关联 issue IKJUWP）。
> 评审对象：回调别名化全量 6 提交（`yate/` 38 文件的类型重构 + 架构守护第 25 个用例 +
> 冒烟存量失败修复 + 规则/评审文档同步）。

## 一、评审结论（机器人自评）

**⚠️ 无阻断项，但发现 2 个改进建议，可优化后合并。风险等级 low。**

| 评审规则 | 结论 |
|---|---|
| 功能性与逻辑 | ✅ 通过 |
| 安全性 | ✅ 通过 |
| 性能 | ✅ 通过 |
| 可维护性 | ⚠️ 待优化（2 项，见下） |

机器人对本次变更的正面认定：纯类型注解重构不改变运行时行为；PEP 695 `type` 统一了回调类型
定义方式；新增 AST 扫描提升架构防回归能力；修复了长期存在的冒烟误报，确保 CI 门禁准确性。

## 二、改进项与处置

| # | 问题 | 证据 | 机器人建议 | 处置 |
|---|---|---|---|---|
| M1 | 守护用例 `_assigns_callable_alias` 对普通赋值（`ast.Assign`）的值做字符串子串匹配，可能误报模块级字符串常量（如含 `Callable[` 的文档或错误消息模板） | `tests/test_architecture.py` `_assigns_callable_annotation` 的 `ast.Constant` + `str` 分支 | 把字符串前引号的宽松匹配限定在 `AnnAssign` 的注解分支，或在 `Assign` 分支排除纯字符串常量值 | ✅ **已修（采纳原建议的第一种等价实现）**：`Assign` 分支先排除 `ast.Constant` 字符串值再判别名，字符串启发式只对注解位置生效。理由：延迟注解（`from __future__ import annotations`）下**只有注解**可能是带引号的前向引用，赋值位置的字符串恒为普通文本（pyright 也不会把它当别名用） |
| M2 | 未覆盖元组解包形式的别名赋值（`X, Y = Callable[...], Callable[...]`）：`node.value` 为 `ast.Tuple` 时直接 `return False` | 同上，`_is_callable_annotation` 缺 `ast.Tuple` / `ast.List` 分支 | 在 `_is_callable_annotation` 中增加对 `ast.Tuple` / `ast.List` 元素的递归检查（或在文档登记豁免） | ✅ **已修（采纳递归检查）**：新增 `isinstance(node, (ast.Tuple, ast.List))` 分支递归判定元素。选递归而非登记豁免，因为豁免会把这个洞长期留在唯一防回归用例里；递归只认"元素本身是顶层 `Callable[...]`"，与既定的"只判顶层"原则一致，不会把 `dict[str, Callable[...]]` 类数据表误判 |

两条均为可维护性改进，无阻断项，无需回滚设计。两处修复均经**负向演练**验证
（探针文件随命令创建并删除，不入库）：**7 类违规全部拦截**（普通赋值、带注解赋值、
`typing.Callable` 限定名、字符串前引号注解、模块级 `if` 内、元组解包、类体），
**4 类应放行形态零误伤**（数据表 `dict[str, Callable[...]]`、裸声明 `Field: Callable[...]`、
含 `Callable[` 的普通字符串常量 `DOC`、常量元组 `PAIR`、函数体内实例属性）。

## 三、门禁（主代理亲自跑，worktree 内 `.venv`）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 | `0 errors, 0 warnings, 0 informations` |
| `python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75` | 0 | **1996 passed / 9 skipped**，覆盖率 **91.44%** |
| `python -m pytest tests/test_architecture.py -q` | 0 | **25 passed** |
| `python -m tools.smoke_test run --skip-slow --no-color` | 0 | **102/102 scenarios，1236/1236 checks** |

## 四、关联

- 实施方案与全部偏离记录：[callable-aliases-plan.md](../documents/callable-aliases-plan.md)
  （§十一登记本轮评审处置）。
- 守护用例的规则文本：[architecture-boundaries.md §六](../rules/architecture-boundaries.md)
  「回调别名」条目；编码规范：[python-coding-style.md §3.5](../rules/python-coding-style.md)。
- 本轮之前的同分支评审：`code-review-expert` 独立评审的 14 条问题已全部处置，
  见方案文档 §9.2。