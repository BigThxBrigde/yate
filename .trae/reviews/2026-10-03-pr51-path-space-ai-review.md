# yate Code Review — Gitee PR #51 评审（fix/path-space-handling 分支）— 2026-10-03

## Gitee PR #51 评审（fix/path-space-handling 分支）— 2026-10-03

> **范围**：PR #51 `fix/path-space-handling` → `master`（issue IKJK0B：ex 命令行
> 含空格路径解析——[yate/commands.py](../../yate/commands.py) 新增引号感知
> tokenizer `_split_paths`（`:diff`）与成对引号剥离 `_strip_quotes`（`:e` /
> `:saveas` / `:sp` / `:vs`）、[yate/editor.py](../../yate/editor.py)
> `run_command` 改 `split(maxsplit=1)`，配套 `tests/test_command_path_args.py`
> 与 `tests/test_diff_integration.py` 增补；评审时点含方案 e7da154 / 修复
> d7b84be + 7a91c80 / 测试 528648b / 回填 6073ef6 共 5 笔提交）。本次登记
> **Gitee AI 队友审查**
> （[原始评论](https://gitee.com/jermaine/yate/pulls/51#note_51435445_conversation_191349311)，
> 2026-10-03 15:05）：结论 **⚠️ 无阻断项，可优化后合并**——功能性 / 安全性 /
> 性能 ✅ 通过，可维护性 ⚠️ 待优化，风险等级 **low**（0 阻断 / 1 改进）。

### AI 发现逐条登记与处置

- [ ] **改进项 1：`_saveas` / `_split` / `_vsplit` 的 `_strip_quotes` 调用缺
  前置 `.strip()`**（可维护性）—
  [yate/commands.py](../../yate/commands.py) 三处直接 `_strip_quotes(args)`
  而未先 strip，审查者指出 args 含尾部空白时首尾字符不匹配、引号静默不剥，
  下游会收到带字面量引号的路径；建议对齐 `_edit` 的写法（先 `args.strip()`
  再剥引号）。

  *核对结论（2026-10-03）：失败场景当前不可达——三个命令的 args 唯一来源是
  `Editor.run_command`（[editor.py](../../yate/editor.py) 入口 `text.strip()`
  + `split(maxsplit=1)` 消耗首个空白 run，args 不携带首尾空白）；属防御性
  一致性与接口口径统一问题，非行为缺陷。*

### 处置（2026-10-03 用户决策）

**本次登记不另修**（⏸）：无阻断、场景不可达。若后续出现 `run_command` 之外的
args 来源（如扩展 API 直调命令表），先复核该条再动手。
