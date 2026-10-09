# closure-sweep-reviews-plan-c（任务 4：reviews 非闭环点核实与修复）

来源：用户指令「修复 reviews 下非闭环的点；除非无法修复，不管是否标注登记不修复都要修复」。
核实基准：2026-10-09 代码（两路只读探索取证，见 overview）。
索引来源：`.trae/reviews/README.md` §一（40 条总索引）+ `legacy-issues.md`。

## 一、核实结论汇总

- 仍成立且本轮修复：R1–R16（§二）。
- 已被后续重构消除，销项登记：VISUAL `>` count 语义（vim.py 已正确）、diff tab 行
  高亮偏移（diff_pane.py 已改字符索引映射）、`os.replace` 失败路径（document.py
  docstring 已文档化）、wiki.py `import io` 并存（已不存在，但 tests 侧两文件仍并存 → R13）。
- 无法修复 / 维持已批准取舍，闭环登记（§三）：7 组。

## 二、修复清单

### Wave C1（主代理，`yate/` + 直接耦合测试）

| # | 出处 | 修复 | 文件 |
|---|---|---|---|
| R1 | #16.1 | `_submit_save_as`：`saved = True` 移到 `doc.save()` 成功后立即设置（"写入即成功"），后续 `set_root`/`refresh_tree` 失败不再回锁 | `yate/flows/document_flows.py` |
| R2 | #26 | `_saveas` / `_split` / `_vsplit` 的 `_strip_quotes` 调用补前置 `.strip()` | `yate/commands.py` |
| R3 | #8 | `_apply_theme` 去 `refresh_tree()`：新增轻量 `_retheme`（保结构 re-label + 背景色），切主题不再全量重建树/重扫目录 | `yate/editor_view/explorer.py` |
| R4 | #16.3 | blocked-build 消息 `%s` → `%r`，同步测试断言 | `yate/editor_syntax/ts_backend/languages.py`、`tests/test_syntax_engine.py` |
| R5 | #23.1 | split 不变量裸 `assert` → 显式 `ValueError`（`-O` 安全） | `yate/session.py` |
| R6 | #18.3 | vsc `cut` 原子性：先取文本 → 删除 → 再写寄存器/剪贴板（对齐 vim `_store_deleted`）；新增只读 cut 不污染寄存器回归用例 | `yate/actions.py`、`tests/test_clipboard.py` |
| R7 | #21.3 | 补 `@override`：`diffview.py` `on_mount`/`on_unmount`、`diff_pane.py` `on_unmount`、`explorer.py` `on_unmount` | 对应 3 文件 |
| R8 | #21.2 | `render_line` 超长行预截断（`text_w * 2 + tab_width` 上限）后再展开，可视区输出不变 | `yate/editor_view/diff_pane.py` + 渲染用例 |
| R9 | legacy 权衡 2 | `_stringified_imprecise` 升级为嵌套字符串化注解检测（子串/递归），负向演练 `"list[App[Any]]"` 拦截 | `tests/test_architecture.py` |

### Wave C2（子代理并行，tools/tests 独占文件）

| # | 出处 | 修复 | 文件（独占） |
|---|---|---|---|
| R10 | #23.2 | `_pkg_path` 与 `SpecInputs.pkg_path` 去重（统一到方法） | `pack/_common.py`、`tests/test_pack_spec.py` |
| R11 | #23.3 | `read_tags` 改 NUL 分隔解析 | `tools/changelog/gitdata.py`、`tests/test_changelog_tool.py` |
| R12 | #30 M3 | `test_smoke_cli.py` 补 autouse 全局状态隔离 fixtures（对齐 test_smoke_harness） | `tests/test_smoke_cli.py` |
| R13 | #34 M3 | `import io` 与 `from io import StringIO` 并存清理（统一 `from io import StringIO`） | `tests/test_pack_wiki_errors.py`、`tests/test_pack_wiki_parallel.py` |
| R14 | #34 M2 | AST 结构守护补"重构须同步"告警注释 | `tests/test_pack_wiki_errors.py` |
| R15 | #40 M1 | 排水 timeout `5.0` 抽 `_DRAIN_TIMEOUT_S` 常量 | `tools/smoke_test/scenarios/_base.py` |
| R16 | #40 M2/M3 | `0x1000` 命名为 `PROCESS_QUERY_LIMITED_INFORMATION`；`pause(0.15)` 改由 `_SEARCH_DEBOUNCE_S` 推导 | `tests/test_shell.py`、`tests/test_app_manual.py`、`tests/test_app_palette.py` |

子代理须遵守 subagent-workflow §二任务书纪律：只改独占清单文件；验证命令用
worktree `.venv\Scripts\python.exe -m pytest <相关文件> -q`；回报改动清单 + 命令实测结果。
主代理回收后重跑其名下测试（只认落盘结果）。

## 三、闭环登记（无法修复 / 维持已批准取舍，附理由）

