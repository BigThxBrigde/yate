# 2026-11-05 全仓库多维度评审（第二轮，r2）

- **Date**：2026-11-05
- **Scope**：全仓 audit 路由（`yate/` 162 个 `.py` / 42763 行、`tests/` 147 / 66173 行、
  `tools/` 90 / 16884 行；用户可见双语文档、规则文本、评审索引）。基线
  `master 75bccfa`，worktree `enh/multi-dim-review-r2`；距上一轮基线 `0ae1a64`
  共 174 提交 / 366 文件 +32492−4469。
- **Sources**：[multi-dim-review SKILL](../skills/multi-dim-review/SKILL.md)、
  [主计划](../documents/multi-dim-review-r2-plan.md)、
  [修复方案](../documents/multi-dim-review-r2-fixes-plan.md)、
  [上一轮记录](2026-10-31-multi-dim-review.md)、[评审索引](README.md)、
  `.trae/rules/` 八份规则；5 名只读审查员两波 fan-out 报告 + 主代理机械取证与逐条回读复核。
- **流程事实**：`plan-architect-designer` 两次 spawn 均因定义 frontmatter
  `qwen-3.7-plus` 未注册失败（第二次任务书已显式指定 `Hy4 preview` 仍失败），按
  `task-orchestration.md` §三由主代理兜底亲自产出方案，**如实标注该环节子代理零产出**；
  5 名只读审查员（SA–SE）全部交付，主代理逐条回读当前文件复核。
- **Overall**：**REQUEST_CHANGES（基线态）→ 修复闭环后 APPROVE** —— 基线态
  0 BLOCKER / **2 MAJOR** / **13 MINOR**，全部当轮闭环；六道硬门禁中覆盖率一道首次被
  本机 safe-delete 钩子拦截（环境事故，非测试失败），按独立轮次复跑处置；修复后六道门禁
  全 exit 0，收尾复核提出的 4 MINOR 亦全闭环。逐项事实见文末「修复后复核」。

> 本文件是**只读事实记录**，不含修复排期；改法、验收命令与回滚见
> [修复方案](../documents/multi-dim-review-r2-fixes-plan.md)。

## 一、逐维度结论（13/13，clean 维度亦列检查面与代表性排除）

