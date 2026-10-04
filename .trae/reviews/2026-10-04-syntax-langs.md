# syntax-langs 分支评审（issue IKJLTB 内置语法高亮扩展）— 2026-10-04

> 来源：Gitee PR #53 评论
> [`note_51442774`](https://gitee.com/jermaine/yate/pulls/53#note_51442774_conversation_191380732)
> （conversation `191380732`）。本条目即该评论所对应的分支评审与后续三轮修复的
> 落盘记录：评审结论见下文，修复方案与门禁回填见
> [`../documents/syntax-langs-review-fixes-plan.md`](../documents/syntax-langs-review-fixes-plan.md)。

- **评审对象**：分支 `enh/syntax-langs`（worktree `../yate-syntax-langs`，基线 `master`），7 笔提交 / 51 文件 / +2182 −223，核心是 `yate/editor_syntax/`（23 个新 `.scm` + 13 条 regex 回退 `LangSpec` + `BUILTIN_ENTRY`）、`pyproject.toml` 与 `pack/_common.py` 的 22 个语法包、`yate/extensions/` 5 个 `*.py.example` 模板、7 个文档文件。
- **评审方法**：两件事并行——①按方案文档 [`../documents/syntax-langs-plan.md`](../documents/syntax-langs-plan.md) 逐波次（W1–W5）对账实施完整性；②按 `.trae/skills/python-code-review/SKILL.md` 六维度框架（正确性 / 安全 / 性能 / Pythonic / 可维护性 / 错误处理）做代码评审，3 个只读 `code-explorer` 子代理按互不重叠文件切分并行（regex 后端 + `tests/test_highlight.py` / ts 后端 + 23 个 scm + `tests/test_ts_backend.py` / examples + pack + docs），主代理汇总并**逐条复核**——本文所有条目的问题描述均带主代理实测证据，子代理自述数字不直接引用。
- **基线门禁**（主代理在 worktree 沙箱亲自复跑）：`python -m pyright yate/ tests/ tools/` → 0 errors / 0 warnings / 0 informations；`python -m pytest tests/` → **1718 passed, 7 skipped**；`python -m pytest tests/test_architecture.py` → **22 passed**；`python -m pytest tests/ -q --cov=yate --cov-fail-under=75` → **91.29%**。四项 EXIT=0，与方案 §八 记载一致。
- **总体结论**：`MINOR ISSUES` — 0 CRITICAL / 5 WARNING（计划核对阶段 G1–G5）/ 若干 SUGGESTION。**实施完整性：W1/W2/W4/W5 通过，W3 的验收未执行**（详见 §一）。
- **处置**：**已修复**（2026-10-04，用户批准"全部范围"）。方案、逐条处置与门禁回填见 [`../documents/syntax-langs-review-fixes-plan.md`](../documents/syntax-langs-review-fixes-plan.md)（本文为只读事实记录，结论不因修复而改写）。§一 W3 的"验收未执行"已由 `tests/test_extension_examples.py` 补做：4 个声明式模板经真实 `ExtensionAPI` 注册并断言 tokenize 非空，fsharp 因缺 `tree-sitter-fsharp` 走 `skipif` + 静态捕获名检查。

---

## 一、计划实施核对（W1–W5 逐项对账）

| 波次 | 结论 | 核对证据 |
|---|---|---|
| W1 核心注册表 + scm + 依赖 | ✅ 通过 | `BUILTIN_PACKS` 25 条（`yate/editor_syntax/ts_backend/languages.py:80-106`）+ 新增 `BUILTIN_ENTRY`（`:111-116`）；23 个新 `queries/*.scm` 全部落盘且与 25 个映射双向闭合；`ts` / `dev` extras 各 +22 包（`pyproject.toml:31-52`、`:66-87`）；`pack/_common.py:36-62` +22 模块名；13 条 regex 回退 `LangSpec` 齐备（`regex_backend.py:384-662`）；`yate/extensions/csharp_highlight.py` 已删除且全仓无残留引用（仅测试中的"断言其不存在"） |
| W2 测试 | ✅ 通过 | `tests/test_ts_backend.py` +228 行、`tests/test_highlight.py` +157 行；`test_builtin_packs_ship_a_query_file`（`tests/test_ts_backend.py:611-614`）把"每个 pack 必有 scm"固化为不变式 |
| W3 example 扩展 | ⚠️ **验收未执行** | 5 个模板确已落盘（`batch` / `ini` / `fsharp` / `git` / `diff`），但方案 §四 W3 规定的验收"去掉 `.example` 后注册成功且 tokenize 样例非空"**客观无法执行**——主代理实测 `importlib.util.find_spec("tree_sitter_fsharp") is None`（`tree-sitter-fsharp` 既不在 `ts` extras 也不在 `_TS_PACKAGES`，沙箱未装）；§八 执行记录仅写"5 个 `*.py.example` 落盘"，无验收结论。`fsharp_syntax.py.example:29-47` 的节点名（`function_or_value_definition` / `typar` / `triple_quoted_string`）与 60 余个匿名 keyword token 全部未经实测——而 §八 W1 恰恰记录了 22 个内置 scm 的大量节点名必须按实测修正 |
| W4 文档 | ⚠️ **4 处失准** | 双语成对更新到位（`extensions.*.md` §4.7/4.8、manual FAQ、`yaterc.*.md`、`README.*`），逐语言后缀与 `regex_backend.py` 实际注册键**逐项一致、无一处不符**；但有 4 处表述与实现不符，见 §二 G3 |
| W5 门禁 | ✅ 通过 | 主代理复跑四项全绿，数字与 §八 一致（见文首门禁块） |

## 二、查漏补缺（G1–G8，均为主代理实测复核）

**G1 [WARNING] `yate/editor_syntax/ts_backend/queries/markdown.scm:17` 的 `@builtin` 未登记在 `DEFAULT_CAPTURE_MAP`，静默失效**
问题：`(fenced_code_block (info_string) @builtin)` 使用的捕获名 `builtin` 不在 `languages.py:123-149` 的映射表内（实测 `'builtin' in DEFAULT_CAPTURE_MAP == False`，表中只有 `function.builtin` / `variable.builtin`）。`ts_backend/backend.py::_highlight` 对 `kind is None` 的捕获 `continue` 丢弃 → 围栏代码块的语言标签（` ```py `）永不着色，且违反方案 W1 明令"捕获名仅用 `DEFAULT_CAPTURE_MAP` 已有集合"。现有测试无法发现：`tests/test_ts_backend.py:295-298` 的 markdown 用例不触碰 `info_string`，`test_capture_map_targets_are_valid_token_kinds`（`:606-608`）只校验映射的**值** ⊆ `SYNTAX_KINDS`，不校验 scm 里的**键**存在。
修复：`DEFAULT_CAPTURE_MAP` 补 `"builtin": "builtin"`（`SYNTAX_KINDS` 确有 `builtin`，`tokens.py:37`），或把捕获名改为已登记的 `function.builtin`（语义亦更准）。

**G2 [SUGGESTION] `DEFAULT_CAPTURE_MAP` 新增的 `heading` / `emphasis` 是死条目**
问题：`git grep "@heading|@emphasis" queries/` 零命中；`markdown.scm:8-13` 的标题标记用 `@keyword`，与 regex 后端 `regex_backend.py:975` 发 `heading` kind 的行为不一致。两个键的**值**合法（`tokens.py:41`/`43`），故现有测试照样通过。
修复：让 `markdown.scm` 标题改用 `@heading` 并同步 `tests/test_ts_backend.py:297` 断言；或确认 ts 侧不需要后从映射表删除，避免"看起来支持、实际无效"的契约。

**G3 [WARNING] 文档承诺了引擎做不到的事（4 处）**
- `yate/docs/extensions.en.md:363` / `.zh.md:333` 称 batch 模板支持 `%VAR%` 变量。实测 `_SIGIL_RE = \$\{?[A-Za-z_][A-Za-z0-9_]*\}?`（`regex_backend.py:712`）只认 `$VAR` 形式，且 `batch_syntax.py.example:33-38` 也没有任何字段能做到；方案 §七 偏离清单未登记此项被丢弃。
- `yate/resources/manual.en.md:721` / `.zh.md:670` 仍写"两个扩展示例"，实测 `yate/extensions/*.py.example` 已是 **7 个**（`batch` / `diff` / `example_ext` / `fsharp` / `git` / `ini` / `yatesh`）。
- `README.md:32` 的 "upgrades 25 built-in languages (**everything above** plus Python/Shell)"：括号枚举含 **Perl**，而 Perl 无语法包（`BUILTIN_PACKS` 无 perl 条目，方案 §三.1 已登记该偏离），与 `manual.en.md:1311-1314` / `.zh.md:1185-1186` 的口径"除 JSONC、INI 和 Perl 外"自相矛盾；"everything above plus Python/Shell" 本身也自相矛盾（Python 就在 above 里）。
- `yate/extensions/git_syntax.py.example:11-12` 称 "`.gitignore` files have no leading basename -- their suffix is `.gitignore` itself, which becomes the filetype key `gitignore`"。实测 `Path('.gitignore').suffix == ''`（前导点文件名无后缀），`Document.filetype` 落到 `plaintext`，`lang_for` 返回 `None` → 该模板承诺的"复制后 `.gitignore` 自动高亮"不成立（需手工 `:set filetype=gitignore`），且方案 §七 未登记此偏离。

**G4 [WARNING] 缺两道静态守护，正是 G1/G3 类问题零防线的根因**
- 无"scm 捕获名必须已登记 `DEFAULT_CAPTURE_MAP`"的测试：`tests/test_ts_backend.py:329-332` 的 23 条样例仅在对应 grammar pack 已安装时执行，纯 regex 安装配置下全部 skip，此时 `test_builtin_packs_ship_a_query_file`（只查文件存在）也发现不了未登记捕获名。建议加一条不依赖任何 grammar 的静态测试：AST/正则扫 `queries/*.scm`，断言每个非注释行里的 `@name` 都在 `DEFAULT_CAPTURE_MAP` 中。
- `BUILTIN_PACKS`（`languages.py:80-106`）、`pyproject.toml` 的 `ts` + `dev` 两份 extras、`pack/_common.py` 的 `_TS_PACKAGES` 是三份逐行重复的清单，仅靠 `pyproject.toml:28` 一句散文 "keep in sync" 维系。本次人工核对三者完全一致（24 个语法包 = 25 个语言去重 `tree_sitter_xml`；模块名与沙箱 `site-packages` 逐一吻合），但建议按 `test_builtin_packs_ship_a_query_file` 的思路加一致性测试固化。

**G5 [WARNING] `scss` / `less` 会被路由到 CSS 的 tree-sitter grammar**
问题：`regex_backend.py:452-458` 把 `css` / `scss` / `less` 三个键指向同一 spec（`spec.name == "css"`），而 ts `resolve()` 正是用 `spec.name` 查 `BUILTIN_PACKS`（`languages.py:92` 无 scss/less 条目）→ 装了 `[ts]` 的用户打开 `.scss` 会用 CSS grammar 解析 `$var` / `@mixin` / `//` 注释，产出 ERROR 节点与错位着色。
修复：或在共享层设"仅 regex"名单（`scss` / `less`），或为两者单独注册 spec 使 `name` 分别为 `scss` / `less`。

**G6 [SUGGESTION] `xml` / `xaml` 的 regex LangSpec 无任何词表**
问题：`regex_backend.py:517-524` 两条 spec 只有 `block_comment`，`<root attr="1">x</root>` 里只有注释与属性值两类 token，XAML 常用元素（`Grid` / `TextBlock` / …）一个都不认，与方案 §一.2 "无 `[ts]` 依赖时仍有着色"的意图有落差。

**G7 [SUGGESTION] `test_sql_keywords_are_case_insensitive` 名不副实**
问题：`tests/test_highlight.py:358-365` 三行断言全是小写 `select` / `from` / `where`；而被测实现 `regex_backend.py:629-632` 的大小写展开（`{w.upper() for w in _SQL_KEYWORDS}`）正是本批唯一有技巧的部分。删掉该推导，用例依然全绿。

**G8 [SUGGESTION] 方案文档证据行号失效**
问题：`../documents/syntax-langs-plan.md:45` 用 `tests/test_ts_backend.py:383-386` 标注 `test_builtin_packs_ship_a_query_file`，该测试实际在 `:611-614`（383-386 现为 blocked-version 用例）。方案是本次唯一规范来源，证据指针应随手改位置同步修正。

## 三、六维度评审发现

### 3.1 正确性 / 可维护性（regex 后端，`regex_backend.py`）

**H1 [WARNING] `regex_backend.py:537-540` — perl 的 `sub` 未接 `func_def_words`**
问题：`sub foo {` 中 `sub` 是 keyword，但 `foo` 后是空格 + `{`，不满足 `_classify_ident` 的 `after.startswith("(")` 判定 → perl 函数名不着色。同期 lua（`:501`）、php（`:566`）、ruby（`:593`）、zig（`:658`）、csharp（`:390`）都显式接线，perl 单独遗漏。
修复：`_spec("perl", ..., func_def_words=frozenset({"sub"}))`。

**H2 [WARNING] `regex_backend.py:712-713` — `@` 在所有 spec 里都被当 decorator，perl / ruby / powershell 的 sigil 失真**
问题：`_DECORATOR_RE = @[A-Za-z_][\w.]*` 无条件进入 master alternation，`_SIGIL_RE` 只覆盖 `$`，故 perl `@array`、ruby `@ivar`、powershell `@splat` 全被染成 decorator。这是词表后端的固有取舍，但新 spec 无一个能关掉它。
修复：给 `LangSpec` 增加开关（如 `at_sigil: bool`），perl 开启后 `@name` 发 `property`；或至少在 spec 旁注释登记该限制。

**H3 [WARNING] `regex_backend.py:512-515` — make 的 `sigils=True` 基本不生效，`-include` 是永远匹配不到的死项**
问题：`_SIGIL_RE` 只认 `$name` / `${name}`，而 Makefile 实际用 `$(VAR)` / `$@` / `$<`（`(` 不满足 `[A-Za-z_]`）→ 变量全灰，正是 `sigils=True` 想解决的场景；`-include` 以 `-` 开头，而 `_IDENT_RE = [A-Za-z_]\w*` 不含 `-`，永不可匹配。
修复：删掉 `-include`；若要覆盖 `$(VAR)`，给 `LangSpec` 加 `paren_vars` 开关并在 `_code_line_pattern` 追加 `\$\([^)\n]*\)`。

**H4 [WARNING] `ts_backend/languages.py:209-213` — 加载失败吞掉全部异常细节**
问题：宽 `except` 只发一条通用 warning，不带异常对象。而"scm 节点名与实际 grammar node-name 不符 → Query 构造失败降级 regex"是方案 §六 的头号风险，排查该风险唯一线索就是被吞掉的 `QueryError` 文本。
修复：保留 warning，另补 `log.debug("tree-sitter load error for %s: %s", name, exc)`（惰性 `%` 占位，符合 §4.6）。

**H5 [WARNING] 同节点被两条 pattern 以相同 span 捕获，胜负取决于 `captures` 字典迭代序**
问题：`backend.py` 声明"最短 span 胜出"，但同一节点被宽窄两条 pattern 同时捕获时排序键完全相同，`sorted` 稳定 → 结果取决于 `dict(cursor.captures(node))` 的键插入顺序（py-tree-sitter 无跨版本契约）。本 diff 有 8 处 `@property` 兜底与窄捕获重叠（`c.scm:50-51`、`cpp.scm:42/44-45`、`go.scm:40-41`、`rust.scm:46-47`、`javascript.scm:40-41`、`typescript.scm:50-51`、`json.scm:6`）。`tests/test_ts_backend.py:228` 断言 `("property", '"k"')` 恰好依赖"`property` 先入列"这一未文档化细节。
修复：去掉兜底里与窄捕获重叠的面（非调用的成员访问才用 `@property`），并在 `backend.py` docstring 写实 tie-break 规则。

**H6 [SUGGESTION] `xml.scm` 与 `xaml.scm` 逐字节重复且无同步约定**
问题：`_load_builtin` 按 `QUERIES_DIR / f"{name}.scm"` 取文件（`languages.py:199`），两份查询必须同内容；当前无任何机制保证同步，且 `xaml.scm:1-3` 丢失了其余 22 个 scm 都有的"未映射捕获继承默认前景色"说明行。
修复：`xaml.scm` 头注释加 `NOTE: body is intentionally identical to xml.scm -- keep the two in sync.`

**H7 [SUGGESTION] 其它 scm 缺口**
- `sql.scm` 无 `@number`（实测 `grep @number sql.scm` 零命中）：tree-sitter-sql 无 `number_literal` 节点，`literal` 同时覆盖字符串与数值 → 数值字面量被涂成字符串色；`tests/test_ts_backend.py:246-252` 不覆盖数值故未暴露。
- `php.scm` 只捕获 `(string)`，带插值的双引号串建模为独立的 `encapsed_string` 节点 → 整体不着色（plan §八 的探针校准清单未记录此项，属遗漏而非取舍）。
- `html.scm:17` 是 `html.scm:14` 的真子集，产生完全相同的重复区间（`claimed` 掩码会吸收，无功能影响）。
- `yaml.scm:21` 只处理无引号 plain scalar 作 key，`"key": v` 落到 `@string`，与无引号 key 视觉不一致。

**H8 [SUGGESTION] 示例模板的文档与实现偏差**
- `fsharp_syntax.py.example:10-11` 称缺依赖时 "falls back to plain text"：实际 `load_language_from_grammar` 在缺 `tree_sitter` 时 `raise RuntimeError`（`languages.py:274-279`）、缺语法包时 `raise ValueError`（`:285-288`），冒泡到扩展加载器被记为 `record.error` → **扩展加载失败、什么都没注册**，而非纯文本回退；`:20-22` 的 "stops matching" 同理——节点名非法会让 `ts.Query` 在注册期直接抛错（`languages.py:244`）。
- `fsharp_syntax.py.example:49-51` 的 `_CAPTURE_MAP = {"identifier": "function"}` 是死配置：查询里没有任何 `@identifier` 捕获，`DEFAULT_CAPTURE_MAP` 也不含 `identifier`；一旦有人加 `@identifier`，**所有**标识符都会变函数色。建议删除或改为注释说明"演示新增映射的方式"。
- `batch_syntax.py.example:10-11` 称引擎处理 "labels"：`_tokenize_code_line` 无任何 label / goto 处理。
- `diff_syntax.py.example:18-22` 关键词表含死项 `"GIT"`（git 输出小写）与大小写重复的 `"Binary"` / `"binary"`（匹配大小写敏感，实际只命中前者）。
- `extensions.*.md` §4.7 与 `services/extensions.py:206-209` 的"grammar 加载失败仍保留最小 regex 回退"是错误承诺：`register_language(LangSpec(name=key), *extensions)` 位于 `load_language` **成功之后**（`languages.py:244-255`），三类真实失败（缺 `tree_sitter` / 缺包 / query 非法）都发生在它之前，此时扩展键根本没注册。
- 5 个新模板完全不在任何质量门禁内：`pyproject.toml` 的 `include` 不含 `.py.example`，pyright 不检查；`tests/test_extensions.py` 无任何 example 相关用例。对比主题模板有 exec 测试（`tests/test_theme_palettes.py:255-261`）。

### 3.2 一致性与可观测性（跨切面）

**H9 [SUGGESTION] `:set filetype=`（无参）的候选提示会被截断**
问题：候选集从 41 键 + 14 名涨到 62 键 + 28 名（去重约 77 项），`commands.py:274` 与 `editor.py:823` 都是全量 `', '.join(...)`，`prompt_bar.write` 按宽度截断 → 后半段完全看不到。`diagnostics.py:329-332` 已有"显示前 12 + `(N total)`"的现成写法。
修复：抽一个共用的截断助手，两处复用。

**H10 [SUGGESTION] 词表死项与既有约定偏差**
- `_PERL_KEYWORDS` 有重复字面量：`local` 与 `sub` 各出现在 `:528` 与 `:534`（frozenset 静默去重，无功能影响但掩盖"被追加过两次"）。
- perl / ruby 把一批内置函数（`print` / `open` / `keys` / `require` / `puts` / `raise` …）放进 `keywords`，kind 变成 `keyword` 而非 `builtin`，与 `_PY_BUILTINS` / `_GO_BUILTINS` 的既有分类约定不一致（ruby 的 `each` 根本不是关键字）。
- 永远走不到的条目（keywords 判定先于 types）：`_LUA_TYPES` 的 `function`（`:492`）、`_PS_TYPES` 的 `switch`（`:470`）、`_PHP_TYPES` 的 `static` / `callable`（`:558-559`）。
- `_SQL_KEYWORDS | {w.upper() …}`（`:629-632`）是本文件全部具名常量之后唯一的匿名集合推导，读者无法看出最终词表规模；建议提为 `_SQL_KEYWORDS_ALL` 等具名常量。
- CSS 连字符属性被拆两半：`_IDENT_RE` 不含 `-`，`font-size: 12px` 里 `font` 命中 builtins、`-` 变 operator、`size` 无着落（`background-color` 恰好两段都在词表里纯属偶然）；`scss` / `less` 同样受影响。
- `make` 只注册 `mak` / `mk`、`ruby` 只注册 `rb`，但 `register_language` 会 `setdefault` 把 `spec.name` 也写进 `_NAME_TO_KEY`（`:245`），故 `:set filetype=make` / `=ruby` 与补全候选**仍可用**（已核实 `resolve_filetype` 走名字回落）；真正缺的是 `.makefile` 后缀（`workspace.py:38` 已把 `.makefile` 列为可编辑文本）。
- php 缺 `#` 行注释、powershell 缺 `<# #>` 块注释（`LangSpec` 只有一个 `line_comment` 字段，无从表达）。
- `:set filetype=` 之外的后缀覆盖不全（低优先）：php `.phtml` / `.inc`、perl `.t`、ruby `.rake` / `.gemspec`、powershell `.psrc`。

## 四、门禁复跑实测（主代理亲自跑，worktree 沙箱）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors, 0 warnings, 0 informations**，EXIT=0 |
| pytest 全量 | `.venv\Scripts\python.exe -m pytest tests/` | **1718 passed, 7 skipped in 238.15s**，EXIT=0 |
| 架构测试 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py` | **22 passed**，EXIT=0 |
| 覆盖率 | `.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75` | **91.29%**（≥75），EXIT=0 |

> 踩坑记录：`pyproject.toml:111` 的 `addopts = "-q"` 已含 `-q`，命令再叠 `-q` 会变成 `-qq`，pytest 摘要行被吞（只看到进度点）——复核门禁数字时用默认 addopts 或 `-o addopts=` 读取摘要。

## 五、Strengths

1. **交付范围与方案高度对齐**：W1 的"4 处填表"（`BUILTIN_PACKS` + `queries/*.scm` + extras + `_TS_PACKAGES`）一处不漏，25 个映射与 25 个 scm 双向闭合并被测试固化；`csharp_highlight.py` 删除后全仓零残留引用（连 `pack/_common.py` 的 extensions `Tree` 也无需改动）。
2. **`BUILTIN_ENTRY` 映射经实证正确**：多语言包的 C 入口不是 `language()`（typescript → `language_typescript`、xml/xaml → `language_xml`、php → `language_php`），这是纯填表模式唯一需要开口子的地方，处理得干净且在 plan §八 与代码注释双向可追溯。
3. **探针驱动的校准诚实**：plan §八 逐条记录了"c/cpp 的 `nullptr` 是匿名 token"、"rust 的 `mut` 走 `(mutable_specifier)`"、"markdown 是块级语法"等 22 个 scm 的实测差异，避免后续 grammar 升级时的误判成本。
4. **降级链完整且不重复付费**：`_FAILED` 记忆失败（避免每次击键重试）、`_DEGRADED_WARNED` 每语言只警告一次且成功后重新武装、`_BLOCKED_TS` 在 0.26 损坏版本上彻底禁用；regex 回退在 13 条新 `LangSpec` 加持下确实兜得住。
5. **词表质量高于既有基线**：`_CS_KEYWORDS` 收全 C# 上下文关键字（LINQ、async/await、primary ctor 的 `record`/`init`/`required`）、`_ZIG_KEYWORDS` 连 `errdefer`/`orelse`/`linksection`/`anyframe` 都没漏；21 个新注册键与 `Document.filetype` 推导完全一致（无 `CS` / `cs.py` 这类推不出来的键），且**未覆盖任何既有注册**。
6. **打包三方严格 1:1**：extras / `_TS_PACKAGES` 的模块名与沙箱 `site-packages` 实测逐一吻合，版本下界统一取实测版本的 `major.minor`，`<0.26` 上界及其理由注释保留。
7. **风格零偏差**：新代码 4 空格、行宽 ≤100、`from __future__ import annotations` 在位、无 `Any` / `type: ignore` / 裸 `except`；新增 22 词表全部带类型注解，分节注释与既有风格一致。
