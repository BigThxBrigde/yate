# translate-cmd 工具计划：用 codebuddy-code 实现 `--translate-cmd`

> 需求：用 `codebuddy-code` CLI 实现一个 `tools.translate` 模块作为 wiki 的
> `--translate-cmd`，接受"输入文档名 / 输出文档名"，免费模型用 `Hy4 preview` / `Hy3`。

## 一、实测事实（2026-09-30）

| 事实 | 证据 |
|---|---|
| 本机已装 CLI：`codebuddy-code`（别名 `cbc`），`@tencent-ai/codebuddy-code@2.154.0`，全局安装并已加入 PATH | 实测 |
| 非交互模式：`-p/--print`（"Print response and exit (useful for pipes)"），`--output-format text` | `codebuddy-code --help` 实测 |
| `--model` 支持项含 `hy4-preview-f`、`hy3`、`hy3-x`、`deepseek-v4.1-flash`、`glm-*`、`kimi-*` 等；`--fallback-model` 可过载兜底 | help 实测 |
| 无工具调用时 stdout **纯净**：`codebuddy-code -p "Reply with exactly: PONG" --model hy4-preview-f --output-format text --tools "" --max-turns 1 --no-session-persistence` → stdout 仅 `PONG`，exit 0 | 实测 |
| 启用 `Read` 工具时**每个工具调用占用一个 turn**：`--max-turns 2` 报 `Max turns (2) exceeded`；需 `--max-turns >= 10` | 实测 |
| 非交互下 `Read` 需权限放行：默认报 "The Read tool was denied because permission prompts can't be shown in this non-interactive session"，提示用 `-y` 或 `--permission-mode bypassPermissions` | 实测 |
| `--permission-mode bypassPermissions` + `--tools "Read"` 探针：17.6s 输出纯净英文 Markdown（结构保留、代码块未译），exit 0 | 已实测验证 |

## 二、目标与非目标

**目标**

1. 新增 `tools/translate`：`python -m tools.translate [IN] [OUT]`，把中文 Markdown 译为英文并落盘；
   无位置参数时读 stdin、写 stdout（兼容 wiki 现有 `--translate-cmd` 协议，**wiki.py 无需改动**）。
2. 模型可配：默认 `hy4-preview-f`，`--model` 可切 `hy3` / `hy3-x`，`--fallback-model` 过载兜底。
3. 输出校验：非空、无外层代码围栏、结构与源文档基本对齐；失败退出码非 0 并报 stderr。
4. 离线可测：测试全部 monkeypatch 掉子进程，不联网。

**非目标**

- 不内置任何 LLM SDK / API Key（全部走本机已登录的 CLI）；
- 不改 `tools/pack/wiki.py` 的钩子协议；
- 不做批量并发调度（wiki 本身是逐页串行调用）。

## 三、选型与否决理由

| 方案 | 结论 | 理由 |
|---|---|---|
| A. 正文直接塞进 `-p` 的 prompt | **否**（小文档备选） | Windows 命令行 argv 上限约 32K 字符；`.trae/documents` 单篇最大 ~47 KB，超限 |
| B. 让代理自己读 IN、写 OUT（给 `Read`+`Write`） | 否 | 需要写权限，且结果要从文件二次读取；权限面更大 |
| C. **Python 负责全部 I/O，代理只 `Read` + 输出**（推荐） | **采用** | 落盘由我们控制，stdout 即译文；配合 `--tools "Read"` 把能力面压到最小 |
| D. `--serve` / `--acp` 长连接 | 否 | 需起服务、管生命周期，复杂度远高于逐页调用 |
| E. 用 `--output-format json` 解析结构化结果 | 否 | text 模式 stdout 已纯净（实测），json 增加解析负担 |

## 四、接口设计

```
python -m tools.translate                      # stdin -> stdout（供 --translate-cmd 使用）
python -m tools.translate IN.md OUT.md         # 文件 -> 文件（同时把译文打印到 stdout）
python -m tools.translate IN.md OUT.md --model hy3 --max-turns 10 --timeout 600
python -m tools.translate --dry-run IN.md OUT.md   # 只打印将要执行的命令与 prompt，不调用模型
```

接线示例（wiki 侧零改动）：

```
.venv\Scripts\python -m tools.pack wiki ^
  --translate-cmd ".venv\Scripts\python -m tools.translate --model hy4-preview-f"
```