| 维度 | 结论 | 检查面与代表性排除 |
|---|---|---|
| D1 正确性 | 1 MAJOR + 1 MINOR | 边界/极大值/极深树、off-by-one、pane-tree 不变量、undo delta、`take_dirty_range` 消费 vs peek、`editor_compose`/`editor_dispatch` 拆分等价性、workspace anchored 规则。代表性排除：`buffer.py:377-396` 消费语义由 `_note_dirty` 重置双端保证，`tests/test_editor_core.py:296-320` 钉住；`editor_compose.py:103` 的 LSP 启动期竞态被 `app.py:158/215` 挂载顺序反证。 |
| D2 健壮性 | 1 MAJOR + 2 MINOR | 具体异常类型、69 处 `except Exception` 的 noqa 与反馈面、进程池/PTY 收尾、30 处 worker 协程形态、上一轮 pty 四处修复保持性。代表性排除：30 处 `run_worker` 全传 coroutine function / `partial`，`filterwarnings=error::RuntimeWarning` 无游离协程。 |
| D3 安全 | **clean** | 三入口 trust 门控（project rc / `./extensions` / `./themes`）、`.yxp` 子包四文件 casefold 去重与 zip-slip/盘符/保留目录/symlink 端到端、record↔disk 原子写与回滚、`exec`/`eval`/`pickle`/`shell=True` 全仓精确扫描、新增模块是否引入自动执行面。代表性排除：`yaterc.py:195 exec(code, namespace)` 被同文件 `:128 if is_trusted(project.parent):` 直接反证。 |
| D4 算法复杂度 | 5 MINOR | bisect 区间表、高亮版本缓存、匹配桶、workspace 忽略规则/遍历、file_manager 排序与缓存、wiki 并发分桶、全仓 list 成员测试。代表性排除：`highlighting.py:310` 全行重建由 `:346` 版本写回 + `take_dirty_range` 限定为「每内容版本一次」。 |
| D5 性能 | **clean**（5 Suspect） | 每按键路径（dispatch→refresh_ui→LSP/completion）、TTL 缓存拷贝、file_manager stat/preview 缓存、`.yxp` 流式读、循环内 `+=`、wiki 池生命周期、截图帧 I/O。代表性排除：`editor_dispatch.py:176 if handled: ed.refresh_ui()` + `manager.py:430-442` 0.25s 防抖，全文快照不在每键。 |
| D6 架构边界 | 1 组 MINOR 登记漂移 | R1–R15、`_LAYER_RANKS`、`UPWARD_EDGES_FROZEN`、命名守卫、`self.app` 能力注入、devtools 通道、widget id。代表性排除：全仓 `from yate.app` 精确 1 命中（`cli.py:481`）。 |
| D7 结构与职责 | 4 MINOR 文档/登记漂移 | >800 行两处同步、包根惰性、flows 接入清单、无中央接口层、子包化门面路径。代表性排除：`SIZE_EXEMPT_FILES` 4 项与规则 §三.7 名单逐名一致；两个无 `from __future__` 的 `__init__.py` 为 docstring-only 包根。 |
| D8 类型纪律 | **clean** + 建议级一致性偏离 | future import、40 处 ignore 逐处诊断类别、`Any` 理由一致性、PEP 695 别名 49 处、`@override` 49 处、`App[None]`/`Screen[None]` 精确形态。代表性排除：`yxp/install.py:303` 是 `reportUnusedFunction` 且 `:112` 有门面晚绑定调用，非类型不匹配掩盖。 |
| D9 风格惯用 | **clean** + 建议级一致性偏离 | 行宽（9 处命中逐条裁定）、ASCII 注释、散文式 docstring、日志惰性 `%`、`print()` 豁免面。代表性排除：`characters.py:62` 的 `§` 属 `NON_ASCII_COMMENT_EXEMPT` 引述型存量，本轮无新增命中。 |
| D10 并发/运行时/可观测 | 3 MINOR + 3 Suspect | 12 处 `run_worker`、worker 失败日志、R10 一次派发、`support_mouse` 闸门、主题进程全局还原、时序敏感代码。代表性排除：`app.py:268-272` 闸门早于 `super().on_event`；`chunked_flows.py:169-175` 是观测性正面样板。 |
| D11 测试验证 | **clean** + 4 Suspect | 拆分/子包化契约用例、37 守卫与负向演练、真实睡眠断言全量扫、`caplog` propagate、冒烟基线。代表性排除：`test_app_find.py:1150-1161` 冻结窗口 30.0 + 显式 flush，`conftest.py:311-331` 单调时钟轮询。 |
| D12 文档/双语/提交 | 1 MINOR | 7 对 `*.{en,zh}.md` + 根双语 + `manual.{en,zh}.md`、四个 CHANGELOG 生成标记、`.trae/` 路径、20 条提交 subject。代表性排除：`manual.en.md:467,768,769` / `manual.zh.md:433,702,703` 已同步 `Alt+Shift+F` / `:cd` / `:file-manager`；5 条不合规 subject 均为平台生成 merge。 |
| D13 硬门禁 | **clean** + 1 Suspect | 六道命令在 skill / `pyproject.toml` / GitHub Actions / Gitee 腿 / 主计划中齐备，阈值 75 单源于 `pyproject.toml:166`，`tests/test_gate_config.py` 断言 CI 不得硬编码 `--cov-fail-under`。代表性排除：CI 无独立架构步骤不构成缺门禁（`testpaths=["tests"]` 必收集 37 守卫）。 |

## 二、Findings

### [BLOCKER]

无。

### [MAJOR]（2）

