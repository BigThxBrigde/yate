# 2026-11-02 filemgr-wrapup 评审记录

- 对象：分支 `ref/filemgr-wrapup`（自 master `4a4f900`，v0.2.16），issue IKS4CT
  （filemgr 收尾：R1 中栏万级条目增量刷新 + R2 独立包迁移 + R3 遗留清扫）。
- 方案：[`filemgr-wrapup-plans/`](../documents/filemgr-wrapup-plans/overview.md)
  （overview + plan-a/b/c，执行记录已回填各子计划）。
- 本记录为只读事实文档；修复落点见文末「处置登记」。

## 第一轮：python-code-review（六维）

结论 **MINOR ISSUES**（无 CRITICAL）。实测门禁：pyright 0 / pytest 全量绿 / 架构 37 passed / filemanager 冒烟场景 17/17。

| # | 发现 | 级别 | 处置 |
|---|---|---|---|
| W1 | R15 滚动条守卫扫描面被包迁移击穿：`test_scrollable_widgets_apply_theme_scrollbar_pair` 非递归 `glob("*.py")` 扫不到迁入子包的 `filemgr/screen.py`（定义 `_FileListView(ListView)`），守卫对恰好被迁移的模块静默失明 | WARNING | 修复：glob → `rglob`（提交 `7bdad83`），逐模块核对扩面零误报；规则文档 §六 #37 与 R15 条目同步递归口径（`a7bf55c`） |
| W2 | mtime 同刻度竞态：coarse-mtime 文件系统（FAT32/网络共享 1-2s 刻度）上同刻度变更可短期钉死陈旧列表（NTFS/ext4 纳秒级自愈） | WARNING | 登记：`_lookup_dir_listing` docstring 补残余窗口说明，`r` 强刷兜底（`7bdad83`）；不改机制（mtime 键控缓存固有界限） |
| W3 | `tests/test_manual.py` docstring 的 `is_mounted`→`is_attached` 修正游离未提交 | WARNING | 补提交（`7bdad83`） |
| S1 | 缓存命中下外部修改文件内容不推目录 mtime，size/mtime 装饰与 size 排序陈旧至 `r`（相对 master 的可见差异；plan-b 已登记为划出缓存职责的接受项） | SUGGESTION | 登记：`DirListing` docstring 补边界说明（`7bdad83`）；手册语义（`r` invalidate + re-list）与实现一致，不追加光标单条 re-stat（避免行为变化） |
| S2 | 跨目录导航时 `_stats` 累积既往目录条目（全部消费方按当前 entries 查找，无正确性影响，内存上界可忽略） | SUGGESTION | 注记：`_reload` 缓存命中路径注释补充"跨目录累积无害"论证（`7bdad83`） |
| S3 | `test_filemgr_mutations_drop_dir_cache` 尾注对 "sub" 4 次 list_dir 的归因错误（rename 重扫列的是 cwd 而非 sub） | SUGGESTION | 修正注释为真实来源（mount 预览 + rename 后光标落回的预览 + paste/delete 重扫）（`7bdad83`） |

## 第二轮：pr-review（PR 级，review 模式）

结论 **APPROVE**（无 BLOCKER/MAJOR，1 条 MINOR）。硬门禁实测：pyright 0 / pytest 全量绿 / 架构 37 passed；coverage 以"修复波零运行时代码（全为 docstring/注释）"注记沿用首轮实测 92.81%；变更面 L2 为主（filemgr 子包 + 三文件清扫）+ L3 一处导入 + tools/tests/文档。

| # | 发现 | 级别 | 处置 |
|---|---|---|---|
| M1 | 规则文档 §三.7 `screen.py` 豁免行数落后（954 vs review-fixes 波后实测 963） | MINOR | 同步为 963（提交见本记录末行；plan-c 执行记录同步） |

## 评审修复提交

- `7bdad83` fix(review): review fixes for filemgr wrap-up（W1/W3/S1/S2/S3 + 计划文档执行记录回填）
- `a7bf55c` docs(rules): note the R15 guard scan is recursive over editor_view subpackages
- 行数 963 同步随评审记录落盘提交（`docs(reviews): record filemgr-wrapup review rounds`，与本记录同一提交；规则文档 §三.7 与 plan-c 执行记录同步更新）

## Strengths（两轮共同）

- stamp 先于扫描的时序论证落在代码里（陈旧列表不可能钉在新 stamp 下）；`(path, show_hidden)` 键承载可见性切换且有专项测试。
- mutation 清缓存以 grep 枚举定案并落盘；`toggle_hidden` 有意不 drop 附带反证理由。
- is_mounted 清扫 9 处逐一甄别（全部换 `is_attached`，宿主可达性逐处核实），清单外存量逐处清点并说明不扫理由。
- 性能收益实测背书：热 `_reload` 0 次 list_dir、目录预览 8.8×，诚实标注 j/k 墙钟测量边界。
- W1 是真修复（恢复守卫递归扫描面）而非补丁式放行（未把 screen.py 加豁免集）。
