# big-module-split 计划（issue IKK5F7）

来源：<https://gitee.com/jermaine/yate/issues/IKK5F7>（ENHANCE - 大模块拆分）。
分支 `ref/big-module-split`，worktree `../yate-big-module-split`（独立 `.venv` 已自证）。
子计划总纲：[`.trae/documents/big-module-split-plans/overview.md`](big-module-split-plans/overview.md)。

## 一、目标与非目标

### 目标

1. 拆分 `yate/editor_syntax/regex_backend.py`（实测 1225 行）：语言定义
   （`LangSpec`、词表、注册表、内置语言登记）抽到新模块
   `yate/editor_syntax/regex_langdefs.py`（用户定名）；`regex_backend.py`
   只留 regex 构建与 tokenizer 引擎。两文件均降到 800 行以下。
2. 其余可拆模块按子计划波次 b–f 逐波拆分（每波独立提交 + 验收命令）。
3. 规则侧落地：`tests/test_architecture.py` 新增
   `test_source_files_within_size_threshold` 守卫（>800 行必须登记豁免）；
   同步校准 `architecture-boundaries.md` §三.7 行数与豁免名单
   （b–f 各波随拆分完成同步收缩名单，见各子计划"规则侧同步"节）。

### 非目标

- `keymaps/vim.py` 与 `yate/editor.py` 的拆分（§二 论证维持豁免）。
- 架构分层调整：全部拆分为同包/同层内部切分，不改任何依赖方向。

### 模块处置总表

> **行数口径**：本表"实测"列为**含空行**口径（PowerShell
> `Get-Content <file> | Measure-Object -Line`，等价 `.Count`，2026-10-08
> worktree HEAD ab820d4）。issue 原文行数是**不含空行**口径（如
> regex_backend 1097），两套数字不可混用；issue 所列 `config.py: 924` 已
> 过时——A9 拆分后（加载器迁入 `yaterc.py`）实测 330 行，不再超标。

| 文件 | 实测 | 处置 | 波次 | 拆分后预估 |
|---|---|---|---|---|
| `editor_syntax/regex_backend.py` | 1225 | 拆 → `regex_langdefs.py` | a | ~490 / ~780 |
| `editor_view/diffview.py` | 1035 | 拆 → `diff_pane.py` | b | ~600 / ~490 |
| `editor_view/editor.py` | 1007 | 拆 → `highlighting.py` + `welcome.py` | c | ~680 / ~300 / ~115 |
| `keymaps/vim.py` | 1117 | **维持豁免**（详见 §二） | — | 1117 |
| `editor.py` | 933 | **维持豁免**（详见 §二） | — | 933 |
| `editor_core/buffer.py` | 888 | 拆词运动 → `words.py` | e | ~822（仍豁免）/ ~85 |
| `editor_term/emulator.py` | 861 | 拆 → `palette.py` + `keys.py` | e | ~775 / ~50 / ~80 |
| `editor_lsp/manager.py` | 833 | 拆解析 → `parsing.py` | f | ~630 / ~230 |
| `editor_view/theme.py` | 805 | 拆 → `themes.py` + `cells.py` + `theme_files.py` | d | ~140 / ~500 / ~80 / ~75 |
| `yaterc.py` | 803 | 拆 → `yaterc_options.py` | f | ~200 / ~630 |

## 二、维持豁免的文件（否决理由，均已实测核对）

- **`keymaps/vim.py`（1117）**：模块 docstring 一句话可概括；全部职责块经
  `self` 上 9 个 chord 状态字段交织引用（NORMAL 分发横跨 9 块、VISUAL 与
  NORMAL 共用寄存器状态、count 语义散布三处），不存在"互不引用的职责块"，
  不满足 A11 拆分判据。唯一低耦合候选（build_bindings + 类目常量，~97 行）
  迁出后 vim.py 仍 ~1020 行，无解阈值，纯 churn。剪贴板桥接还被
  `tests/test_vim_keymap.py:1458` monkeypatch 钉住。→ 维持豁免并更新登记行数。