1. **`yate/services/workspace.py:581-588` — `is_text_file` 把「非法 UTF-8 但无 NUL」的二进制判为文本（D1）**
   `chunk.decode("utf-8")` 抛错后无条件 `chunk[:exc.start].decode("utf-8")`（该切片必然解码成功），
   随后 `return b"\x00" not in chunk`。PNG 头 `b"\x89PNG\r\n\x1a\n"` 无 NUL 且含非法首字节，
   因此被判为文本；`yate/session.py:114,140` 据此允许把二进制文件打开为文本文档，
   `editor_components/preview.py:102`、`flows/overlay_flows.py:158` 同路径。
   现有 `tests/test_workspace_filter.py:678-679,691-692` 两个二进制用例都带 `\x00`，恰好绕开该分支；
   `:38-47` 只钉住「切口截断多字节」的合法场景。主代理最小探针确认：截断尾的
   `UnicodeDecodeError` 为 `reason="unexpected end of data" / end==len(chunk)`，PNG 头为
   `reason="invalid start byte"`，二者可区分。修复见方案 F1（增量解码器 + 两条回归用例）。

2. **`yate/editor_components/terminal.py:182-186` — `shutdown()` 静默吞异常（D2）**
   `except Exception:  # noqa: BLE001` 块内仅 `pass`，`await proc.wait_closed()` 的任何失败
   既无日志也无用户反馈，违反 `python-coding-style.md` §4.5；解释性注释不是日志。
   同仓 `editor.py:376-387` 三段 teardown 均有 `log.exception`，故为孤立缺口而非面状缺陷。
   修复见方案 F2。

### [MINOR]（13）

| # | 位置 | 摘要 |
|---|---|---|
| m-01 | `tools/mdlint/cli.py:227,238,324`；`tools/pack/wiki/lint.py:129,354` | 5 处 `except Exception` 缺 `# noqa: BLE001`（均有 stderr/WikiError 反馈，故非静默吞异常，不升 MAJOR） |
| m-02 | `yate/editor_term/pty_proc.py:182-183,205-206,289-293,319-320,346-350,358-359` | 六处 best-effort `pass` 无 tracing；上一轮只修了外层四处，内层仍静默 |
| m-03 | `yate/editor_components/terminal.py:577-580` | worker 捕获 `PtyProcessError`/`OSError` 后仅写 prompt，模块已有 `log` 却零 tracing |
| m-04 | `yate/editor_components/palette.py:234-235` | `except OSError: entries = []` 把跨层扫描失败静默降级为空结果，同包 `preview.py:131` 已有 `log.warning` 惯例 |
| m-05 | `yate/flows/shell_flows.py:137-142` | flows(L3)→`fonts.ensure_font`(L0) 失败仅用户提示，模块无 logger |
| m-06 | `yate/services/yxp/manifest.py:177-179` | `zi.filename in payload`（list）→ O(m×n)，标准替代 `set(payload)`；子包化新文件 |
| m-07 | `yate/yaterc_options.py:103,151` | 两处 list 成员测试去重 O(n²)，标准替代 set 累加 |
| m-08 | `tools/pack/wiki/report.py:117-118` | 组循环内对整 bucket 线性过滤 O(G×N)，`:87-89` 已示范 dict 分桶；子包化新文件 |
| m-09 | `yate/editor_core/search.py:72-81` | `_nearest_index` 线性扫描，matches 已按 `(row,start)` 有序，标准替代 `bisect_left` |
| m-10 | `yate/services/extensions/loader.py:118-121` | set 命中后仍线性扫 `loaded` 找 record，标准替代 `dict[Path, LoadedExtension]` |
| m-11 | `yate/services/workspace.py:424` | 未命中缓存分支返回 `files` 本体，命中分支 `:372` 返回 `.copy()`，调用方可反向污染 TTL 缓存 |
| m-12 | `.trae/documents/multi-dim-review-r2-plan.md:54,61,65` | 本轮新建文档含 3 处本机盘符路径，违反 `doc-conventions.md` §五；同文件 Step 1 自验收声明与实际矛盾 |
| m-13 | `.trae/rules/architecture-boundaries.md:308,319` | 登记漂移：`vim.py` 1528 行 vs 实测 1531；`filemgr/` 与真实目录 `file_manager/` 两名并存 |

另有 D6/D7 的登记漂移组（mermaid L3 节点、§三.5 例外名单、§三.8 `None` 初值）
经主代理裁定**降级为 Deferred**（需架构裁决 + 守卫数同步），见第四节。

