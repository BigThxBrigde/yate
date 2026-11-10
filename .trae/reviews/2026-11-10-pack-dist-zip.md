# IKTRDV pack-dist-zip 代码评审记录

评审对象：分支 `feature/feat-pack-dist-zip`（`git diff master...HEAD`，8 笔提交，22 个文件，+2175 / -5）。
评审范围：`tools/pack/zip_dist.py`（新，208 行）、`tests/test_pack_zip.py`（新，183 行，12 用例）、`tests/test_pack_spec.py`（+248 行，8 条静态守卫）、`tools/pack/__init__.py`（+2 行）、`pack/pack.ps1`（+21）、`pack/pack.sh`（+16）、`pack/pack.bat`（+4）、`README.md`/`README.zh.md`、`yate/resources/manual.en.md`/`manual.zh.md`，以及 `.trae/documents/` 下的 issue、主计划、总纲、7 个子计划与进度文档。

框架来源：`.trae/skills/python-code-review/SKILL.md`（6 维度评审 + 三级严重等级 + 输出格式）。Skill 工具无 `python-code-review` 注册项，按角色剧本回退为直接读取该 SKILL 文件执行，未阻塞评审。

## 一、实测命令与退出码

本机 shell 为 cmd.exe，工作目录为仓库根。

| # | 命令 | 退出码 | 关键数字 |
| --- | --- | --- | --- |
| 1 | pyright yate/ tests/ tools/ pack/ | 0 | 0 errors, 0 warnings, 0 informations |
| 2 | pytest tests/ -q -n auto | 0 | 进度至 100%，全程无 FAILED / ERROR 行；本环境未输出汇总行，以退出码为权威 |
| 3 | pytest tests/test_architecture.py -q | 0 | 37 passed |
| 4 | 同上 -n 1 | 0 | 37 passed（并行与单进程一致） |
| 5 | pytest tests/ --cov=yate --cov-branch -n auto | 0 | 3493 passed, 10 skipped；TOTAL 19552 语句 / 1088 miss / 6246 分支 / 568 BrPart = 93%（阈值 75） |
| 6 | 同 #5 以 -n 1 运行（首次） | 1 | FAILED tests/test_app_panes.py::test_close_command_closes_active_pane（pane leaf 2 not found，yate/editor_components/panes.py:139） |
| 7 | pytest tests/ -q -n 1 重跑 | 0 | 无 F / E，100% 完成 |
| 8 | pytest tests/test_app_panes.py -q -n 1 | 0 | 26 passed |
| 9 | tools.smoke_test run --jobs 4 | 0 | 1464/1464 checks (100%)、121/121 scenarios passed、82.06s |
| 10 | tools.changelog check | 0 | released changelog sections are up to date；unreleased lag 7 commit 属存量 |
| 11 | pytest tests/test_pack_zip.py tests/test_pack_spec.py -q | 0 | 44 passed |
| 12 | 同 #11 以 -n 1 运行 | 0 | 44 passed |
| 13 | #11 加 --cov=tools.pack.zip_dist --cov-branch --cov-fail-under=0 | 0 | zip_dist.py 119 语句 / 2 miss / 30 分支 / 2 BrPart = 97%；未覆盖 69、183 至 185 分支、208 |
### 未覆盖行逐条判定（不接受「数字没掉就行」）

- 第 69 行：`_file_mode` 的真实实现（stat.S_IMODE）。POSIX 单测用 monkeypatch 打桩 `_file_mode`，故真实 stat 调用未在本机执行；本评审另以独立探针（真实 chmod 0755 后 posix=True）验证 0755 可正确写入 external_attr。
- 第 183 至 185 行分支：`sums_tmp is not None` 为假的路径（首个 mkstemp 后、第二个 mkstemp 前失败）。写 zip 抛错用例在 `_write_archive` 内即失败，未走到该点，属防御性分支。
- 第 208 行：`__main__` 守卫，由 `-m tools.pack.zip_dist` 集成运行覆盖，pytest 不导入该路径。

三者均为可解释的防御性/入口行，非新增代码缺少测试。本次新增代码覆盖：`zip_dist.py` 97%（分支口径），两个测试文件由 #11 全绿背书。
### 独立性交叉复核（本评审自建探针，不引用他人数字）