- **`yate/editor.py`（933）**：构造工厂群 ~243 行是流程模块显式构造注入纪律
  的直接产物（顺序敏感，注释记录依赖链）；Editor 类核心 ~500 行是全仓唯一
  L3 App 句柄持有者/能力分发点，方法皆为 3–15 行薄动词；已有 6 个职责
  迁入 flows/*（docstring 标注 "Extracted from yate.editor"）。唯一候选
  `theme_flows.py` 仅迁 ~78 行，且触发 R11 `UI_FROZEN_FILES` 新登记 +
  commands.py apply 映射改动，成本 > 收益。→ 维持豁免并更新登记行数。

## 三、波次调度（子计划见 big-module-split-plans/）

| 波次 | 子计划 | 内容 | 触碰面 |
|---|---|---|---|
| a | [big-module-split-regex-langdefs-plan-a.md](big-module-split-plans/big-module-split-regex-langdefs-plan-a.md) | regex_langdefs 抽取 + 行数守卫 + 规则校准 | editor_syntax、tests、.trae/rules |
| b | [big-module-split-diff-pane-plan-b.md](big-module-split-plans/big-module-split-diff-pane-plan-b.md) | diffview → diff_pane | editor_view、3 个测试、tools |
| c | [big-module-split-view-highlight-plan-c.md](big-module-split-plans/big-module-split-view-highlight-plan-c.md) | editor_view/editor → highlighting + welcome | editor_view、1 个测试 |
| d | [big-module-split-theme-registry-plan-d.md](big-module-split-plans/big-module-split-theme-registry-plan-d.md) | theme → themes/cells/theme_files（门面） | editor_view（40+ 引用零改动） |
| e | [big-module-split-leaf-extracts-plan-e.md](big-module-split-plans/big-module-split-leaf-extracts-plan-e.md) | buffer→words；emulator→palette/keys | editor_core、editor_term、keymaps、flows、tests |
| f | [big-module-split-lsp-yaterc-plan-f.md](big-module-split-plans/big-module-split-lsp-yaterc-plan-f.md) | manager→parsing；yaterc→yaterc_options | editor_lsp、yaterc、tests |

**调度纪律（硬性）**：

- **a 波先行**：b–f 依赖 a 落地的行数守卫与全量豁免名单。
- **b–f 必须串行，不得并行**：产品源码文件波次间互不重叠，但每波都要改
  `tests/test_architecture.py`（豁免集合逐波收缩）与
  `.trae/rules/architecture-boundaries.md` §三.7（豁免名单收缩）两个共享
  文件——文件重叠即不可并行。上一波验收命令全部退出码 0 才进入下一波。
- 每波收尾跑该波子计划所列验收命令；全部波次结束后统一全量门禁
  （pyright + pytest + 架构测试 + 覆盖率，命令见 plan f 末节）。

依赖关系图与执行状态追踪表见
[big-module-split-plans/overview.md](big-module-split-plans/overview.md)。

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| 循环导入 | 每个子计划显式声明 import 方向并验证单向 |
| 测试 monkeypatch 私有名失效 | 子计划逐个登记 patch 面（如 `_tokenize_with_states`、`_welcome_lines`、`CHANGE_DEBOUNCE_S`、`copy_text`）并同步改 patch 目标或保留薄委托 |
| 架构守卫白名单（UI_FROZEN_FILES / UI_FREE_FILES）漂移 | 各子计划列出需登记/无需登记的判定 |
| 共享守卫文件导致并行冲突 | b–f 强制串行（§三），每波独占 `tests/test_architecture.py` 与 rules §三.7 的修改窗口 |
| 回滚 | 每波独立提交，`git revert` 单笔回退 |

## 五、执行记录（回填，与 overview.md §三 状态追踪表同构）

| 波次 | 状态 | 验收命令退出码 | 提交（hash/说明） | 偏离记录 |
|---|---|---|---|---|
| a（regex_langdefs + 行数守卫） | 已完成 | 4/4 退出码 0（pyright `yate/editor_syntax/` 零诊断；pytest 5 文件 `-q` 通过，1 个 py-tree-sitter 可选依赖既有 skip；`available_filetypes()` 探针 = 72，与 HEAD 基线一致；行数实测 regex_langdefs 794 / regex_backend 500） | `074ed7d` refactor(editor_syntax): extract regex_langdefs from regex_backend | 实测行数 794/500，略高于预估 ~780/~490（含模块 docstring 与 `__all__` 开销），均在阈值内。私有注册表再导出为满足 pyright 零诊断，除 `regex_backend.__all__` 外还需在声明模块 `regex_langdefs.__all__` 登记 `_LANGUAGES` / `_NAME_TO_KEY`（否则 `reportPrivateUsage` 报错），导入方向仍单向、无行为改动 |
| b（diffview → diff_pane） | 已完成 | 3/3 退出码 0（pyright `yate/editor_view/` 零诊断；pytest 4 文件 `-q` 96 passed；行数实测 diff_pane 475 / diffview 581）。波次收尾前置项 `pyright yate/ tests/ tools/` 另测零诊断 | `966a686` refactor(editor_view): extract diff_pane from diffview | 实测行数 475/581，与预估 ~490/~600 相符（迁移时 diff_pane 无日志调用，未引入 `yate.logs` 依赖，导入面与 plan-b 依赖清单一致） |
| c（editor_view/editor 拆分） | 已完成 | 3/3 退出码 0（pyright `yate/editor_view/` 零诊断；pytest 4 文件 `-q` 41 passed；行数实测 highlighting 416 / welcome 128 / editor 599）。波次收尾前置项 `pyright yate/ tests/ tools/` 另测零诊断 | （待主代理提交） | highlighting.py 实测 416 行高于预估 ~300：`HighlightMixin` 落成纯 mixin（不继承 Widget）——双基类 `EditorView(ScrollView, HighlightMixin)` 会把 Textual 内部 `scroll_to` 签名分裂（`ScrollView.scroll_to` 缺 `release_anchor`）暴露为 pyright 基类冲突，故 mixin 以纯声明桩镜像其用到的 4 个 Widget 成员（doc/is_mounted/refresh/set_timer/run_worker，~55 行，运行时 MRO 中 Widget 真实成员在前、桩永不生效）；`EditorView.doc` 相应补 `@override`。welcome 侧 `_WelcomeRow` 经 `__all__` 登记后供 editor.py 缓存注解导入（沿 a 波私有再导出先例）。editor.py 实测 599 低于预估 ~680。提交 `7e32bcc` refactor(editor_view): extract highlighting and welcome from editor_view |
| d（theme 拆分） | 已完成 | 4/4 退出码 0（pyright `yate/editor_view/` 零诊断；pytest `test_theme_palettes.py`+`test_config.py` `-q` 134 项全过；门面探针 `from yate.editor_view.theme import THEMES, active, set_theme, cell_len` → `len(THEMES)=8`；行数实测 themes 575 / cells 98 / theme_files 102 / theme 182）。波次收尾前置项 `pyright yate/ tests/ tools/` 另测零诊断 | （待主代理提交） | 实测行数 575/98/102/182 高于预估 ~500/~80/~75/~140：差额来自三个新模块的模块 docstring 与 `__all__`、theme 门面的再导出导入段 + `__all__`（~40 行），四文件均远低于 800 阈值。一处记录在案的必要处置：`tests/test_theme_palettes.py:191/261` 经 `theme._theme_namespace()` 使用加载器命名空间，而该测试文件不在 d 波独占清单内，为守住"外部 import 零改动"不变量，按 a 波私有再导出先例在 `theme_files.__all__` 与 `theme.__all__` 登记 `_theme_namespace`（导入方向仍单向无环，无行为改动）。提交 `ece4f89` refactor(editor_view): split theme into themes, cells and theme_files |
| e（words + palette/keys） | 已完成 | 3/3 退出码 0（pyright `yate/editor_core/` + `yate/editor_term/` 零诊断；pytest 6 文件 `-q` 398 passed / 1 既有 skip；行数实测 words 82 / buffer 820 / palette 47 / keys 74 / emulator 757） | （待主代理提交） | ① plan-e「buffer.py 对词函数零内部调用、无需新增 import」断言实测为假（buffer.py:578/598/609/625 共 4 个调用点），按主代理裁决采纳方案 X：照常拆出 words.py 并在 buffer.py 头部新增 `from yate.editor_core.words import next_word_start, prev_word_start, word_end`，判据修正为「word_span 与缓冲主体零耦合 + 词函数为无状态纯函数、消费面在 textobjects/vim/mouse_flows」（plan-e 文档已同步修正）；② emulator.py 保留 `key_to_terminal` 再导出导入触发 pyright `reportUnusedImport`，改为显式再导出写法 `from .keys import key_to_terminal as key_to_terminal` 消除（test_terminal_emulator.py 消费面需要该再导出，零行为改动）；③ 实测行数与预估相符，buffer.py 820 仍 >800 维持 A11 豁免并更新登记（规则 §三.7 与 `SIZE_EXEMPT_FILES` 两处同步）。提交 `67e9d9a` refactor(editor_core,editor_term): extract words, palette and keys |
| f（parsing + yaterc_options） | 已完成 | 3/3 退出码 0（pyright `yate/editor_lsp/` + `yate/` 零诊断；pytest 6 文件 `-q` 239 passed；行数实测 parsing 243 / manager 652 / yaterc_options 669 / yaterc 189）。波次收尾前置项 `pyright yate/ tests/ tools/` 另测零诊断 | （待主代理提交） | ① plan-f 未登记的测试钉面实测存在：`tests/test_lsp.py:668/684` 经 `LspManager._parse_diagnostics` 类属性直调、`:873` monkeypatch `LspManager._unwrap_completion`（该 patch 只有 `request_completion` 经 `self._unwrap_completion` 调用才可拦截）；tests/test_lsp.py 不在 f 波独占清单，按主计划 §四「保留薄委托」预案处置——实现本体全部迁入 `parsing.py`，manager 保留 `_unwrap_completion` / `_parse_diagnostics` 两个转发 staticmethod 且调用点经 `self` 走委托，无测试钉点的 `_parse_completion_item` 调用点改 `parsing.*`（零测试改动）；② manager 对 `_from_utf16` 的转发 import 沿 e 波先例用 `from .parsing import _from_utf16 as _from_utf16` 显式再导出写法消 `reportUnusedImport`，parsing / yaterc_options 被跨模块导入的私有函数在声明模块 `__all__` 登记以消 `reportPrivateUsage`（a 波先例）；③ 实测行数 parsing 243 / yaterc_options 669 略高于预估 ~230/~630（模块 docstring 与 `__all__` 开销），manager 652 / yaterc 189 与预估 ~630/~200 相符，四文件均低于 800 阈值。提交 `c9d2b6f` refactor(editor_lsp,yaterc): extract parsing and yaterc_options |
| 全量门禁 | 已完成 | 主代理亲测全绿：`pyright yate/ tests/ tools/` 零诊断（退出码 0）；`pytest tests/test_architecture.py -q` 27 passed；`pytest tests/ -q --cov=yate --cov-fail-under=75` 退出码 0（2045 passed / 9 skipped，覆盖率 91.44% ≥ 75）；冒烟 `python -m tools.smoke_test run` 107/107 场景、1286/1286 检查全过 | — | 审核代理（code-review-expert）结论：无 blocker / major；2 个 minor（规则 R4 正文与 §六 R12 枚举漏列 `yaterc_options.py`、追踪表未回填）已修正；1 个 info 为 `test_app_manual.py` 单点偶发（单独重跑 5×15 全绿，既有 flaky，与本分支无因果） |

回填纪律：状态只允许 `待执行 → 执行中 → 已完成`；"已完成"必须附验收命令
实际退出码与提交 hash；偏离计划须在"偏离记录"列写明实测依据。本表与
[overview.md §三](big-module-split-plans/overview.md) 逐行对应，两处同步回填。

## 六、审核记录与遗留待办

审核执行了两轮，均按 `../agents/code-review-expert.md` 剧本 + `../skills/python-code-review/SKILL.md`
框架（6 维度 + `[CRITICAL]`/`[WARNING]`/`[SUGGESTION]` 三级等级）：

- **第一轮**（波次 a–f 全部提交后）：无 blocker/major；2 个 minor（规则 R4 正文与
  §六 R12 枚举漏列 `yaterc_options.py`、追踪表未回填）随提交 `73ba503` 修正。
- **第二轮**（按剧本全量复评，含 skill 6 维度扫描新增文件 + 迁移保真逐行比对 +
  branch 覆盖率明细 + 冒烟）：`Overall: LOOKS GOOD`，无 CRITICAL/WARNING；
  新增模块覆盖率全部 ≥82%（words/palette/keys/diff_pane/theme/yaterc 100%，
  最低 `editor_view/cells.py` 82%），无覆盖率倒退。结论：可合并。
  主代理独立复核：全量 pytest 退出码 0、冒烟 107/107 场景 / 1286 checks 全过。

遗留待办（均 `[SUGGESTION]` 级，不阻塞合并，建议合并后另开小任务）：

1. `tests/test_screensaver.py:180` 存量时序敏感用例（`test_parade_keeps_names_distinct_and_sprites_never_overlap`）
   在覆盖率插桩负载下偶发失败（断言下限 31.3 实得 27），与本分支无关
   （diff 未触碰 editor_sprites/screensaver）。建议固定随机种子或放宽下限断言去偶发化。
   同类存量 flaky：`tests/test_app_manual.py` 单点偶发（第一轮实测记录）。
2. `yate/editor_view/highlighting.py` 的 mixin 声明桩签名是手工镜像 Textual 成员
   （doc/is_mounted/refresh/set_timer/run_worker），Textual 升级改签名时桩漂移不会自动报警
   （组合处基类冲突反而会报）。建议在 `keyproto/textual_internals.py` 同款
   "升级 Textual 先查该文件"清单中补记 `highlighting.py`（R12/A2 先例表述）。

两项均已立项修复，方案与执行记录见 §七（2026-10-09）。

## 七、遗留待办修复（2026-10-09）

### 修复 1：两处 pilot 测试偶发去稳定化

- **根因 1（screensaver）**：`ScreensaverScreen.on_mount` 的真实
  `set_interval(1 / TICKS_PER_SECOND, advance_tick)` 在测试手驱 tick 期间仍被
  事件循环调度（coverage 插桩拖慢循环时更频繁），`_tick_count` 领先测试局部
  `tick`；当 interval 在测试读取 walkers 前 spawn 了新 walker（其 `spawn_tick`
  大于测试局部 tick），测试以负 tick 调 `walk_x`
  （`editor_sprites/render.py:58` 的 `% travel` 对负数回绕到右缘），位置失真
  → `tests/test_screensaver.py:180` gap 断言误报（实测 27 < 31.33）。
- **修复**：`ScreensaverScreen` 新增只读 `tick` 属性（与 `walkers` 同为
  测试/遥测视图）；测试改以 `screen.tick`（retire 判定的同一时钟）采样位置——
  active walker 的 elapsed 恒小于其 travel（retire 用同一计数器），
  `walk_x` 永不回绕，间距不变量严格成立。断言本身不变（遵守
  "先重跑确认、不许直接改断言"纪律，subagent-workflow §三.3）。
- **根因 2（manual 搜索）**：`MarkdownDocScreen._SEARCH_DEBOUNCE_S = 0.12`，
  测试用固定 `pilot.pause(0.15)` 只留 0.03 s 余量，coverage 插桩下 debounce
  flush 未及完成 → 状态断言误报。
- **修复**：改用本文件既有 `wait_until` 轮询助手（同文件
  `test_f8_opens_manual_and_esc_closes` 等处理同类问题的既定模式）等待
  `"no matches"` / `"type to search"` 状态翻转，替换两处固定 pause。

### 修复 2：Textual 升级镜像面注记

`yate/keyproto/textual_internals.py` docstring 补记
`yate/editor_view/highlighting.py` 的 HighlightMixin 声明桩（手工镜像 5 个
公共 widget 签名）为 Textual 升级时需同步核对的第二处镜像面
（沿用 R12/A2 "升级先查"先例表述）。

### 验收命令

- `pytest tests/test_screensaver.py tests/test_app_manual.py -q` 连续 10 次全绿；
- 全量门禁：pyright 零诊断 + `pytest tests/ -q --cov=yate --cov-fail-under=75`
  + 架构测试 + 冒烟（主代理亲跑）。

### 执行记录（2026-10-09 回填）

| 项 | 状态 | 实测 |
|---|---|---|
| 稳定性重跑 | 已完成 | `pytest tests/test_screensaver.py tests/test_app_manual.py -q` 连续 **10/10 次全绿**（退出码 0） |
| 全量门禁 | 已完成 | 主代理亲测：pyright `yate/ tests/ tools/` 零诊断（退出码 0）；架构测试 27 passed；`pytest tests/ -q --cov=yate --cov-fail-under=75` 退出码 0（覆盖率 91.43% ≥ 75）；冒烟 107/107 场景 / 1286 checks（退出码 0） |
| 提交 | 已完成 | `fix(tests): drive pilot tests off the screensaver clock and poll search debounces` + `docs(keyproto): note highlighting mixin stubs in the upgrade checklist` + 本提交 |