## 三、Suspects（不确定项，全部保留，写明缺什么证据）

| 来源 | 位置 / 断言 | 缺失证据 |
|---|---|---|
| SA D1-3 | `workspace.py:308` 目录级含 `/` 的 anchored 规则按 basename 匹配，可能与 git 语义不符 | 需 `git check-ignore -v` 对照 `sub/.gitignore` 的 `a/b` 与真实仓库依赖；docstring 已声明 per-directory 近似 |
| SA D1-14 | `yxp/install.py:113` 仅 `except YxpError` 回滚，门面 seam 抛 `RuntimeError` 时可能部分安装落盘 | 需 `_write_record`/`read_package` 全异常类型清单 + 注入负向演练；读码现症不可达 |
| SA D1-15 | `yxp/install.py:324` 固定 `.tmp` 名在并发安装同名包时互相覆盖 | 缺「产品是否要求并发安装」契约与 `tools/yxp/cli.py` 调用面确认 |
| SA D1-16 | `tools/pack/wiki/run.py:191` `errors="replace"` 静默译码，lint 侧与翻译侧判定不一致 | 需构造非 UTF-8 `.zh.md` 跑一轮复现；`collect_sources` 不校验编码 |
| SA D2-11 | `tools/screenshots/driver.py:189` `subprocess.run` 无 timeout，fontTools 可能挂起 | 缺损坏字体上的阻塞可达性 + 有界 timeout 探针 |
| SB S1 | `yxp/install.py:374-388` uninstall 中途 unlink 失败留下部分删除 + record 仍在 | 缺异常注入实测与「已知限制」登记；`missing` 语义提示可重试自愈 |
| SB S2 | `tools/yxp/cli.py:189-208,220-231` 打包器未逐段 casefold 去重，可生成自身 `--verify` 拒绝的包 | 缺大小写敏感 FS 复现与变更集范围确认；安装侧安全面已闭合 |
| SB S3 | `workspace.py:727-729` / `completion.py:415-418` 已排序条目仍线性前缀扫描 | 复杂度类不降（构造 key 数组同 O(N)），缺万级目录 profiler |
| SB S4 | `tools/pack/wiki/run.py:297-308` `expected` 可复用 `collected \| generated` | 纯常数因子，缺 profiler 实测 |
| SB S5 | `tools/yxp/cli.py:228-231,307-309` 每个 payload 文件 `read_bytes()` 两次 | 缺大包 I/O profiler |
| SB S6 | `tools/screenshots/driver.py:149-219` 单帧 SVG 3~4 次整文件读写 | 缺 SVG 体量分布与 profiler；整文件替换使流式无标准替代 |
| SB S7 | `tools/screenshots/driver.py:189-201` 每帧一个 fontTools 子进程 | 缺跨帧 codepoint 集合重复度统计与启动耗时 profiler |
| SC S2 | `tools/pack/wiki/__init__.py` 门面再导出是否属 §三.5 ① 例外 | 缺「§三.5 ① 是否适用于 `tools/` 构建 CLI 包」的口径裁定 |
| SC S3 | L3 同层连线（`editor.py ↔ editor_compose/dispatch`）是否需登记面 | 缺主代理对「除 L4 入口同层边外一律严格向下」是否涵盖拆分双向边的裁决；已按 Deferred 登记 |
| SC S4 | §三.8 「`None` 初值」与代码纯注解不一致 | 缺「是否已放宽为纯类注解」的评审登记；已按 Deferred 登记 |
| SD S1 | `editor.py:726-732` `_rebind` worker 无 try/except/log | 缺 `doc_shown_later()` 异常面核实；`manager.py:404-408` 已覆盖 didClose 失败 |
| SD S2 | `highlighting.py:438-440` / `find_replace.py:389` worker 线程失败无日志 | 缺非 `OSError` 逃逸面核实；协作者已有调试日志 |
| SD S3 | `pty_proc.py:658` `Event().wait(0.2)` 依赖真实睡眠 | 产品代码（非测试面），缺「就绪等待」与「时间窗口断言」边界口径 |
| SD S4 | `tests/test_chrome.py:165` 抑制注释与代码分行，是否真正抑制诊断 | 缺 pyright 对 `:166` 的实测诊断输出 |
| SE #4 | `tests/test_pty_proc.py:605` 固定 0.2s 就绪等待后断言 | 缺规则对「异步就绪等待」的界定；有 `wait_for(..., REAL_PTY_TIMEOUT)` 兜底 |
| SE #5 | `tests/test_terminal.py:404,409` 0.05s 后负向断言 | 短 sleep 只漏检不误报；缺是否落入禁止口径的裁定 |
| SE #17 | `tools/smoke_test/cli.py:333-335` 缺基线只 SKIP，无全场景覆盖断言 | 缺 release gate 是否真跑 `compare` 的证据（`smoke_baselines/` 121 json vs 121 场景数量相符） |
| SE #19 | `tests/test_lua_lint.py:19-22` CI 腿 lupa skip 前提存疑 | 缺 CI Linux 腿实测日志；`pyproject.toml:57` dev 组含 lupa 与 CI 装 `.[dev]` 是静态新证据 |
| SE #24 | `manual.{en,zh}.md` 版本号 `0.1.0` vs `__version__ = 0.2.17` | 缺 `:manual` 是否运行时替换版本、该落差是否被接受的证据 |
| SE #30 | `git-commit-message.md` 未显式豁免平台生成 merge | 属规则文本可补的一句例外，缺用户决策记录（列 Suggestion） |
| SE #38 | `tests/test_gate_config.py` 5 用例未覆盖 changelog/pyright/架构步骤存在性 | 缺「有意裁剪 4 项」还是漏项的证据 |

