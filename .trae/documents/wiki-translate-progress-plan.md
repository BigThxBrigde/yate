# wiki-translate-progress-plan

> 状态：已批准（2026-10-03，用户修改：1. 新建 worktree 走闭环；2. 进度显示用 rich 库）；
> **已实现**（见文末执行记录）。

## 目标

`python -m tools.pack wiki --translate-cmd ...` 的两处 UX 改进：

1. **翻译进度反馈**：开始前预告待翻译页数；翻译中用 rich 进度条展示
   当前页名与整体进度；结束后报告结果与耗时；
2. **Ctrl+C 优雅中断**：不打印调用堆栈，输出一行中断提示，退出码 130。

## 非目标

- 不改 `translate_via_cmd` 的 I/O 协议与 900s 超时语义；
- 不改 manifest 格式与翻译判定规则；
- 不给 rich 加显式依赖条目（rich 由 `textual>=8.0` 传递提供，先例：
  `tools/smoke_test/report.py:21-25` 已直接 import rich）。

## 设计

### 1. 进度反馈（rich，全部走 stderr）

- `Console(file=sys.stderr)`：进度条与提示不污染 stdout（stdout 只留总结）；
- 预告：`translate_cmd` 非 None 时主循环前预扫描 pending 页数，
  `console.print("wiki: N page(s) to translate")`；N=0 时
  `wiki: nothing to translate (M pages up to date)` 后照常收尾；
- 进度条：`rich.progress.Progress`（SpinnerColumn / TextColumn / BarColumn /
  TaskProgressColumn / TimeElapsedColumn，`console=stderr console`），
  单 overall task（total=N pending 页），description 显示
  `translating <en_target>`——满足"开始翻译什么"的提示；每页完成
  `advance(1)`，失败页经 Progress 的 console 打永久行
  `wiki: [k/N] <en_target> failed`（出现在进度条上方，不被覆盖）；
- **预扫描一致性**：`_needs_translation(page, target, manifest, translate_all)`
  与主循环判定同源（en_source 双源页直接 False；无 en / stale → True；
  fresh → translate_all）。已知 edge：en_source 读取失败的 TOCTOU 路径
  预扫描视为不翻译，主循环可能翻译——注释声明，概率可忽略；
- 非 TTY（测试 capsys / 输出重定向）下 rich 自动退化为非动态输出；
  用例只断言关键子串（页名、"to translate"、failed），不锁排版。

### 2. Ctrl+C 优雅中断（单层捕获，`tools/pack/cli.py:main`）

- `main()` 的 dispatch 外层 `try ... except KeyboardInterrupt:` →
  stderr 打印 `\ntools.pack: interrupted`，返回 **130**；
- `wiki.run` 不再 catch（KeyboardInterrupt 直接冒泡到 main）；
  Progress 作为上下文管理器在异常传播时正确 stop 并清屏残留；
  `subprocess.run` 被 Ctrl+C 打断时 CPython 先 kill 子进程再 re-raise，无僵尸；
- **中断后的续作成本天然为零**：已写盘的 en 页在下次运行时因
  `has_en and recorded is None` → 非 stale → 被 adopt（manifest 补记），
  只有中断瞬间正在翻译的那一页需要重译——该行为已存在于现行判定逻辑，
  方案不新增机制，仅在 README 说明。

## 改动文件

| 文件 | 改动 |
|---|---|
| `tools/pack/wiki.py` | 预扫描 `_needs_translation`；预告行；rich Progress 逐页进度 + 失败永久行 |
| `tools/pack/cli.py` | `main()` 捕获 `KeyboardInterrupt` → 提示 + exit 130 |
| `tests/test_pack_wiki.py` | 新增：stderr 含预告与页名；pending 预告数；KeyboardInterrupt → exit 130 且无 traceback |
| `README.md` / `README.zh.md` | wiki 小节补一句进度与中断行为（双语同步） |

## 验收

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
# 人工冒烟：--translate-cmd 指向一个 sleep 后输出的假命令，观察进度条；中途 Ctrl+C 无堆栈
```

## 风险与回滚

- 风险：预扫描与主循环判定漂移（双源真相）→ 用例锁定 pending 数；
- 风险：rich 在非 TTY 下的输出形态与版本相关 → 用例只断子串；
- 回滚：单提交 revert。

## 流程声明

按用户指示建独立 worktree `../yate-wiki-translate-progress`
（分支 `feat/wiki-translate-progress`，自 master 切出），worktree 内重建
`.venv` 并自证沙箱生效；每步单独提交、不推送。

## 执行记录（2026-10-03 回填）

- **提交**：`2ac8453`（方案）→ `6a03d6b`（feat 实现）→ 评审修复提交（本笔）；
- **评审**（code-review-expert 子代理，实测三项命令全 0 退出码）：
  2 个 major + 3 个 minor，全部修复：
  1. **major** `--translate-all` 下预扫描与主循环漂移（recorded-fresh 页预告
     "nothing to translate" 但实际被翻译、进度条不启动）→ `needs_translation`
     改为 adopted/fresh 均返回 `translate_all`，矩阵测试补该格；
  2. **major** 页名直入 rich markup（`[edit]` 被吞 / 平衡方括号触发
     MarkupError 打崩 run）→ 预告/失败行 `markup=False`，进度描述
     `rich.markup.escape`；
  3. **minor** 失败行分母与进度条口径不一（`[k/len(pages)]` vs `total=pending`）
     → 统一为 `[attempted/pending]`（偏离方案原文字面，实测依据：双分母并存
     易误读，评审建议采纳）；
  4. **minor** 汇总行补总耗时（`in N.Ns`，兑现方案"结束后报告结果与耗时"）；
  5. **minor** 预告数断言改为按 `needs_translation` 现算期望值，解除夹具耦合；
  - 未采纳（nice-to-have）：92 字符 genexp 折行（合规 ≤100）、
    `pending==0` 时 `add_task` 语义噪音（无行为影响）。
- **门禁实测**：`pytest tests/test_pack_wiki.py -q` 30 passed（exit 0）；
  `pyright yate/ tests/ tools/` 0 errors（exit 0）；全量 `pytest tests/ -q`
  全绿（exit 0；`test_manual_search_step_lands_on_exact_rendered_row` 首轮
  timing 偶发失败，重跑通过后确认与本次改动无关——该用例不触及 tools/pack）；
- **冒烟说明**：交互式 Ctrl+C 冒烟未执行（本会话无法向子进程发送 SIGINT），
  中断路径由 `test_keyboard_interrupt_maps_to_exit_130` 覆盖（断言 exit 130、
  stderr 含 "interrupted"、无 "Traceback"）；非交互进度输出形态由
  预告/失败行用例覆盖（rich 非 TTY 自动退化为普通输出）。