内部流程：解析 IN（参数缺失则落临时文件）→ 组装 prompt（"读 IN，译为英文，只输出 Markdown"）
→ 调 `codebuddy-code -p <prompt> --model M --output-format text --tools "Read"
--permission-mode bypassPermissions --max-turns N --no-session-persistence`
→ 校验 stdout（非空 / 去围栏 / 结构对齐）→ 写 OUT → 打印译文。

模块结构（`tools/translate/`）：`__init__.py`、`__main__.py`、`cli.py`、`runner.py`；
测试 `tests/test_tools_translate.py`。

## 五、分步实施

1. **前置验证**（必做）：跑通 `--permission-mode bypassPermissions` + `--tools "Read"` 的探针，确认 stdout 纯净；
   若不纯净则回退到方案 A（分批把正文直接放入 prompt，仅用于小文档）或改用 `--output-format json` 取字段。
2. **实现 runner**：命令拼装、子进程调用、超时、退出码与 stderr 透传、输出清洗（去 ``` 围栏、去首尾空行）。
3. **实现 cli + `__main__`**：两种模式（stdin/文件）、`--model` / `--max-turns` / `--timeout` / `--fallback-model` / `--dry-run`。
4. **写测试**（monkeypatch 子进程）：命令序列、prompt 含路径、stdout 清洗、空输出失败、超时失败、文件模式落盘。
5. **真机冒烟**：对 1 篇小文档跑一次全流程，确认 wiki `--check` 侧可被采纳（manifest 记录新 digest）。

验收命令：

```
.venv\Scripts\python -m pytest tests/test_tools_translate.py -q
.venv\Scripts\python -m pyright tools/ tests/ yate/
.venv\Scripts\python -m pytest tests -q
```

## 六、`--translate-cmd` 扩展：翻译范围参数（缺省增量，`--translate-all` 全量）

> 需求演进：第一版设计为 `--translate-needed`（缺省全量、开关限增量）；
> 2026-09-30 用户决策反转为**缺省增量（仅译 stale+missing）、显式 `--translate-all`
> 才全量**，并更名。本节按最终定案描述。

### 6.1 参数命名（定案）

- **缺省行为**：增量——只翻译状态为 stale 或 missing 的条目，fresh 页保持不动；
- **`--translate-all`**（布尔开关，`action="store_true"`）：全量——对包括 fresh 在内的
  所有非双语直拷条目送翻，覆盖现有英文页。

命名理由：全量是破坏性的少用操作，应显式声明，`--translate-all` 直白表达"全部重译"；
增量是日常安全路径，无需开关（`--force` 因此降级为兼容性 no-op）。
否决：`--translate-needed`（第一版名称，随语义反转废弃——"needed" 现在是缺省，无需开关）；
`--if-required`（语义模糊）；`--only-missing`（漏掉 stale）；`--refresh`（未表达"全量重译"）。

### 6.2 语义与默认行为

| 调用形态 | 行为 |
|---|---|
| `wiki --translate-cmd CMD`（**缺省**） | **增量**：只对状态为 stale 或 missing 的条目调用 CMD；fresh/外部维护页保持不动 |
| `wiki --translate-cmd CMD --translate-all` | **全量**：对所有非双语直拷的 zh 条目调用 CMD——包括 fresh 页，**会覆盖现有 en 译文**（慎用） |

> 缺省增量是安全路径；`--translate-all` 的覆盖行为受 git 保护（可 revert），
> 且 digest 仍只在重翻成功后写入 manifest（见 6.4）。

### 6.3 stale / missing 判定逻辑（与现行实现一致，仅显式化）

对每个非双语直拷条目（`en_source is None`）：

1. 计算 zh 源摘要 `digest = sha256(zh_bytes)`；
2. 读 manifest 记录 `recorded = manifest[zh_target]`（可能缺失）；
3. `has_en = en 文件存在且 size > 0`；
4. 分类（互斥，if/elif 链，天然去重）：
   - **missing**：`not has_en`；
   - **stale**：`has_en and recorded is not None and recorded != digest`；
   - **fresh**：`has_en and (recorded == digest or recorded is None)`——后者是
     "外部维护页首次被采纳"（如代理直译落盘）。fresh 缺省不送翻，
     仅 `--translate-all` 送翻；
   - 边界：双语直拷页（`en_source` 非空）永远跳过翻译，两类参数都不影响。

### 6.4 参数解析与兼容性（与现有 `--translate-cmd` 流程完全兼容）

- `cli.py`：`wiki_cmd.add_argument("--translate-all", action="store_true", help=...)`，
  `_wiki()` 透传 `translate_all=args.translate_all`；
- `wiki.run()`：**仅关键字**参数 `translate_all: bool = False`（缺省增量保证
  既有调用方零改动即兼容）；
- `tools.translate` 模块不受影响：它只翻译被送来的那一份，"送哪些页"始终由 wiki 侧判定；
- 与现有开关的交互矩阵：

| 组合 | 行为 |
|---|---|
| 缺省（无开关） | 仅 stale + missing 送翻；fresh 不动 |
| `--translate-all` | 全部送翻（含 fresh，覆盖现有 en） |
| `--force` | 兼容性 no-op（见 §八 偏离记录）；可与 `--translate-all` 同用 |
| `--check` | 门禁统计口径不变：仍按 missing/stale 全集判定退出码，与本参数正交 |

### 6.5 去重逻辑

1. **分类互斥**：单次 `run()` 内每页只进 `missing` / `stale` / `kept` / `translated`
   四类之一，if/elif 链保证不会一页两算、不会重复送翻；
2. **run 内去重**：翻译成功后立即 `manifest[zh_target] = digest` 并写入 en，同一页
   不会在本次 run 中被二次处理（循环每页仅一次）；
3. **跨 run 去重**：成功页的 digest 已更新，下次 run 判为 fresh，不再送翻；失败页
   状态不变（仍 missing/stale），下次 run 会再次尝试——这是有意的重试语义；
4. **`_assert_unique`**：收集阶段已保证 zh/en 目标名全局唯一，不存在两源映射同页导致的重复翻译。

### 6.6 实施增量与测试

- 实施步骤：cli 注册与透传；测试覆盖：
  1. 缺省：fresh 页不送翻、en 内容不变（hook 调用次数只含 missing/stale）；
  2. `--translate-all`：fresh 页也送翻且 en 被覆盖（断言 hook 调用次数翻倍）；
  3. stale 与 missing 分类互斥（断言两列表无交集、总数守恒）；
  4. `--translate-all --force` 组合不报错、行为与单独 `--translate-all` 一致。
- 验收命令不变（见 §五）。

## 七、风险与回滚

| 风险 | 缓解 |
|---|---|
| `bypassPermissions` 权限面 | 仅授 `Read`；prompt 只读不改；文档外路径不传入 |
| **残留风险（评审 M1，已文档化）**：源文档是不可信内容，代理可读任意路径，恶意文档可注入指令把敏感文件并进"译文"，随 `--push` 外泄到公开远端 | 已在模块 docstring 显式声明"仅对可信文档使用"；如需更强隔离，后续可评估 codebuddy-code 的目录白名单/沙箱参数 |
| `--translate-all` 全量重译覆盖现有译文 | help 显式警示；缺省是安全的增量路径；建议搭配 `--check` 或先对小样本验证；wiki 仓库受 git 保护可 revert |
| 免费模型配额/速率 | `--fallback-model hy3`、调用失败明确报错不静默 |
| 输出被代码围栏包裹或夹带说明文字 | 输出清洗 + 结构校验；异常即失败退出（不写脏译文） |
| 大文档 turn 消耗、单次耗时 ~14–22 s | `--max-turns 10`、单页超时可配；全量 122 页需较长时间，建议分批 |
| 回滚 | 该模块独立，删除目录 + 还原 `--translate-cmd` 用法即可；wiki.py 不受影响 |

## 八、执行记录（收尾回填，2026-09-30 实测）

- 前置探针：`bypassPermissions + --tools "Read"` 对真实文件产出纯净英文 Markdown
  （17.6s，exit 0，代码块未译）——§一"未实测"行已转为已验证。
- 交付：`tools/translate/`（`__init__` / `runner` / `cli` / `__main__`，共 4 文件）+
  `tests/test_tools_translate.py`（12 用例）；wiki 侧 `--translate-needed`（初版，后按用户决策更名 `--translate-all` 并反转缺省语义，见 §十）
  （`wiki.run` 新增仅关键字参数、cli 注册与透传、help 更新）+ `tests/test_pack_wiki.py`
  重构/新增用例。
- 实施中发现并修复：npm 的 `codebuddy-code` shim 是 `.cmd`/`.ps1`，裸
  `subprocess.run` argv 报 `WinError 2`——runner 增加 `shutil.which` 解析
  （PATH/PATHEXT 感知），找不到时转为明确的 `TranslateError`；成员测试全 mock
  子进程未暴露该问题，由真机冒烟暴露。
- 真机冒烟：`python -m tools.translate theme-ownership-plan.zh.md <tmp>/out.md`
  → exit 0，译文纯净落盘。
- 门禁实测：全量 `pytest tests -q` **54 用例全绿**（新增 12 + wiki 侧重构/新增）；
  `pyright yate/ tests/ tools/` 0 errors / 0 warnings。
- 偏离记录：§6.4 矩阵初稿中 `--force` 行与默认行语义矛盾，实施时定案为
  **force = 兼容性 no-op**（stale 在有钩子时一律重译），help 与矩阵已同步；
  `--translate-needed` 缺省"翻译全部"为第一版实现语义（破坏性已在
  help/文档警示；后按用户决策反转，见 §十）。

## 九、评审与修复记录（code-review-expert，2026-09-30）

评审实测：pytest 1487 passed / 7 skipped（覆盖率 90.74% ≥ 75% 门禁）、
pyright 0 诊断。结论：1 blocker + 1 major + 5 minor，已全部处置：

| 级别 | 发现 | 处置 |
|---|---|---|
| B1 阻断 | stdin/stdout 管道编码错配：wiki 钩子按 UTF-8 读写，模块用裸 `sys.stdin/stdout`（中文 Windows 管道继承 GBK）→ 静默乱码/崩溃；单测 mock 管道层未暴露 | `cli._force_utf8_pipes()`：非 tty 流 `reconfigure(encoding="utf-8")`（cast 到 `TextIOWrapper`，容忍 `UnsupportedOperation`）；新增**真实子进程管道集成测试**（`.cmd` stub，CRLF 归一化断言）；stdin 读取加异常兜底（随修 minor 3） |
| M1 major | 源文档不可信时，代理可被注入指令读任意文件并随 `--push` 外泄 | 模块 docstring 显式声明"仅对可信文档使用"；计划 §七风险表补录；更强隔离（目录白名单/沙箱）登记为后续可选项 |
| minor 1 | 默认模式 fresh 页重翻失败时 manifest 已提前写入新 digest，报告口径与 manifest 不一致 | digest 写入移到重翻**成功之后**；新增回归测试（失败后 manifest 保持空） |
| minor 2 | `clean_output` 会误剥"译文整体是一个合法代码块"的首尾围栏 | 仅当首行为无语言标签的裸 ` ``` ` 时才视为包装；新增测试 |
| minor 3 | stdin 非编码异常产生 traceback | 随 B1 一并兜底（`UnicodeDecodeError`/`OSError` → stderr + exit 1） |
| minor 4 | wiki 钩子超时硬编码 900s 与模块 `--timeout` 脱节 | 登记为已知项，不阻断合并（外层先到时错误信息可溯源） |
| minor 5 | `--max-turns` / `--timeout` 无正整数校验 | argparse 后校验，非正数 `parser.error`（exit 2）；新增测试 |
| nice | `--translate-needed` 无钩子时静默忽略；tmp 文件遗留 | 前者：stderr 一行提示已加（随语义调整改为 `--translate-all` 提示）；后者待用户手动删除 `.trae/tmp-missing-en.txt` |