**主代理复核删除（引反证）**：SA D1-13（`editor_dispatch.py:27` logger 命名空间变化）——
精确检索 `caplog.at_level|set_level(..., logger="yate.editor")` 在 `tests/` 仅命中
`test_theme_palettes.py:456` 的 `yate.editor_components.theme.themes`，无任一用例订阅
`yate.editor` 这三条消息，按 Step 4「只有同行反证才删除」删除该 Suspect。
SA D1-2 由 m-11 直接修复销账；SA D2-5 降级 Suggestion（见下）。

## 四、Suggestions（真实但建议级，不改行为）

- `workspace.py` 9 处 `except OSError` 无日志：docstring 定义显式降级契约且
  `test_list_dir_returns_nothing_when_iterdir_fails` 等用例钉住返回值，属「返回值反馈」，
  是否统一补 `log.debug` 由后续裁定（SA D2-5）。
- `yate/services/yxp/` 新子包 `Any` 注解无 `# noqa: Any` 理由：全仓 `**kwargs: Any` / LSP JSON
  既有面一致，属「平迁而非新增体系性漂移」，按一致性偏离一次登记（SC S1 / SD D8-C）。
- `yxp` 子包 3 处文件级 `# pyright: reportPrivateUsage=false` + 4 处
  `reportUnusedFunction` 抑制相对 `yaterc_options.py` 的 `__all__` 先例是抑制手段偏离，
  建议下轮统一并补计划级登记（SD B3-补）。
- 9 处 >100 字符行（6 处 `yate/` 既有 + 3 处 `tools/` 平迁）建议下轮顺手折行（SD D9-A）。
- `tests/test_architecture.py::test_editor_does_not_paint_widget_styles` 只扫 `editor.py`，
  建议把新拆的 `editor_compose.py` / `editor_dispatch.py` 纳入扫描面（SC S5，实测 0 命中）。
- `git-commit-message.md` 可补一句「平台生成 merge 提交豁免」（SE #30）；
  `tests/test_gate_config.py` 可补 changelog / pyright / 架构步骤存在性断言（SE #38）。

## 五、Deferred（确认真实但本轮登记不修）

