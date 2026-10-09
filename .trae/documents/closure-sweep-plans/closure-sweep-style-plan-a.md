# closure-sweep-style-plan-a（任务 2：python-coding-style 合规审查）

来源：用户指令「审查是否遵守 .trae/rules/python-coding-style.md」。
取证基准：2026-10-09 master `25e17d3`，worktree 内实测。

## 一、审计结论（实测证据）

| 检查项 | 规则条款 | 实测结果 | 结论 |
|---|---|---|---|
| pyright strict 零诊断 | §4.2 | `python -m pyright yate/ tests/ tools/` → `0 errors, 0 warnings, 0 informations`（exit 0） | ✅ |
| `from __future__ import annotations` | §4.1 | 全仓强制，pyright + 架构守护在位 | ✅ |
| `TYPE_CHECKING` | §4.3 / R6 | 全仓 0 处（仅架构测试 docstring 提及） | ✅ |
| `Optional[` / `Union[` | §3.2 | 全仓 0 处 | ✅ |
| 裸 `except:` | §4.5 | 0 处 | ✅ |
| 日志惰性 `%` 占位符 | §4.6 | 守护用例 `test_log_calls_use_lazy_percent_formatting` 在位并通过 | ✅ |
| `print()` 调试 | §4.6 | 仅 CLI 输出路径（`cli.py` / `diagnostics.py` / `logs.py:104` stderr / tools CLI），非调试用途 | ✅ |
| `# type: ignore` / `# pyright: ignore` | §4.2（禁止，特例须附理由） | **15 处**（详见 §二） | ⚠️ 部分缺理由注释 |

## 二、唯一整改项：ignore 注释理由补全（§4.2 要求"附带注释说明理由"）

实测清单（search 全仓，仅列缺理由者）：

1. `yate/editor_view/themes.py:483,485,490,511` —— `# pyright: ignore[reportUnnecessaryIsInstance]`：
   运行时校验外部主题文件的动态数据，类型收窄无法静态表达。补一行理由注释。
2. `yate/editor_syntax/engine.py:83` —— `# type: ignore[no-any-return]`：可选依赖
   py-tree-sitter 动态导入返回值。补理由注释。
3. `tools/smoke_test/harness.py:56` —— `# pyright: ignore[reportPrivateUsage]`：
   复用 Textual 私有 `_wait` 实现确定性等待。补理由注释。
4. `yate/editor_term/pty_proc.py:228-232,430,577` —— POSIX 模块平台限定导入与
   ctypes `attr-defined`：`import-not-found` / `attr-defined` 语义已自明，仍补短语注释统一口径。
5. `tests/test_app_manual.py:138,167`、`tests/test_theme_palettes.py:343,358`、
   `tests/test_workspace_filter.py:57`、`tests/test_pty_proc.py:83` —— 负向用例 /
   ctypes 桩的 `arg-type` / `attr-defined`：补短语注释。

改动全部为注释行，不改任何可执行语句；pyright / pytest 行为零变化。

## 三、实施步骤

- 输入：§二清单。
- 改动文件：上列 9 个文件。
- 输出：每处 ignore 附短语理由注释（`# <reason>`，与 ignore 注释同行或上方）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pyright yate/ tests/ tools/
  .venv\Scripts\python.exe -m pytest tests/ -q -x -k "theme or pty or smoke or engine"
  ```

## 四、备选与否决

| 备选 | 否决理由 |
|---|---|
| 删除全部 ignore 改写类型 | 平台限定导入 / 动态数据校验在 pyright strict 下无替代写法，会引入更宽的 `Any` |
| 用 §4.2"极特殊场景"批量豁免登记成文 | 与"零 ignore"红线冲突；逐处理由注释是规则原文要求的形态 |

## 五、风险与回滚

零行为风险（纯注释）。回滚：revert 单提交。

## 六、执行结果回填（2026-10-09）

复核证据（带上下文 grep 全量 14 处）：**全部 ignore 注释均已附理由注释**
（themes.py 块注释 / pty_proc.py:227、:429、:576 / harness.py:55 /
engine.py:82 / 各测试文件行内注释）——§二清单系初扫未带上下文的误报，
本轮零代码改动，合规结论由 ⚠️ 升级为 ✅；pyright 全仓（含 pack/）0 诊断。