## 十、参数语义调整（2026-09-30 用户决策）

第一版把"翻译全部"作为缺省、`--translate-needed` 作为增量开关。用户决策反转为
**缺省增量（仅 stale+missing）、`--translate-all` 显式全量**，理由：增量是日常
安全路径（不覆盖已有译文），全量是破坏性的少用操作，应显式声明。

落地改动：

- `wiki.run()`：`translate_needed: bool = False` → `translate_all: bool = False`，
  分支条件取反（fresh 仅在 `translate_all` 且有钩子时送翻）；
- `cli.py`：`--translate-needed` 移除，新增 `--translate-all`，help 更新；
- `--force` 维持兼容性 no-op 不变；
- 测试：`test_default_mode_retranslates_every_page` →
  `test_translate_all_mode_retranslates_every_page`（送翻断言移到 translate_all
  分支）、`test_translate_needed_with_force_is_accepted` →
  `test_translate_all_with_force_is_accepted`，其余用例移除 needed 标志；
- 文档：README.zh.md / README.md 示例与参数说明、本计划 §六、风险表同步更新。

门禁复测：全量 `pytest tests -q` 58 用例全绿、`pyright yate/ tests/ tools/`
0 errors / 0 warnings。

修复后门禁：全量 `pytest tests -q` **58 用例全绿**；`pyright yate/ tests/ tools/`
0 errors / 0 warnings；stdin 模式真机复验（真实管道 + 真实模型）exit 0 无乱码。