| id | 事项 | 理由 |
|---|---|---|
| D1 | 架构 Mermaid L3 未登记 `editor_compose` / `editor_dispatch` 节点与同层连线 | 规则要求「新增合法连线须先修订图并补守卫用例」，连带 37→38 守卫数与多处文档同步，属架构决策 |
| D2 | §三.5 ② 例外名单未列 `services/yxp/__init__.py` 门面再导出 | 同属架构登记，需架构裁决后单独提交 |
| D3 | §三.8 第 2 条「类型注解 + `None` 初值」与代码纯注解不一致 | 代码侧（pyright strict）是正确的一侧，改规则文本属规范修订 |
| D4 | T2 守卫扫描面偏窄（C23） | 加宽守卫需负向演练与单独登记 |
| D5 | 打包器 casefold、uninstall 非原子、固定 tmp 名、wiki lossy 译码等 Suspect | 缺用户场景/契约证据，按证据纪律不得当 finding 修 |
| D6 | `.trae/` 文档面历史本机路径存量（42 处 / 21 文件） | `doc-conventions.md` §五「随下次修改逐步迁移」，本轮不批量清扫；本轮**新增** 3 处已单列 m-12 修复 |
| D7 | README 中 ⏸ / 👀 / 📌 存量登记项 | 既有登记项，本轮只做有效性复核（见第七节），不重提为 finding |
| D8 | #50 F4–F7、uninstall OSError、空 themes 噪声、logs mkdir mode、lua lint CI skip | 既有登记项；部分 `file:line` 因 2026-11-04 子包化失效，需台账重定位 |

## 六、Strengths（本轮确认的正面事实）

- 三入口 workspace trust 门控在 `editor_compose`/`editor_dispatch` 拆分与 `yxp`/`wiki` 子包化后
  仍完整：`yaterc.py:128`、`extensions/loader.py:303`、`theme/files.py:74` 均锚定 `cwd.resolve()`
  与 `root.resolve()` 同拼写，无新 auto-exec 路径。
- `.yxp` 子包化未丢失任何卫语句：成员名逐段 casefold 去重（`manifest.py:271-281`）、
  拒绝盘符/绝对路径/`..`/`_manifests/`、symlink 端到端、record 原子写与失败回滚；
  `tests/test_yxp_subpackage.py` 锁定门面 `__all__` 与冻结 logger 名。
- 性能审计 #47（PR !104）类别当前仍清零：`buffer.py` bisect 区间表、
  `highlighting.py` 版本缓存 + `take_dirty_range`、`manager.py` 0.25s 防抖、
  `editor.py` `content_stale` 脏标记、`file_manager` stat/preview 缓存。
- 37 个架构守卫与 `tests/test_editor_compose.py` / `test_editor_dispatch.py` 10 个结构用例
  共同钉死 L3 拆分契约；R2 Protocol 白名单、`SCROLLBAR_EXEMPT`/`HOME_PATH_EXEMPT`/
  `UPWARD_EDGES_FROZEN` 三个空集保持。
- 双语面完整：7 对 `yate/docs/*.{en,zh}.md`、根 README/CHANGELOG 双语、`manual.{en,zh}.md`
  同步 `Alt+Shift+F` / `:cd` / `:file-manager`；四个 CHANGELOG 均为生成物且 `check` 绿。
- 覆盖率阈值 75 单源于 `pyproject.toml`，两条 CI 均不硬编码；冒烟 121/121 场景、
  1463/1463 检查通过。

## 七、Exemption ledger（被登记豁免集吸收的候选）

| `file:line` | 集合 / 条款 |
|---|---|
| `yate/keymaps/vim.py`（1531 行）、`editor_components/file_manager/screen.py`（963）、`editor_core/buffer.py`（1565）、`editor_syntax/langdefs.py`（841） | `SIZE_EXEMPT_FILES` + 规则 §三.7（vim 行数登记漂移见 m-13） |
| `yate/flows/*` 10 个文件 26 条 `editor_components` import | `UI_FROZEN_FILES` |
| `yate/cli.py:310-418`（12）、`diagnostics.py:125`、`logs.py:107` | `PRINT_EXEMPT_SITES`（14 处 `print()` 全部合规） |
| `yate/editor_sprites/characters.py:62` | `NON_ASCII_COMMENT_EXEMPT`（引述型存量，本轮唯一机械命中） |
| `editor_components/editor.py:50`、`editor_syntax/engine.py:33`、`ts_backend/backend.py:113,118` | `ALLOWED_PROTOCOLS`（R2 冻结白名单 4 = 4） |
| `services/yxp/{__init__,install,manifest,records}.py` 的 `tracing.get_logger("yate.services.yxp")` | 规则 §一 R12 冻结 logger 名登记例外 |
| `PaneHost`（`panes.py:463` 等） | `BANNED_SUFFIX_WHITELIST`（命名守卫） |
| — | `SCROLLBAR_EXEMPT` = `HOME_PATH_EXEMPT` = `UPWARD_EDGES_FROZEN` = 空集，无候选被吸收 |