| 出处 | 条目 | 登记理由 |
|---|---|---|
| #4 | Gitee Go 3.12 流水线验证 | 外部基础设施触发，本地不可执行 |
| #10 | PB5 三终端人工矩阵 | 需真机人工复测，无人值守会话不可执行 |
| #14 | logs.py 桥 handler 工厂内定义 | textual 懒加载硬约束（模块顶层 import textual 违反 R12 导入面），唯一实现形态 |
| #9 | scrollbars 复刻上游 1/8 算法 | 有意复刻 + `tests/test_scrollbars.py` 回归守卫，非缺陷 |
| #11 | textobjects 无界扫描 | 与已批准偏离记录绑定：截断上限会让深层嵌套配对静默失配（正确性 > 性能） |
| #18.3.2 | vsc paste 只读静默返回 | 与现行显式抛错契约冲突，`test_paste_action_on_read_only_buffer_does_not_prime_register` 已锚定；采纳需先推翻契约，非本轮可决 |
| #25 | G9-3 `closes_block` 未接线 / G9-2 均值基准 | 实验性接缝已标记（docstring）；均值基准为评审自评的刻意选择（余量 500×） |
| #31 | R-09/R-10/R-13 接受为风险 | 修法与已定案语义冲突（R-05 排空不变式 / `translate_via_cmd` 公开签名），附原理由保留 |
| #33 | O-1 shell=True 孙进程 / O-2 抗杀线程泄漏 | 进程组 / Job Object 属选型变更级工程，另案登记（O-3 docstring 精确化并入 R12 所在文件顺带处理） |
| #7 | 输入线程宽 except 残余建议 | `log.exception` 已落堆栈；UI 通知/重置驱动与 stock 复刻基线张力，维持待上游对齐 |
| #35 | A12 插件事件订阅 / A19 sprites 合并 | 新功能开发 / 角色数未达评估线，原登记有效 |

## 四、收尾

1. 门禁：pyright 0 + `pytest tests/ -q` 全绿 + 架构 28+ 用例 + 覆盖率 `--cov-fail-under=75` + 冒烟。
2. 回填：`reviews/README.md` §一逐条更新处置状态（含新登记闭环理由）；本计划 §五执行结果；
   `overview.md` 勾选状态。
3. 提交：分主题 `fix(...) / test(...) / refactor(...) / docs(...)` 多笔，英文 conventional。

## 五、执行结果回填（2026-10-09 收尾）

### 5.1 提交清单（分支 fix/closure-sweep，worktree ../yate-closure-sweep）

| 提交 | 内容 | 对应项 |
|---|---|---|
| ac70997 | fix(flows): saveas lift 紧随写盘 | R1（#16.1） |
| 0882770 | fix(commands): ex args 先 strip 再剥引号 | R2（#26） |
| 03613ff | fix(view): explorer 主题切换就地重标签 | R3（#8） |
| b368f1c | fix(syntax): blocked-build 警告统一 %r | R4（#16.3） |
| c88074f | refactor(session): split 不变量 ValueError | R5（#23.1） |
| 9f8cb42 | fix(actions): cut 先删除后写寄存器 + 只读回归 | R6（#18 三轮 #1） |
| bb278fd | perf(view): diff 行展开按可视窗预截断 | R8（#21.2） |
| c7503b7 | refactor(pack): pkg_path 单一事实来源 | R10（#23.2） |
| 577a26a | fix(changelog): tag ref NUL 分隔解析 | R11（#23.3） |
| a2b4f16 | refactor(smoke): _DRAIN_TIMEOUT_S 常量 | R15（#40 M1） |
| cef2fdb | test(wiki): io 导入统一 + 守护重构告警 | R13/R14（#34） |
| daf7183 | test(smoke): CLI 测试主题隔离 fixture | R12（#30 M3） |
| d9d8422 | test: win32 常量命名 + 防抖暂停推导 | R16（#40 M2/M3） |
| 7781cf7 | test(arch): 嵌套 App[Any] 守卫 + tools 体量守卫 + 规则同步 | R9 + plan-b S2 |
| d0e6cc6 | docs(wiki): 中断路径注记声明 + emit 折行精确化 | F-O + O-3 |

### 5.2 门禁实测（主代理亲自执行，退出码均为 0）

| 门禁 | 结果 |
|---|---|
| pyright yate/ tests/ tools/ pack/ | 0 errors / 0 warnings / 0 informations |
| pytest tests/ -q | 全绿（0 failures） |
| pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 | 覆盖率 **91.41%** |
| tools.smoke_test run | **107/107** 场景、1286/1286 checks、exit 0 |
| 负向演练 1（R9） | 嵌套 `"list[App[Any]]"` 被守卫捕获（临时文件 :3） |
| 负向演练 2（S2） | 移除豁免后体量守卫捕获 `tools/pack/wiki.py`（1487） |

### 5.3 偏离计划记录

1. **模型指定不可用**：DeepSeek-V40-Pro / GLM-5.3-Flash 指定无法满足——运行时无
   模型选择能力；计划与执行由当前会话承担，已向用户声明。
2. **R7（#21.3 @override）反转**：pyright strict 实证 `Screen` / `Tree` 基类无同名
   `on_mount` / `on_unmount` hook，`@override` 非法（4 处 reportGeneralTypeIssues）；
   复核结论改为"评审误判，维持现状"，已回填 reviews/README #21 行。
3. **plan-b S1 反转**：豁免名单行数复测（splitlines 口径）证明原名单正确，
   "行数过期"系 `Measure-Object -Line` 不计空行的初扫误报；buffer.py 维持豁免。
4. **R11 子步骤无对象**：test_changelog_tool.py 经 grep 核实 monkeypatch 在函数
   边界注入 TagRef、无伪造原始行可改，子代理如实上报零改动，采纳。
5. **R16-M3 收窄**：4 处 `pause(0.15)` 中仅 1 处为搜索防抖（test_app_manual:295），
   其余 3 处等待语义不同，按"逐处核实"指示保持原样。
6. **子代理重试**：首轮 2 个 coder spawn 被运行时中止（code=10003）；按
   subagent-workflow §五.4 换 plan-executor 角色重试一次，两批均成功回收
   （104 passed / pyright 0；timing 抖动 1 例重跑排除）；主代理重跑其名下
   全量 pytest 复核通过。
7. **维持登记项**：§三所列 11 组按登记理由维持（"无法修复除外"的适用集合），
   已在 reviews/README.md §一尾部署注节公开。
