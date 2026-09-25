# Python 最低版本升级方案：3.10.x → 3.12.x

> 状态：**方案（未执行）** · 2026-09-25 起草。
> 目标：把 `requires-python` 下限从 3.10 提到 3.12。**核心动机是运行时性能收益**
> （3.11 ~1.25× 均值提速 + 3.12 再 +5%，零代码改动免费获得），次要是落地 3.12 语法现代写法
> （`typing.override`、PEP 604 `X | None`、PEP 695 指引），**全程零行为变更、零回退**。
> 2026-09-25 二批修订：§3.2 规则全面翻转，波次重切为 SP0→D1→SP1→SP2→SP3→SP4（四提交）。
> 唯一规范来源：本文档；执行时按波次推进，每波独立提交。

## 一、现状盘点（2026-09-25 实测证据）

| # | 事实 | 证据 |
|---|---|---|
| F1 | 声明下限 3.10：`requires-python = ">=3.10"`、pyright `pythonVersion = "3.10"` | [pyproject.toml](../../pyproject.toml#L10) L10 / L47 |
| F2 | 开发 venv 实跑 **Python 3.13.2** —— 已高于 3.12，venv 无需重建 | `.venv\Scripts\python.exe -V` |
| F3 | 3.12 移除项全仓零命中：无 `distutils`、`typing.io/re`、`utcnow`、`get_event_loop`、`asyncore`/`asynchat`/`smtpd`/`imp`、`shutil.rmtree(onerror=)`、`randrange` 浮点实参、已移除的 unittest 别名（`assertEquals`/`makeSuite` 等）、无 `sys.version_info` 版本分流 shim | 全仓 grep（yate/tests/tools） |
| F4 | 类型现代写法候选接近零：无 `TypeVar` / `Generic` / `TypeAlias` / `typing.Self` / `StrEnum` 实体用法（命中全为散文或关键字表）；仅 1 处 `IntEnum`（editor_lsp/client.py:152，无需动） | 全仓 grep |
| F5 | **无 `Protocol` 实体类**（唯一命中 `LspProtocolError` 是普通异常类命名）；无 PEP 695 `type` 别名候选 | 全仓 grep |
| F6 | `@override` 适用面 ≈ 55 处基类覆写方法（`on_*` / `compose` / `render` / `watch_*` / `key_*` / 常见 dunder），分布 17 个 yate 文件；tests/tools 另有少量 | grep 计数（yate/） |
| F7 | `asyncio.wait_for` 共 38 处（yate 6 处在 editor_lsp，其余在 tests） | grep |
| F8 | 下限声明散布 7 个非代码文件：pyproject ×2、`.github/workflows/test.yml`（3.11）、`.workflow/test.yml`（Gitee Go，3.11）、README.md / README.zh.md、resources/manual.{en,zh}.md、`.trae/rules/python-coding-style.md` §开头 | grep `3\.10|3\.11` |
| F9 | `asyncio.timeout`（3.11+）/ `itertools.batched`（3.12）/ `tomllib`（3.11）**均无落地场景**：yaterc 解析是手写 parser；`wait_for` 迁移到 `asyncio.timeout` 属语义重构（取消时机与嵌套语义有差异），零收益 | grep + config.py 现状 |
| F10 | pyupgrade `--py312-plus` 可重写目标：旧式泛型 `Dict[`/`List[`/`Tuple[`/`Set[` 与 `TypeAlias` **0 处**；**5 处 `Union[`**（[session.py](../../yate/session.py#L267) L267、[keymaps/base.py](../../yate/keymaps/base.py#L168) L168/L232、[pty_proc.py](../../yate/editor_term/pty_proc.py#L31) L31、[test_key_notation.py](../../tests/test_key_notation.py#L440) L440）+ 308 处 `Optional[`（F11）——PEP 604 codemod 目标面 | 全仓 grep + pyupgrade 能力对照 |
| F11 | `Optional[` 全仓 **308 处 / 53 文件**（yate 37 文件 248 处；tests 9 文件 38 处；tools 7 文件 22 处）；**无引号形态 `Optional["..."]`**，pyupgrade 重写面均匀无特例 | grep 逐文件计数（2026-09-25 实测） |

## 二、风险与防护

| 风险 | 评估 | 防护 |
|---|---|---|
| 3.12 移除/弃用 API 命中存量代码 | **极低**（F3 已证零命中） | 波次一保留 `compileall -W error::SyntaxWarning` 守卫，防无效转义等 SyntaxWarning 潜伏 |
| 依赖在 3.12 的可用性 | 低：`textual>=8.0`（现装 8.2.8）官方支持 3.12+；py-tree-sitter 保持 `<0.26` 上限**不动**（其 0.26 的 Windows wheel 有 python313.dll 堆损坏问题，与本升级无关，见 pyproject 注释） | 决策门 D2：干净 3.12 venv 装轮验证 |
| CI（GitHub 3.11 腿 + Gitee Go 3.11）与新下限矛盾 | **必须处理**（F8） | SP1 把两条流水线升到 3.12；Gitee 公共构建机若无 3.12 镜像则触发 D2 拍板 |
| `reportImplicitOverride` 开启后诊断面失控 | 中（F6 只是模式计数，含 dunder 后真实数可能更高） | 勘察步（SP0）先试开并**精确计数**，超阈值（>150）走 D1 分支 B |
| 既有 flaky pilot 用例干扰门禁判定 | 中（本会话已加固 3 处，全量 5 次 3 败的教训） | 每波门禁 = pyright 0 + pytest **连续两次**全量全绿 + 冒烟全绿；偶发先单独复跑 ×3 再定性 |

**回退策略**：四个波次（声明面 / 规则化 / PEP 604 迁移 / @override）各自独立提交；四波均零行为变更，
任一波 git revert 单提交即完整回退，互不牵连。

## 三、波次与依赖

```mermaid
flowchart TB
    SP0["SP0 勘察与基线（主代理）<br/>基线数字留存 · SyntaxWarning 守卫 ·<br/>reportImplicitOverride 试开计数"]
    SP0 --> D1{"D1 决策门（提前拍板，SP4 消费）<br/>@override 覆写点计数<br/>≤150 → 分支 A 全量装饰<br/>>150 → 分支 B 仅装饰核心链"}
    SP0 --> SP1["SP1 声明面 bump（机械，9 文件）<br/>pyproject ×2 · 双 CI · README ×2 ·<br/>manual ×2 · 编码规则版本号"]
    SP1 --> SP2["SP2 规则 3.12 化（纯文档）<br/>coding-style §3.2 翻转 / §3.5 PEP 695 /<br/>§Self 指引 · pyupgrade 引入"]
    SP2 --> SP3["SP3 PEP 604 存量迁移（pyupgrade codemod，313 处 / 53 文件）<br/>3a yate 叶子+L1（23 文件 155 处）→<br/>3b yate L2–L4（14 文件 93 处）→<br/>3c tests+tools（16 文件 60 处）"]
    SP3 --> SP4["SP4 @override 落地 + 规则固化<br/>typing.override 装饰基类覆写（按 D1 分支）·<br/>reportImplicitOverride = error 入 pyright 配置"]
    SP4 --> GATE["收尾门禁：pyright 0 + pytest ×2 + 冒烟<br/>（每波各自门禁后独立提交）"]
    GATE --> D2{"D2 决策门（可选验证）<br/>干净 3.12 venv 装轮冒烟<br/>Gitee 构建机 3.12 镜像确认"}
    D2 --> DONE["收尾：文档回填 → 提交（推送由用户定）"]
```

### 性能收益评估（升级核心动机，2026-09-25 补充）

数据来源：外部迁移对照建议（转述 CPython 官方基准与 What's New，非本仓实测）。
关键结论：**绝大部分收益是运行时层面的免费提速，不需要任何代码改动**——这正是把
下限 bump（SP1）作为独立首波的价值：波次一落地，性能收益即全额生效。

| 收益点 | 官方数字（转述） | 对 yate 的相关性 |
|---|---|---|
| CPython 3.11 整体提速 | 比 3.10 平均快 10–60%，标准套件约 **1.25×** | **全额受益**：yate 全量代码随解释器升级免费获得 |
| 3.12 整体再优化 | 约 **+5%**（PEP 709 推导式内联、BOLT 优化） | **全额受益**，同上 |
| 列表推导式（PEP 709 内联） | 微基准最高 2×，实际代码约 11% | **高度相关**：yate 的热路径是推导式密集型——`editor_syntax/regex_backend` 逐行高亮扫描、`editor_term/emulator` 渲染循环、`editor_core` 搜索/文档操作 |
| asyncio 性能改进 | 部分基准可达 **75%** | **高度相关**：yate 是重 asyncio 应用（Textual 事件循环、editor_lsp 38 处 `wait_for`、editor_term pty 读写、补全流程），LSP 往返与终端吞吐直接受益 |
| `isinstance`（runtime-checkable Protocol） | 2–20× | **无增量**（F5：本仓无 Protocol 实体类） |
| `tokenize` 模块（PEP 701） | 最高 64% | **无直接增量**（yate 高亮是自研 regex 引擎，不走 tokenize） |

**注意事项（如实记录）**：有测试称 3.12 冷启动略慢于 3.10（`python -c "pass"` 量级 ~25ms，
源于增强的 AST 错误定位等）。对 yate 影响可忽略：交互式 TUI 一次会话以分钟计，25ms 一次性成本
不构成感知差异；打包 exe（tools/pack）的启动感知同样不受影响。

**与"不迁移项"的关系**：`asyncio.wait_for` → `asyncio.timeout` 维持不动——asyncio 的提速
来自解释器/事件循环本身（升级即得），与 API 形态无关；迁移该 API 的唯一收益是写法风格，
语义重构风险依旧为零收益（F7/F9 判定不变）。

**不迁移项（明确记录，防过度工程）**：
- `asyncio.wait_for` → `asyncio.timeout`：38 处，多数被测试直接断言，迁移属语义重构，无收益 → **不动**（F7/F9）。
- `asyncio.gather(..., return_exceptions=True)` → `TaskGroup`（manager.py:668/674/680、client.py:325/330
  关停路径）：TaskGroup 异常时取消兄弟任务并抛 ExceptionGroup，而此处**刻意** return_exceptions
  吞错让任务自行清理（2026-09-25 专项复核）→ 迁移即改行为 → **不动**。
- `asyncio.ensure_future(coro)` → `create_task`（manager.py:358、client.py:361）：3.12 未弃用，
  两者在运行循环内行为等价，仅风格差异、零收益 → **不动**。
- 推导式（PEP 709）：**零迁移项**——内联是解释器行为，升级即自动提速；全 yate 包无
  `for …: .append/extend()` 手工循环可转换形态（multiline grep 实测零命中，模式有效性已验证）。
- `Optional[X]` → `X | None`：**原列为本项，2026-09-25 拍板推翻**——§3.2 规则全面翻转，
  迁移工作独立成 SP3 批次（313 处含 Union），不再是"不迁移项"。
- `from __future__ import annotations`：**保留**（与 PEP 695 兼容，规则 R 不变；本仓无 PEP 695 候选，F5）。
- `tomllib` / `StrEnum` / `itertools.batched`：无候选（F4/F9）→ 零改动；`typing.Self` 存量无候选（F4），
  仅作 §3.2 新代码指引，无迁移动作。

### 工具化策略评估（2026-09-25 二批修订，依据外部迁移对照建议）

外部建议的通用做法是 `pyupgrade --py312-plus` 全仓重写 + 门禁验证。评估结论随 §3.2 规则翻转而演进：

1. **PEP 604 迁移：pyupgrade 由"不采纳"转正为 SP3 指定 codemod**。`Optional[X]`/`Union[X, Y]`
   → `X | Y` 是机械等价重写（313 处，F10/F11），人工逐处改写无增值；迁移后由门禁验证兜底。
2. **仍禁止裸跑**：不带 `--keep-percent-format` 时 pyupgrade 会把 `'%s' % x` 重写为 f-string，
   违反 §4.6 日志惰性求值规则。SP3 统一命令：
   `.venv\Scripts\pyupgrade.exe --py312-plus --keep-percent-format <files...>`。
3. **`@override` 不在语法重写工具能力内**：继承链语义判断（该方法是否真覆写某基类方法）
   无类型信息做不了；`action_*` 分派不得装饰、Textual `on_*` 必须装饰的边界只有类型检查器能划
   → SP4 保持闭环：pyright `reportImplicitOverride` 试开出精确工单（工具定位）→ 主代理逐条落位
   （pyright 只诊断不重写，无现成 codemod）→ 门禁验证（pyright 0 + pytest ×2 + 冒烟）。

pyupgrade 为一次性 codemod，**不进 dev extras**（避免为已完成的一次性迁移固化依赖）；
安装与使用记录随 SP3 执行日志留痕。

## 四、子计划明细

### SP0 — 勘察与基线（主代理，串行前置）

1. **输入**：F1–F11 现状。
2. **步骤**：
   - 留存基线数字：pytest 用例数 / 冒烟场景数与 checks 数 / pyright 0 诊断（对照门禁）。
   - 守卫试跑：`.venv\Scripts\python.exe -W error::SyntaxWarning -m compileall -q yate tools tests`
     与 `pytest tests/ -q -W error::SyntaxWarning`（当前 venv 3.13.2 上先证零告警；该告警在 3.12 升级语境下必须为零）。
   - 试开盘点：临时在 pyright 配置加 `reportImplicitOverride = "error"`，收集全仓诊断清单并计数（只记录，不提交）。
3. **输出**：@override 精确落点清单 + 计数 → 供 D1 拍板；基线数字写进本文件校准记录。
4. **验收**：清单与计数经主代理复核（命令实跑输出）。

### SP1 — 声明面 bump（机械，9 文件）

| 文件 | 改动 |
|---|---|
| [pyproject.toml](../../pyproject.toml) | L10 `>=3.12`；L47 `pythonVersion = "3.12"` |
| [.github/workflows/test.yml](../../.github/workflows/test.yml) | `python-version: '3.11'` → `'3.12'`（若矩阵含多版本，确保最低腿 ≥3.12） |
| [.workflow/test.yml](../../.workflow/test.yml) | Gitee Go `pythonVersion: '3.11'` → `'3.12'`；L48 注释同步（构建机无 3.12 镜像则停手上报 → D2） |
| [README.md](../../README.md) / [README.zh.md](../../README.zh.md) | `Python ≥ 3.10` → `≥ 3.12` |
| [manual.en.md](../../yate/resources/manual.en.md) / [manual.zh.md](../../yate/resources/manual.zh.md) | 同上（打包进 wheel 的用户手册） |
| [.trae/rules/python-coding-style.md](../../.trae/rules/python-coding-style.md) | 仅 §适用范围版本号 `3.10+` → `3.12+`（**已于 2026-09-25 随方案修订先行落盘**；条款级修订全部归 SP2，本波零动作） |

- **不动**：`ts`/`dev`/`build` extras 的版本约束；`tree-sitter<0.26` 上限及其注释；`review.md` 等历史文档中的 `3.10+` 字样（属历史记录）。
- **验收**：`pyright yate/ tests/ tools/` 0 诊断（pythonVersion 提升后类型语义变化即由全量门禁兜住）；`pytest tests/ -q` 连续两次全绿；`python -m tools.smoke_test run --fail-only` exit 0。

### SP2 — 规则 3.12 化与工具引入（纯文档波；规则修订已先行落盘）

1. **python-coding-style.md 修订清单**（已于 2026-09-25 起草阶段落盘，本波执行时复核 diff）：
   - §适用范围 `3.10+` → `3.12+`；§1.3 导入示例、§2.3 docstring 示例去 `Optional` 化；
   - **§3.2 翻转**：可空标注 `X | None`（PEP 604）、联合 `X | Y`（含运行时别名）、
     新增 `typing.Self` 指引；前向引用示例同步；
   - **§3.5 重写**：PEP 695 泛型 / `type` 别名语句为新代码首选；§1.2 类型变量行同步；
   - §五快速清单新增「`X | None` / `X | Y` / `@override`」条目。
2. **工具引入**：pyupgrade（一次性 codemod，临时安装，不进 dev extras）；
   SP3 固定使用 `--py312-plus --keep-percent-format`（理由见工具化策略评估）。
3. **架构规则联动核查**：`architecture-boundaries.md` 无 Optional/版本号关联表述（§七仅交叉引用
   TYPE_CHECKING 条款），**不动**。
4. **验收**：pyright 全仓 0（未动代码）；`pytest tests/ -q` 全绿一次（纯文档波降级为单跑，
   双跑无增量信息）；规则文档内部无自相矛盾（示例与条款一致）。

### SP3 — PEP 604 存量迁移：`Optional[X]`/`Union[X, Y]` → `X | Y`（313 处 / 53 文件）

1. **输入**：F10/F11 实测清单（308 处 `Optional[` + 5 处 `Union[`）；SP2 已翻转的 §3.2 规则。
2. **工具**（先 `pip install pyupgrade`）：
   `.venv\Scripts\pyupgrade.exe --py312-plus --keep-percent-format <files...>`；
   pyupgrade 会顺带清空被掏空的 `typing` 导入（`Optional`/`Union` 不再使用时）。
3. **子批次**（按架构层切分，批间独立可回退；每批后跑批级验证，波次收尾跑标准门禁）：
   - **3a · yate 叶子层 + L1（23 文件 / 155 处）**：editor_core/*（buffer 7、document 6、search 4）、
     editor_lsp/*（client 13、manager 16、protocol 4）、editor_syntax/*（regex_backend 11、
     ts_backend/backend 1、ts_backend/languages 5）、editor_term/*（emulator 7、pty_proc 16）、
     logs.py 24、config.py 7、services/*（extensions 11、workspace 3、trust 3、fonts 1、shell 1）、
     extensions/python_lsp.py 2、session.py 9、registries.py 2、keymaps/*（base 1、registry 1）。
     批级验证：pyright 全仓 0 + `pytest tests/ -q` 一次全绿。
   - **3b · yate L2–L4（14 文件 / 93 处）**：editor_view/*（editor 20、commandline 8、explorer 9、
     terminal 8、panes 7、completion 5、keys 3、theme 3、palette 2、manual 2）、editor.py 15、
     completion.py 4、app.py 6、cli.py 1。批级验证同 3a。
   - **3c · tests + tools（16 文件 / 60 处）**：tests/* 9 文件 38 处、tools/* 7 文件 22 处。
     批级验证同 3a。
4. **边界与风险**：
   - 纯注解改写，零行为变更；`from __future__ import annotations` 全仓在位（规则 §4.1），
     注解全惰性求值；两处运行时类型别名（`Node = Leaf | Split`、`ExitState = int | Literal[...]`）
     在 3.12 运行时与 `Union[...]` 等价（pytest 导入路径即覆盖）。
   - 全仓无引号形态 `Optional["..."]`（F11），重写面均匀无特例。
   - `git diff` 复核：仅允许注解行与 typing 导入行变化；任何方法体/字符串/日志语句变化
     即单独回退该文件复跑。
5. **验收**：pyright 全仓 0；pytest 连续两次全量全绿；冒烟 exit 0；
   `grep -rn "Optional\[\|Union\[" yate/ tests/ tools/` 归零。

### SP4 — `typing.override` 落地 + 规则固化（3.12 核心收益）

1. **输入**：SP0 的精确落点清单（预计 ≈55+，17 文件为核心，tests/tools 另计）。
2. **步骤**（按 D1 分支执行）：
   - **分支 A（≤150 处，默认）**：逐文件给覆写方法加 `from typing import override` + `@override`；
     仅装饰真正覆写基类的方法（Textual 的 `on_*` / `compose` / `render` / `watch_*` / `key_*`、
     dunder 覆写），`action_*` 命名分派方法**不是**基类覆写、不得加；然后把
     `reportImplicitOverride = "error"` 永久写进 `[tool.pyright]`，防回归。
   - **分支 B（>150 处）**：只装饰 L2 组件链（editor_view/*、app.py）+ editor_term/editor_lsp，
     `reportImplicitOverride` 保持关闭并登记为后续项；本分支下 SP4 验收降为「pyright 0 + 抽查 10 处正确性」。
3. **边界**：纯装饰，零运行时行为变更（`typing.override` 是纯标注装饰器）；不改方法体、不动签名。
4. **验收**：pyright 全仓 0 诊断（分支 A 含新规则生效后的 0）；pytest 连续两次全量全绿；冒烟 exit 0；
   `git diff` 复核确认无任何非装饰行改动。

### D1 / D2 — 决策门

| 门 | 触发条件 | 选项 |
|---|---|---|
| D1 | SP0 计数出真实覆写规模 | A：全量装饰 + 规则固化（默认）；B：仅核心链装饰，规则暂缓 |
| D2 | 需要额外置信度时（可选） | ① 干净 3.12 venv：`py -3.12 -m venv .venv312` → `pip install -e .[dev,ts]` → pytest + 冒烟一次；② Gitee 构建机 3.12 镜像不可得时的降级拍板（延后切腿 / 换镜像） |

## 五、执行约定

1. **顺序**：SP0 → D1 → SP1 → SP2 → SP3（3a→3b→3c 串行）→ SP4 → D2 → 文档回填（本文校准记录 +
   `review.md` 无关条目不动）→ 推送由用户定。**每波独立提交**，前一波门禁全绿才开下一波。
2. **门禁**（每波收尾，主代理统一跑）：pyright 全仓 0 诊断；`pytest tests/ -q` 连续两次全绿
   （已知 flaky 单独复跑 ×3 定性）；`python -m tools.smoke_test run --fail-only` exit 0（冒烟不并发）。
   例外：SP2 纯文档波降级为 pytest 单跑；SP3 各子批次批级验证为 pyright 0 + pytest 单跑。
3. **任务书授权**：SP1 机械改文件、SP3 各子批（工具 codemod + 批级验证）可交子代理并行/串行执行，
   任务书按子计划规则写明独占文件清单 + 验证命令 + 报告格式；SP4 `@override` 波动面大，倾向主代理
   以 `reportImplicitOverride` 诊断清单为工单逐文件处理。
4. **提交**（四个 commit，均为零行为变更，可单波 revert）：
   - SP1 `chore(project): raise python floor to 3.12`
   - SP2 `docs(rules): modernize python coding style for 3.12`
   - SP3 `refactor(types): adopt PEP 604 unions across the codebase`
   - SP4 `refactor(types): annotate overrides with typing.override`

## 六、校准记录

- 2026-09-25（起草阶段复核）：按外部迁移对照建议（`pyupgrade --py312-plus` 工具化路线）逐项实测，
  结论落为「工具化策略评估」小节；新增 F10，5 处 `Union[` 收编入计划，
  F3 证据面扩充（`asyncore`/`asynchat`/`smtpd`/`imp`、`rmtree(onerror=)`、`randrange` 浮点均 0 命中）。
- 2026-09-25（二批修订）：**拍板 §3.2 全面切换 `X | None`**（推翻此前"Optional 保留"约定），
  波次重切为 SP0→D1→SP1→SP2→SP3→SP4（四提交）；新增 F11（`Optional[` 308 处/53 文件逐文件实测，
  无引号形态）；工具化策略评估改写——pyupgrade（`--keep-percent-format`）转正为 SP3 指定 codemod，
  `@override` 仍走 pyright 工单闭环；SP2 规则修订与 SP1 版本号行**已先行落盘**
  （python-coding-style.md §适用范围/§1.2/§1.3/§2.3/§3.2/§3.5/§五清单，
  architecture-boundaries.md 经核查无关联不动）；门禁为纯文档波/子批次定义降级例外。
- 2026-09-25（三批补充）：**性能收益确立为升级核心动机**（文档头 + §三新增「性能收益评估」节，
  外部官方基准转述数据逐项映射 yate 相关性：推导式内联 × regex/emulator 热路径、asyncio 提速 ×
  LSP/pty/补全；isinstance/tokenize 两项经核查对 yate 无增量，如实标注）；冷启动 +25ms 风险
  评估为可忽略；`wait_for`→`timeout` 不迁移判定经性能视角复核后维持。
- 2026-09-25（四批专项复核）：按性能视角全量排查推导式与 asyncio 迁移候选，结论全部落入
  「不迁移项」——①推导式 PEP 709 为解释器行为，零迁移（yate 包无 `for…append/extend` 可转换
  循环，multiline grep 零命中且模式有效性已验证）；②`gather(return_exceptions=True)` 关停路径
  迁 TaskGroup 会改行为（manager.py:668/674/680、client.py:325/330）；③`ensure_future` ×2
  （manager.py:358、client.py:361）与 `create_task` 等价零收益。波次结构不变，无新增批次。
- （实施时回填：SP0 计数、基线数字、D1/D2 拍板结果、偏离项）