1. wave-4 遗留真实产物 `release/yate-0.2.18-windows-x64.zip`（22,934,900 B）：条目 3 个（顶层目录 + SHA256SUMS.txt + yate.exe），无 smoke-out.txt、无 .tmp；testzip() 返回 None；实际 SHA256 与 `release/SHA256SUMS.txt` 中该条目逐字符一致（a87e74ca 至 39d1a44）；external_attr 实测 yate.exe = 0755、SHA256SUMS.txt = 0644、目录 = 0755，create_system 全为 3。
2. POSIX 模式位探针（真实 chmod 0755 后 posix=True）：目录条目 0755、yate 0755、notes.txt 0644，POSIX 可执行位确实保留。
3. 原子性探针（打桩 os.replace 记录调用序列）：先 `.st.xxxx.zip.tmp` 替换为 `st.zip`，再 `.SHA256SUMS.xxxx.tmp` 替换为 `SHA256SUMS.txt`；结束后目录仅剩 SHA256SUMS.txt 与 stage，无临时文件残留。
4. upsert 精确匹配探针：预置 yate-0.2.17-windows-x64.zip / yate-0.2.18-linux-x64.zip / 同名 st.zip 三行，归档后前两行原样保留、同名行被替换、新行追加末尾，共 3 行，无跨平台条目误删。
5. `pack.sh` 第 2 至 22 行逐行打印：`sed -n 2,21p` 的终点 21 覆盖到 pip install -e .[build,ts,lua] 行；新增 `--no-zip`（第 12 行）与 by default（第 13 行）均在区间内，第 22 行起为尾随段落，区间与 usage 自洽。

## 二、问题清单（已过强制自我批判，按严重程度排序）

每条含位置、描述、修复建议、引用规则与自我批判状态。

### [major] M1  文档给出的 ps1 调用形态实测绑定失败

位置：`README.md:315-316`、`README.zh.md:331-332`

描述：本分支新增的两条示例（`.\pack\pack.ps1 --dist release` 与 `-NoZip --dist release`）在 PowerShell 命令模式下无法执行。实测调用 `pack.ps1 --dist release -SkipChangelog` 报「找不到接受实际参数 release 的位置形式参数」（ParameterBindingException）；两种形态均失败，对照 `-Dist release -Help` 正常输出帮助。即文档把已确认不可执行的调用方式教给用户，issue 验收 1 的首条形态（`.\pack\pack.ps1 --dist release` 生成 zip）实际未达成，E2E 改由 bat 与 `-Dist` 覆盖掩盖了这一缺口。

修复建议：双语文档改为 `-Dist release`（保留 `pack\pack.bat --dist release` 与 `./pack/pack.sh --dist release` 两个真实可执行形态）；或给 ps1 的 `Dist` 参数加 Alias 使其真的接受 `--dist` 写法。二者择一，文档与实现必须一致。

引用：issue §四验收 1；`pack-dist-zip-plan.md` §1 本轮范围裁定第 2 条（手册已明文描述 --dist 现状，不改即文档谎言）。

自我批判：确认保留 major，已实测复现，上下文无例外条款可推翻。
### [major] M2  pack.ps1 帮助示例含不可执行形态

位置：`pack/pack.ps1:34-36`

描述：`.EXAMPLE` 段第 34 行为既有 `.\pack\pack.ps1 --dist release`，第 35-36 行是本任务新增的 `-NoZip --dist release` 与注释。实测 `-Dist release -Help` 的「示例 1」段原样打印这些行，其中第 35 行同样不可执行（应写 `-NoZip -Dist release`）。

修复建议：第 34-36 行改为 `.\pack\pack.ps1 -Dist release` / `.\pack\pack.ps1 -NoZip -Dist release`。第 34 行属存量，一并修正即可。

引用：issue §四验收 1（-Help 须可见新开关且可用）。

自我批判：确认保留 major（35-36 为本任务新增，34 行为存量仅作提示，不单独计入）。

### [major] M3  非 ASCII 校验行导致归档步骤硬失败

位置：`tools/pack/zip_dist.py:137`