D1/D2 的 3 条 MAJOR/MINOR 均**不在**任何豁免集覆盖范围内，不构成「豁免变宽」；
`tools/mdlint/cli.py` 的 print 属 §六 #35「`tools/` CLI 产品输出不在扫描面」，非库模块调试打印。

## 八、既往登记项有效性复核（Step 6.4，默认不重提）

| id | 状态 | 本轮证据 |
|---|---|---|
| #4 Gitee Go 3.12 未实跑 / #10 PB5 人工矩阵 / #11 配对扫描无上限 / #14 logs 桥 handler / #19 PR !46 / #25 G9-2,G9-3 / #31 真实 TTY / #33 O-1,O-2 / #35 A12,A19 / #45 m-21 / #46 18 WARNING / #12 H1-L7 / #51 file-manager / #52 `:cd` / #22 全仓 18 WARNING | 未变 | 索引登记维持，本轮无推翻性证据 |
| #9 scrollbars 1/8 粒度 / #40 PR !64 M1-M3 | 已修/记录保留 | `tests/test_scrollbars.py` 守卫在位；索引已标 ✅ |
| #17 S-1…S-9 | **部分新证据** | S-9「`editor.py` 拆分」已由 2026-11-04 big-module-split-2 落地为 `editor_compose.py` + `editor_dispatch.py`，该条应重估，其余未变 |
| #53 file-manager PR 未通过 | **部分推翻** | 「手册缺 `:file-manager` 与 `Alt+Shift+F`」已被 `manual.en.md:467,769` / `manual.zh.md:433,703` 推翻；blocker 与其余 minor 未逐项复核 |
| #50 F3 尺寸豁免行数 1239/841/841 | **已被取代** | `tests/test_architecture.py:350-360` 记录 2026-11-04 拆分后摘除 3 项，当前仅 4 项 |
| `cli.py:413` 排版 | **已不成立** | 当前 `:412-414` 为三行 `cleanup_defaults(...)` 多行调用 |
| arch-sec-audit F4 / logs mkdir mode / 空 themes 噪声 / uninstall OSError | 仍成立 | `yate/logs.py:194-207` 仍 `mkdir` 后 `chmod`；`install.py` 仍多处 `except OSError` |
| F5 / F6 / F7 / `yxp.py:398-399` | **路径失效需重定位** | `yate/user_setup.py` → `yate/services/user_setup.py`；`yate/editor_components/theme/loader.py` 已不存在；`yate/services/yxp.py` → `yate/services/yxp/` 四文件 |
| lua lint CI lupa skip | 未定 | `pyproject.toml:57` dev 组含 `lupa>=2.0` 且 CI 装 `.[dev]`，与 #50 推断前提相左；缺 CI Linux 实测日志，不判推翻 |
| `.trae/` 文档面历史本机路径 | 登记待办 | 按 §五不批量清扫；本轮新建文档的 3 处新增违规另列 m-12 |

## 九、硬门禁实测（主代理亲跑，Step 7）

基线态命令与真实退出码（六道串行执行于同一后台执行器；解释器 `.venv\Scripts\python.exe`，
`pyright` 前注入 `%LOCALAPPDATA%\pyright-python\nodeenv\Scripts` 到 PATH）：

