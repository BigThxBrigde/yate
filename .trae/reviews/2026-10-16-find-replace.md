# 2026-10-16 find-replace（PR 预审与修复闭环）

- 范围：分支 `feat/find-replace-complete`，`c326922..HEAD`（6 个特性提交），
  对应 Gitee issue IKL7AT。模式：pr-review `review`。
- 结论：**REQUEST_CHANGES**（2 MAJOR，无 BLOCKER）。
- 修复方案：[`.trae/documents/find-replace-complete-review-fixes-plan.md`](../documents/find-replace-complete-review-fixes-plan.md)
  （2 MAJOR 已修，终态见文末二轮复审）。

## 硬门禁实测（全绿）

| 门禁 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings | 0 |
| `python -m pytest tests/ -q` | 全绿（8 个既有 skip） | 0 |
| `python -m pytest tests/test_architecture.py -q` | 31 passed | 0 |

## 架构边界核对（无违规）

R2 无新 Protocol；R3 `find_replace.py` 只依赖 editor_core/textual/theme；
R6 无 TYPE_CHECKING/Any；R9 新 screen 自持 DEFAULT_CSS（不触外壳 app.tcss）；
R10 消费键才 stop+prevent_default；R11 `UI_FROZEN_FILES` 已登记
`yate.editor_view.find_replace`；R12 日志全走 tracing 惰性 %；
R13 主题经 `theme.attach` 自持。命名无 `*Feature/*Host/*Ops/*Delegate/*Controller`。

## 发现

### [MAJOR] yate/editor_view/find_replace.py:453-459 — 磁盘替换路径破坏行尾与分隔符保真

问题：`_replace_on_disk` 以 `text.splitlines(keepends=False)` 切行、
`"\n".join` 后 `write_text`（未传 `newline`）。三重后果：

1. `splitlines` 把 `\r`、`\v`、`\f`、`\x1c`-`\x1e`、`\x85`、`\u2028`、
   `\u2029` 都当行界——文件中合法存在的这些字节（如 `\u2028`）会被
   拆行再以 `\n` 重接，**替换区域之外的内容也被改写**；
2. `write_text` 默认 `newline=None` 把每个 `\n` 翻译为 `os.linesep`：
   Windows 上 LF 文件被静默改成 CRLF，POSIX 上 CRLF 文件被改成 LF
   （编辑器本体 `Document.save` 是按 open 时记录的 EOL 回写的，二者不一致）；
3. 行语义与 `TextBuffer`（只按 `\n` 切）发散，同一次替换在
   "打开的 buffer" 与 "磁盘文件" 两条路径下行为不同。

修复方向：改用 `text.split("\n")`（与 buffer 同语义、与 `join("\n")`
互逆、字节级往返），以 `write_bytes` 落盘绕开换行翻译。

### [MAJOR] yate/editor_view/find_replace.py:457-462 — 直接 write_text 非原子落盘

问题：仓库自身的耐久性标准见 `yate/editor_core/document.py:190-259`
（`Document.save` docstring 明言"mid-write 崩溃/满盘不得破坏原文件"，
实现为 sibling 临时文件 + `os.replace` + 权限位继承）。项目替换对
未打开文件的写盘绕开了这一标准，崩溃可能截断用户文件。

修复方向：对齐 `Document.save` 的临时文件 + `os.replace` 原子写
（含 `shutil.copystat` 权限继承；时间戳按 save 惯例取当前）。

### [MINOR] yate/editor_view/find_replace.py:240-258 — 命中文件二次读盘（缓办）

`_scan` 对每个命中文件在 `search_files` 已读过一遍后为取片段再读一遍。
量级受 `max_matches=2000` 约束，可接受；后续可让 `search_files` 顺带
返回命中行文本。登记为 follow-up，不在本轮修。

### [MINOR] yate/editor_view/find_replace.py:379-381 — 空替换串被守卫拦截（缓办）

`find == "" or replacement == ""` 的守卫使"删除全部匹配"（空替换）
这一合法用例不可达。计划 plan-c §4.2.12 明文规定了该守卫（已批准的
决策），按计划执行；登记为 follow-up issue 候选，不在本轮修。

## 优点（Strengths）

- 确认循环终止性论证写入 docstring 且有 engine 级 + pilot 级双重锚定；
- `replace_lines` 与 `SearchEngine.replace_all` 的逐匹配 sub 语义有
  黄金对齐测试（D4b 风险收口干净）；
- reveal 时序（异步 open worker 覆盖光标）有专项用例实证；
- 门禁真实跑通，架构守卫对新文件零豁免全遮盖。

## 二轮复审（修复 diff `2f2c652` + `3d2f2f6`）