描述：`_checksum_text` 用 `sums_path.read_text(encoding=ascii)` 读 dist 根校验文件。实测写入一行含中文或 é 的 SHA256SUMS.txt 后调用，抛 UnicodeDecodeError。该异常是 ValueError 子类，被 `main` 的 `except (ZipDistError, OSError, ValueError, zipfile.BadZipFile)` 捕获，因此不会 traceback、不会留半截 zip（故不判 blocker）；但 dist 根校验文件一旦含任何非 ASCII 行（带作者名注释的清单、从别处拷来的 sha256sum 输出等），整个 zip 步骤硬失败，且错误信息只有笼统的 error: zip archive failed，不指向编码根因。

修复建议：改为 `read_text(encoding=utf-8, errors=surrogateescape)`（写回同 errors），或至少把 UnicodeDecodeError 单独转成 ZipDistError 并写明该文件须为 ASCII/UTF-8。若决定不修，须在手册写明该校验文件须为 ASCII。

引用：`python-coding-style.md` §4.5（异常须可读、不得只给笼统信息）；issue §四验收 4。

自我批判：确认保留 major。初版曾考虑 blocker，因 ValueError 兜底使其不崩溃，已下调为 major。
### [minor] m1  pack.bat 未对 powershell 启动期失败给出可辨识信号（由 major 降级）

位置：`pack/pack.bat:48-49`

描述：初版曾判 major（称 bat 吞掉 ps1 失败退出码）。逐条反证后降级：实测 bat 带不可绑定参数运行时得到 0，但该 0 来自本评审 shell 对 `%ERRORLEVEL%` 的取值时机（同一会话里 `powershell -Command { exit 7 }` 也返回 0），并非 bat 的 `exit /b %ERRORLEVEL%` 失效。业务失败（`Stop-WithMessage` 走 exit 1）经 `powershell -File` 传递为进程退出码后可被正确带出。因此仅保留一条成立的点：bat 对 powershell 自身启动期失败（参数绑定错误、执行策略阻止）无可辨识提示，用户在 cmd 里拿到 0 会误判成功。

修复建议（可选，非本任务引入的回归）：在 pack.bat 头注释补一句说明，或在 :run 前加一次 -Help 探针校验命令行。

引用：本角色剧本「宁可漏报存疑项，不留无实证的断言」。

自我批判：由 major 降级为 minor，理由如上（初判源于本评审 shell 的观测伪影）。

### [minor] m2  目录条目时间戳非确定

位置：`tools/pack/zip_dist.py:98,104`

描述：顶层目录与嵌套目录条目用 `time.localtime()[:6]` 取归档时刻，而文件条目取 `st_mtime`。后果是同内容两次构建 zip 字节不同，与 `_stage_files` docstring 自述的 deterministic output（仅指条目顺序确定）在确定性目标上不自洽。对发布产物影响极小（stage 内 mtime 本身每次构建都变）。

修复建议：目录条目改用 stage 目录自身 `st_mtime`，或统一固定 epoch 如 `(1980, 1, 1, 0, 0, 0)`。

自我批判：保留 minor，不升级（无实测功能影响）。
### [minor] m3  校验文件换行风格与 ps1 侧不一致

位置：`tools/pack/zip_dist.py:142,174-178`

描述：新行用 LF 连接、写盘指定 `newline=\n`（LF）；而 `pack.ps1` 的 `Set-Content -Encoding ascii` 与 stage 内 SHA256SUMS.txt 为 CRLF。同一 dist 根下同一语义文件两种行尾，不影响 `sha256sum -c`（GNU coreutils 容忍），但 Windows 记事本与工具链体验不一致。

修复建议：可保持 LF（跨平台工具更友好），并在此处注释说明「刻意统一为 LF，供 sha256sum -c 与 shasum -c 使用」，把差异变成显式契约。

自我批判：保留 minor（初判 minor 正确，无升级理由）。

### [minor] m4  stdlib 白名单守卫的正则可被续行/括号形式绕过

位置：`tests/test_pack_spec.py:926-930`

描述：守卫用 `^import (\w+)` / `^from (\w+)` 提取根模块名。当前实现全是单行导入，实测提取到 12 个根、未漏判；但若未来把导入写成多行括号形式，正则可能漏判。属「守卫未来可绕过」而非当前缺陷。