| 门禁 | 命令 | 首次退出码 | 实测输出要点 |
|---|---|---|---|
| pyright | `-m pyright yate/ tests/ tools/` | **0** | `0 errors, 0 warnings, 0 informations` |
| pytest | `-m pytest tests/ -q -n auto` | **0** | `-q` 无汇总行，以 exit code 为准；用例总数以覆盖率轮次输出为准 |
| 架构 | `-m pytest tests/test_architecture.py -q` | **0** | 37/37 守卫用例 |
| 覆盖率 | `-m pytest tests/ --cov=yate --cov-branch -n auto` | **1** | `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":18377,"threshold":9999}`，99→100% 处被本机钩子杀进程，**无 FAILED、无汇总行**——按项目记忆 `reference_safe_delete_pytemp.md` 定性为环境事故，非测试失败 |
| 冒烟 | `-m tools.smoke_test run --jobs 4` | **0** | `121/121 scenarios passed`、`1463/1463 checks (100%)`、77.69s |
| changelog | `-m tools.changelog check` | **0** | `released changelog sections are up to date`；unreleased 滞后 87 提交属生成物语义 |

覆盖率门禁处置：先以原生 `rmdir /s /q` 清理 `%TEMP%\pytest-of-Administrator`
下 43 个轮换 `garbage-*` 目录（682531 条目），再**单独一个轮次**复跑覆盖率门禁，
避免多个 pytest 在同一 turn 累计删除量越界；未使用仓库内 `--basetemp`。
基线态单独复跑结果：exit 0，`3391 passed, 10 skipped in 194.59s`，
`Required test coverage of 75.0% reached. Total coverage: 92.85%`（未改产品代码的基线态）。
修复后全量门禁结果见第十节。

## 十、修复后复核

> 本区为【迭代】完成后主代理亲自复跑的真实数字，非预期值。

| 项 | 结果 |
|---|---|
| 修复项 | F1–F10 全部落盘：2 MAJOR（F1 `is_text_file` 改增量解码 + 2 条负向回归用例、F2 `terminal.shutdown` 日志）；13 MINOR 含 F3/F4/F5 可观测性三组、F6a–e 五处低复杂度替代、F7 缓存副本、F8 文档路径、F9 规则登记；D1–D8 登记不修项在第五节逐条列理由。 |
| 收尾复核 | `code-review-expert` 按 `.trae/agents/code-review-expert.md` 剧本只读复核（92 次工具调用 / 250.09s），总裁定 REQUEST_CHANGES：0 BLOCKER / 0 MAJOR / **4 MINOR**（`_resolved` 冗余状态与注释失真、README 索引断链、本区待回填、修复方案 F6d「既有单测」陈述不实且建议补边界用例）。四项全部闭环：删 `_resolved` 字段及两处写入、补 #57 索引行与增量段、本区回填、更正风险行并新增 `test_nearest_index_bisect_boundaries`（改走公开 `next()` 以避开 pyright `reportPrivateUsage`）。复核者未复跑门禁（主代理已亲跑）、未逐条回读 D3/D5/D6/D8/D10/D11/D12 七维证据，范围限制如实登记。 |
| 六道门禁 | 最终态（全部主代理亲跑；`-q` 无汇总行时以 exit code 为准）：pyright **0**（`0 errors, 0 warnings, 0 informations`）；全量 pytest `-n auto` **0**；架构 **0**（37/37 守卫）；覆盖率 `--cov=yate --cov-branch -n auto` **0**（`3394 passed, 10 skipped in 157.48s`，`Total coverage: 92.90%`，阈值 75 单源于 `pyproject.toml`）；冒烟 `--jobs 4` **0**（`121/121 scenarios passed`、`1463/1463 checks (100%)`、81.74s）；changelog check **0**（`released changelog sections are up to date`）。 |
| safe-delete 处置 | 覆盖率与架构门禁在「同一 turn 连跑多个 pytest」时两次被本机钩子以 `count 18377 / 13054 > threshold 9999` 杀进程（无 FAILED、无汇总行）；按项目记忆以原生 `rmdir /s /q` 分批清 `%TEMP%\pytest-of-Administrator` 下 43 个 `garbage-*` 目录，并把每道门禁拆到独立轮次执行，六道最终全绿。未使用仓库内 `--basetemp`。 |
| 复核裁定 | **APPROVE**：0 BLOCKER / 0 MAJOR；13 MINOR 全部修复或按理由登记不修，收尾复核 4 MINOR 亦销账，六道门禁全 exit 0。 |
