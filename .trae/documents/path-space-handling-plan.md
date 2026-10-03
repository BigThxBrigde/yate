# path-space-handling-plan（路径空格检测与修复，issue IKJK0B）

> 来源：[Gitee issue IKJK0B](https://gitee.com/jermaine/yate/issues/IKJK0B)
> （BUG - 路径空格检测和修复），即 [diff-tool-plan.md](diff-tool-plan.md) 遗留待办
> S5。执行分支：`feat/diff-tool`（PR49 未合并，`:diff` 代码仅存在于此分支，
> 续作任务复用既有 worktree `D:/Programming/yate-diff-tool` 及其 `.venv`，不新建）。

## 一、目标与非目标

### 目标

1. `:diff` 支持含空格路径：`"..."` / `'...'` 引号包裹的 token 按单路径解析。
2. 排查全仓所有"命令行字符串 → 路径"入口，统一引号处理口径：
   `:e` / `:saveas` / `:sp` / `:vs` 增加成对引号剥离（空格路径不加引号仍可用）。
3. `Editor.run_command` 的 args 切分改为 `split(maxsplit=1)`，
   保留路径内原始空格（现状 `" ".join(parts[1:])` 会把连续空格压扁）。
4. 回填文档：diff-tool-plan.md S5 标记已修；本计划回填实测结果。

### 非目标

- 不修 PR49 评审记录（2026-10-03-pr49-diff-tool-ai-review.md）里的改进项 1/2
  （tab 高亮偏移 / 超长行性能）——评审处置明确"先复核再动手"，与路径空格无关。
- 不改 CLI `--diff`（argparse + shell 引号，天然支持空格路径，实测无需改）。
- 不给提示条（prompt bar）输入路径加引号剥离——口径限定在 `:` 命令行。
- 不引入 escape（反斜杠转义）支持——与 Windows 路径语义冲突，引号已够用。

## 二、调研取证（关键事实清单）

| # | 事实 | 位置 |
|---|---|---|
| F1 | `:diff` 用 `args.split()` 切 token，空格路径被拆碎 | `yate/commands.py:300` |
| F2 | `:e` 整段 args 当单路径（`args.strip()` → `Path(args)`），空格可用但引号成字面量；**S5 所说"引号解析先例"实际不存在**（计划文档表述不准确，本计划即补上该口径） | `yate/commands.py:99-104` |
| F3 | `:saveas` 整段字符串进 `save_as` → `_submit_save_as`，同 F2 | `yate/commands.py:46-47`、`document_flows.py:308` |
| F4 | `:sp`/`:vs` 整段 args 进 `split_with_path`（`args.strip()` → `Path(text)`），同 F2 | `yate/commands.py:75-79`、`window_flows.py:74` |
| F5 | `run_command` 用 `text.split()` + `" ".join(parts[1:])`，路径内连续空格被压扁 | `yate/editor.py:853-854` |
| F6 | CLI `--diff` 走 argparse（`nargs="+"`），shell 负责引号，空格路径天然可用 | `yate/cli.py:188-195` |
| F7 | 全仓其余 `.split()` 调用点与路径无关（textobjects 语法名 / logs 版本串）；`shlex` 仅两处且都是 shell 语义（终端 shell / LSP 启动命令行），不是路径口径 | `textobjects.py:426`、`logs.py:140`、`shells.py:35`、`extensions/python_lsp.py:71` |
| F8 | worktree 干净、`.venv` 自证指向本 worktree（沙箱可用） | `D:/Programming/yate-diff-tool` |

## 三、备选方案与否决理由

### `:diff` 多路径切分

- **方案 A（采纳）：自写引号感知 tokenizer（`_split_paths`）**——空白切分，
  `"` / `'` 段内空白不切、引号字符剥离；未闭合引号 best-effort（行尾剩余算一个
  token）。约 20 行，无平台分叉，Windows 反斜杠路径原样保留。
- 方案 B（否决）：`shlex.split(posix=True)`——Windows 路径反斜杠被吃
  （`C:\dir` → `C:dir`），本项目主平台是 Windows。
- 方案 C（否决）：`shlex.split(posix=False)`——引号保留在 token 里需二次剥离，
  且单双引号行为怪异（`shlex` 的 posix=False 语义为 shell 设计，不是路径设计）。

### 单路径命令（`:e` 等）引号处理

- **方案 D（采纳）：成对引号剥离（`_strip_quotes`）**——仅当剥后仍非空且首尾
  为成对 `"`/`'` 时剥离；不切分，保住"不加引号的空格路径"既有可用性。
- 方案 E（否决）：单路径命令也走 tokenizer——`:e a b`（不带引号）会被切成两个
  token，破坏 F2 既有行为。

### 放置位置

- **方案 F（采纳）：helper 放 `commands.py` 模块级私有函数**——唯一消费者是
  命令表；"能用函数实现的就不造类"，不新建模块、不进叶子层。
- 方案 G（否决）：下沉到 `registries.py` 或新建 parsing 叶子——过度抽象，
  违反"不为假设性需求加抽象"。

## 四、解析口径（修复后）

```mermaid
flowchart LR
    A[":&lt;cmd&gt; rest-of-line"] --> B["run_command<br/>text.split(maxsplit=1)<br/>(F5 修复: 保留原始空格)"]
    B --> C{entry}
    C -->|":diff"| D["_split_paths(args)<br/>引号感知切多 token"]
    C -->|":e / :saveas<br/>:sp / :vs"| E["_strip_quotes(args)<br/>成对引号剥离, 不切分"]
    C -->|"其余命令"| F[原样传 args]
    D --> G[Path(token)...]
    E --> H[Path(整段)]
    style A fill:#bbdefb,color:#0d47a1
    style D fill:#c8e6c9,color:#1a5e20
    style E fill:#c8e6c9,color:#1a5e20
```

## 五、分步实施

### Step 1 — `yate/commands.py`：引号口径 helper + 五个命令接线

- 输入：§四口径；F1–F4。
- 改动：
  - 新增模块级 `_strip_quotes(text: str) -> str` 与
    `_split_paths(args: str) -> list[str]`（含 docstring，PEP 257 散文式）。
  - `_diff`：`tokens = _split_paths(args)`；usage 提示补 "quote paths with spaces"。
  - `_edit` / `_saveas` / `_split` / `_vsplit`：args 经 `_strip_quotes` 后传下家。
- 输出：`"C:\my dir\a.txt"` 等引号路径与不带引号空格路径均按预期打开。
- 验收：`.venv\Scripts\python.exe -m pyright yate/` 零诊断；
  Step 3 测试通过。

### Step 2 — `yate/editor.py`：`run_command` 用 `split(maxsplit=1)`

- 输入：F5。
- 改动：`name, args = parts[0], parts[1] if len(parts) > 1 else ""`
  （替代 `" ".join(parts[1:])`）。
- 输出：路径内连续空格原样保留。
- 验收：pyright + Step 3 测试。

### Step 3 — 测试

- 输入：§五 Step 1/2 行为。
- 改动：
  - 新建 `tests/test_command_path_args.py`：`_split_paths` /
    `_strip_quotes` 单测（引号成对、单双混合、未闭合 best-effort、
    空引号丢弃、多空格保留）；`run_command` maxsplit 行为（含 `:diff`
    引号路径走通 `open_diff` 的 pilot 用例）。
  - `tests/test_diff_integration.py` 增补：`diff "spaced a.txt" "spaced b.txt"`
    打开双栏 diff（真实临时目录含空格）。
- 输出：新用例全绿。
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_command_path_args.py tests/test_diff_integration.py -q`。

### Step 4 — 文档回填

- 输入：实测结果。
- 改动：diff-tool-plan.md S5 标记已修（附 commit 号）；本计划回填执行记录。
- 验收：文档内相对路径引用合规（doc-conventions §五）。

### Step 5 — 收尾门禁

- `.venv\Scripts\python.exe -m pyright yate/ tests/` 零诊断；
- `.venv\Scripts\python.exe -m pytest tests/ -q` 全绿（含架构测试 22 例）；
- 覆盖率 `--cov-fail-under=75`；按 `git-commit-message.md` 分步提交（不推送）。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `run_command` maxsplit 改动影响非路径命令的 args 空白语义 | 仅 `:set`/`:theme` 等自行 `strip()`，不受影响；逐命令核对 F1–F4 覆盖面 | 单 commit revert |
| 未闭合引号 best-effort 与用户直觉不符 | 行尾剩余整体一个 token（"忘记闭合"直觉）；单测锁定 | 同上 |
| `:sp "x y"` 剥引号后为空字符串 | `_strip_quotes` 空串不剥（len<2 卫语句），行为同现状 | 同上 |

## 七、执行记录（2026-10-03 回填）

- [x] Step 1：commit `d7b84be`（`fix(commands)`，+53/−6）——`_strip_quotes`
  （commands.py:37-46）与 `_split_paths`（commands.py:49-77）落位；
  `:diff` / `:e` / `:saveas` / `:sp` / `:vs` 五处接线与 §四口径一致，
  usage 提示补 `(quote paths with spaces)`。
- [x] Step 2：commit `7a91c80`（`fix(editor)`，+2/−2）——`run_command`
  改 `split(maxsplit=1)`（editor.py:853-854）。
- [x] Step 3：commit `528648b`（`test(commands)`，+202）——新建
  `tests/test_command_path_args.py` 13 例（helper 单测 10 + pilot 3），
  `tests/test_diff_integration.py` 增补引号含空格目录双栏用例 1 例。
  测试基建说明：`wait_until` 因 tests/ 无 `__init__.py` 无法跨文件复用，
  按 `test_app_textual.py` 先例内联，并用精确 `Pilot[None]` 泛型避免 `Any`。
- [x] Step 4：本提交——S5 状态与 4 条 minor 待办登记回填 diff-tool-plan.md。
- [x] Step 5 门禁（code-review-expert 实测 + 主代理复核，退出码均 0）：
  pyright `yate/ tests/` 0 errors；`pytest tests/ -q` 全绿（1 skipped）；
  架构测试 `tests/test_architecture.py` 22 passed；覆盖率 91.39%
  （`--cov-fail-under=75` 达标，改动行 0 missing）；冒烟 89/89 场景、
  932/932 checks。
- [x] 评审结论（closed-loop 步骤 5）：无 blocker / major；1 WARNING（方案
  文档回填缺口）已由本提交补齐；4 条 minor（引号路径集成测试 ×3 命令、
  边界口径锁定断言、`wait_until` 下沉 conftest、`:diff --3way` flag 覆盖）
  登记至 diff-tool-plan.md 遗留待办，不在本轮扩 scope。
- [x] 偏离记录：无。