- 范围：`_replace_on_disk` 保真/原子化改造 + 2 个回归用例 + 评审文档。
- 门禁：pyright 0 errors；`pytest tests/ -q` 退出码 0；架构 31 passed。
- 新发现并当场修复：`mkstemp` 原在 try 块外，目标文件在搜索与替换之间
  消失会以 `FileNotFoundError` 中断整批替换、违背 docstring 的跳过契约
  （`3d2f2f6` 修正为守卫内 stage + 跳过该文件继续）。
- 复核通过项：`split("\n")`/`join("\n")` 双射（CRLF/LF/CR 字节级往返，
  用例锚定）；原子写对齐 `Document.save`（权限位继承、时间戳取新鲜值、
  `os.replace` 同卷原子换入、失败路径清临时文件）；无架构违规。
- 结论：**无遗留 issue**；2 MINOR 维持缓办（follow-up，不阻塞合并）。

## 三轮复审（code-review-expert，全分支 diff，2026-10-16）

- 范围：`4380528...HEAD`（30 文件，+3462/-20，12 提交）。技能：
  python-code-review + TRAE-code-review 双清单合并。
- 门禁实测全绿（pyright 0 / pytest 0 / 架构 31）。
- 结论：**REQUEST_CHANGES** — 3 MAJOR + 4 MINOR：
  - M1 `reveal_match` 行越界：`buf.lines[row]` 先于 `set_cursor` 钳制求值，
    buffer 未保存删行后 enter 崩溃（[editor.py](../../yate/editor.py)）；
  - M2 搜索/片段侧 `splitlines()` 与 TextBuffer/替换侧 `split("\n")`
    行视图不一致：reveal 错行、CRLF `$` 锚搜索命中/替换不命中的矛盾；
  - M3 结果面板无滚动跟随：1fr Static 不产生虚拟溢出，命中超一屏后
    `>` 光标不可见（探针实证 virtual_size 恒等于容器高）；
  - m1 跨匹配边界断言计数虚增（与 `replace_all` 既有取舍一致，仅补披露）；
    m2 walk 5000 文件上限静默截断；m3 replace worker 重读实时输入与
    磁盘路径快照漂移；m4 `_replace_scope_all` O(n²) 去重。
- 修复：`d3c7c94`（F3-F9，见
  [find-replace-complete-review-fixes-plan.md](../documents/find-replace-complete-review-fixes-plan.md)
  §五）——行视图统一 `split("\n")` + 片段 `rstrip("\r")`、reveal 先钳行、
  `VerticalScroll` 容器承载 auto 高度结果面板并滚动跟随光标、worker
  改收引擎快照、`dict.fromkeys` 去重、截断提示、docstring 披露；
  新增 6 个测试（engine 2 + pilot 4）。
- 门禁复测：pyright 0 errors；`pytest tests/ -q` 退出码 0；架构 31 passed。

## 四轮复审（pr-review 技能，全分支，2026-10-16）

- 范围：`4380528...HEAD`（31 文件，13 提交，基线 master）。
- 门禁实测全绿（pyright 0 / pytest 0 / 架构 31）。
- 六维度（功能/安全/性能/可维护性/架构/门禁）逐条核对：**零发现**；
  已修条目与两条 follow-up 按 false-positive 规则不复述。
- 结论：**APPROVE** —— 无 BLOCKER/MAJOR/MINOR 遗留，
  「登记→计划→修复→再审直至无 issue」闭环达成；合入由人工决定。

## 遗留 follow-up 修复（2026-10-16 第二批）

- 输入：第一轮登记的两条 MINOR follow-up；方案见
  [find-replace-complete-review-fixes-plan.md](../documents/find-replace-complete-review-fixes-plan.md)
  §六（含备选与否决、风险回滚）。
- 命中文件二次读盘：`FileMatch` 增量携带 `hit_lines`（row →
  `split("\n")` 视图原始行文本，default 工厂零破坏），`_scan` 删除
  第二次 `read_bytes`；L2 冗余 `_snippets` 字典移除，片段渲染直取
  `hit_lines`（显示侧 `rstrip("\r")`）。
- 空替换守卫：移除 `replacement == ""` 拦截——plan-c §4.2.12 决策
  推翻（`replace_lines` / `replace_all` 实测均原生支持空替换删除，
  测试与手册未锚定旧守卫），"删除全部匹配"可达；守卫仅剩 find
  非空，消息改 "find field must be filled"。
- 新增 3 个测试（engine 2 + pilot 1）；四项人工验证项不在本轮
  （无头环境无法执行）。
- 门禁复测：pyright 0 errors；`pytest tests/ -q` 退出码 0；
  架构 31 passed。
- 结论：两条 follow-up 关闭，评审闭环无遗留。