修复建议：改用同文件已在用的 ast.parse 遍历 ast.Import / ast.ImportFrom 取根名，风格一致且无绕过面。

引用：本角色剧本「守卫是否过松（子串断言易绕过）」核查项。

自我批判：保留 minor；已确认当前实现对现存代码不漏判，不夸大。
### [minor] m5  进度文档对负向演练给出自相矛盾的陈述

位置：`.trae/documents/pack-dist-zip-progress.md:110` 与 `:125-127`

描述：第 110 行写负向演练「尚未执行，收尾前补做」；同一文件第 125 至 127 行写「已把 2,21p 改回 2,19p，守卫变红（RC 1），字节级还原成功」。同文档对同一事实相反陈述，而该文件自述是落盘事实、失败续作唯一依据，矛盾直接损害其可信度。

修复建议：删除或改写第 110 行，指向后面已执行的记录。

引用：`doc-conventions.md` §二.1（评审记录是只读事实文档）。

自我批判：保留 minor。不升 major：不影响产品行为，属文档一致性问题。

### [minor] m6  偏离记录表缺命令与退出码列（降级收窄）

位置：`.trae/documents/pack-dist-zip-plans/overview.md:98-104`

描述：§五 要求偏离须给出实测命令与退出码，§六 表列为轮次 / 偏离 / 实测依据 / 裁定。实测依据列已逐条写了命令（如 `-Dist release -Help` exit 0），实质满足要求，但未单列退出码，逐条核对需二次解读。

修复建议：§六 增退出码列，或把 §五 措辞改为实测依据含命令与退出码。

自我批判：降级收窄，初版判与 §五 不自洽证据不足，实质要求已满足，仅留可读性建议，保留 minor。

### [minor] m7  show_help 的 sed 区间仍是硬编码

位置：`pack/pack.sh:28-31`

描述：`sed -n 2,21p` 为硬编码行号，新增 usage 行须人工同步。已实测第 2 至 22 行确认 21 为正确终点；且 `tests/test_pack_spec.py:785-831` 已把 --no-zip / by default / 所有 usage 行 <= 端点全部断言，并把旧区间 2,19p 列入黑名单，负向演练已验证变红。守卫已充分，sed 无语义锚点故硬编码不可消除。

修复建议：无需改动（当前处置已达最优），仅记录为已知脆弱点。

引用：issue §三「帮助文本的硬编码行区间」。

自我批判：保留 minor（提示性质），不要求本任务处理。
## 三、自我批判：已删除的误报

### [删除] ZipDistError 缺领域字段

初判 minor，称异常无 `__init__`、CLI 靠 `str(exc)` 转述。反证：测试 `pytest.raises(match=...)` 直接依赖消息文本且工作正常；加结构化字段属无收益抽象（`architecture-boundaries.md` §三.6「不为假设性需求加抽象」）。证据不足，删除。

### [删除] _write_archive 每文件重复 stat

初判 minor（stat 调用两次、整文件 read_bytes 入内存）。反证：实测整包 22.9 MB、364 文件，归档在一次性构建里相对 30s 冒烟与 69.3 MB 拷贝可忽略；read_bytes 最大单文件约 22 MB 可接受。按「不做无谓挑剔」与 `python-coding-style.md` §6.1「无实测依据的预优化不做」，删除。

## 四、漏报自查（六维度反向扫）

| 维度 | 复查结论 |
| --- | --- |
| 正确性 | `_stage_files` 以 is_file() 过滤、sorted() 定序；stage 名取首段，由脚本生成为 yate-ver-os-arch 不含分隔符，不成立为缺陷；subdirs 用 range(1, len(parts)) 跳过顶层，实测条目齐全，正确 |
| 边界条件 | 空 stage 报 no files；stage 不存在报 stage directory not found；zip 已存在由 os.replace 覆盖；重跑条目幂等单行。均已实测覆盖，未发现遗漏 |
| 异常处理 | finally 无条件清理两个临时文件（实测目录仅剩 SHA256SUMS.txt 与 stage）；except 列具体类型非裸 except；KeyboardInterrupt / MemoryError 不捕获。M3 为唯一异常语义缺陷 |
| 并发安全 | 无锁。两进程同时对同一 dist 根归档时 mkstemp 名唯一、os.replace 各自原子，但校验文件条目可能丢失一次更新。打包脚本为人工串行调用、issue 未要求并发，不计入缺陷 |
| 性能 | `_digest` 1 MB 分块流式；ZIP_DEFLATED；单次 rglob。无 O(n^2) 或循环内 I/O |
| 类型与测试覆盖 | pyright strict 0 诊断；`zip_dist.py` 97% 分支覆盖，3 处未覆盖已逐条解释；12 个运行时用例 + 8 条静态守卫。未发现遗漏 |
| 分层与编码 | 新模块无 Any / TYPE_CHECKING / 相对导入 / 裸 except；from __future__ 位置正确；两文件实测纯 ASCII；行数 208 / 183 远低于 800 阈值；`tests/test_pack_spec.py` 932 行，`architecture-boundaries.md` §三.7 明示 tests/ 不设限 |
| 文档双语 | README 与手册 en/zh 新增段落结构、示例数量、语义逐项对齐；build,ts,lua 字样保留；全量扫描未发现本机绝对路径。M1 属内容正确性而非双语同步 |
| 提交规范 | 8 笔提交均为 type(scope): subject 全英文，符合 git-commit-message.md |

## 五、偏离评估（独立判断）

| 偏离 | 独立结论 | 理由 |
| --- | --- | --- |
| 1. ps1 直接 --dist release 绑定失败，改由 bat / -Dist 覆盖 | 需修复（对应 M1 / M2） | 作为既有参数解析行为记录历史成因可以接受；但本分支新增的 README、手册与 .EXAMPLE 示例正是该不可执行形态，等于把已确认失败的调用方式教给用户，并直接导致 issue 验收 1 首条未达成。E2E 用 bat 与 -Dist 覆盖掩盖了这一真实缺口。修复成本极低 |
| 2. Linux 真实构建不纳入 | 可接受 | issue 验收 4 明示允许：至少一平台真实构建，另一平台由脚本级用例 + 静态守卫覆盖并记录偏离理由。已做 Windows 三次真实构建、posix=True 单测断言 0755、python -m zipfile -t、sh 静态守卫；本评审另以独立探针复验 POSIX 模式位。文档均如实登记，未声称跑过 Linux 构建 |
| 3. E2E dist 目录用 release 替代 release-e2e | 可接受 | `.gitignore:15` 只忽略 release/，用 release-e2e 会留未跟踪产物；语义等价且实测 git status --short 为空。不掩盖任何验收缺口 |

## 六、总体结论

- blocker：0
- major：3（M1 README / README.zh 示例不可执行、M2 pack/pack.ps1 帮助示例不可执行、M3 zip_dist.py:137 非 ASCII 校验行致归档硬失败）
- minor：7（m1 由 major 降级、m2、m3、m4、m5、m6 降级收窄、m7）
- 已删除误报：2 条（ZipDistError 缺字段、重复 stat 预优化）

门禁层面六项命令实测退出码全 0（pyright 0 诊断、pytest -n auto、架构 37 用例、覆盖率 93% 高于 75、冒烟 1464/1464、changelog check）。第 6 项 -n 1 首轮出现的 `tests/test_app_panes.py::test_close_command_closes_active_pane` 失败，在重跑与单文件复核中均不复现，且 `yate/editor_components/panes.py` 不在本分支 diff 内，判定为存量负载下的时序假设问题；按剧本「后者也要修用例，不得记成偶发」，登记为独立待办，不属本分支缺陷、不计入清单。

合并判断：当前不应合入。M1 / M2 必须先修（文档与实现一致、issue 验收 1 首条形态可执行）；M3 建议同批修，或明确登记为已知限制并在手册写明 dist 根 SHA256SUMS.txt 须为 ASCII。三者修完即达仅 minor 待办状态，可合入。

修复方案：[pack-dist-zip-review-fixes-plan.md](../documents/pack-dist-zip-review-fixes-plan.md)（第一轮评审修复，双向互链）。
