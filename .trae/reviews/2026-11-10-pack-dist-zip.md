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

## 七、第二轮迭代复核

复核对象：`git diff 508c7b2..HEAD`（`4f11dd1d` 修 8 个代码/文档文件、`f5117e1f` 回填 3 份文档），并以 `git diff master...HEAD`（24 文件）作整体回归视角。
框架来源：`.trae/skills/python-code-review/SKILL.md`（6 维度 + 三级严重等级 + 输出格式）。Skill 工具无 `python-code-review` 注册项（返回 not found），按剧本回退为直接读取该 SKILL 文件，未阻塞评审。
本机 shell 为 cmd.exe + powershell -NoProfile，工作目录为 `d:\Programming\yate-pack-dist-zip`。

### 7.1 实测命令与退出码

| # | 命令 | 退出码 | 关键数字 |
| --- | --- | --- | --- |
| 1 | pyright yate/ tests/ tools/ pack/ | 0 | 0 errors, 0 warnings, 0 informations |
| 2 | pytest tests/ -q -n auto | 0 | 输出 52 行、100% 完成；FAILED/ERROR 匹配数 = 0；本环境无汇总行，以退出码为准 |
| 3 | pytest tests/test_architecture.py -q | 0 | 37 个用例点全绿（与第一轮 37 passed 一致） |
| 4 | pytest tests/ --cov=yate --cov-branch -n auto | 0 | 3495 passed, 10 skipped in 204.76s；TOTAL 19552 语句 / 1077 miss / 6246 分支 / 571 BrPart = 93.03%（阈值 75.0 reached） |
| 5 | tools.smoke_test run --jobs 4 | 0 | 1464/1464 checks (100%)、121/121 scenarios passed、88.88s |
| 6 | tools.changelog check | 0 | released changelog sections are up to date；unreleased lag 10 commit（第一轮 7，新增 3 为本轮迭代提交）、missing zh 属存量 |
| 7 | pytest tests/test_pack_zip.py tests/test_pack_spec.py -q | 0 | 46 passed（第一轮 44，+2 为新增用例） |
| 8 | pytest tests/test_pack_zip.py --cov=tools.pack.zip_dist --cov-branch --cov-fail-under=0 | 0 | zip_dist.py 120 语句 / 2 miss / 30 分支 / 2 BrPart = 97%；未覆盖 74、188-190、213 |
| 9 | pytest tests/ -q -n 1（全量单进程复核） | 0 | 100% 完成、FAILED/ERROR 匹配数 = 0 |
| 10 | pytest tests/test_app_panes.py -q -n 1（连续 4 次） | 0,1,0,0 | 4 次里第 2 次失败（见 7.4 N1） |
| 11 | pytest tests/test_app_panes.py::test_close_command_closes_active_pane -q（连续 6 次单独跑） | 全 0 | 6/6 passed |

未覆盖行判定（不接受「数字没掉就行」）：74 为 `_file_mode` 真实 `stat.S_IMODE`（POSIX 用例 monkeypatch 打桩，本轮另以独立探针 posix=True 实跑覆盖）；188-190 为 `sums_tmp is not None` 为假的防御分支；213 为 `__main__` 守卫。与第一轮同类，属可解释的防御性/入口行，非新增代码缺测。

### 7.2 第一轮 major 闭环复核（逐条实测）

**M1 文档 ps1 示例可执行性 —— 已闭环**

- 静态：`README.md:315-316` / `README.zh.md:331-332` 已改为 `.\\pack\\pack.ps1 -Dist release` 与 `-NoZip -Dist release`；bat/sh 示例保持 `--no-zip` / `--dist`（`README.md:317-319`、`README.zh.md:333-335`）；两文件各补 2 行「PowerShell 直接调用用 -Dist，双连字符由包装脚本提供」的说明（`README.md:320-321`、`README.zh.md:336-337`）。
- 残留扫描：`pack.ps1.*--dist` 在 README 双语仅命中 2 处（`README.md:320`、`README.zh.md:336`），均为说明文字注释而非可执行示例；手册双语命中 0 处。满足方案 §6「--dist 仅出现在 bat / sh 的可执行示例与说明文字中」。
- 手册澄清：`manual.en.md:1653-1655` / `manual.zh.md:1476-1477` 各补一句等价澄清，中英逐句对应；既有 `-OneFile -Dist release`（`manual.en.md:1658`、`manual.zh.md:1480`）与 `-OneFile -Dist release -NoZip`（`manual.en.md:1675`、`manual.zh.md:1496`）本就为 -Dist 形态，未被动坏。
- 实测：`& .\\pack\\pack.ps1 -NoZip -Dist release -Help` → exit 0，输出示例段为 `.\\pack\\pack.ps1 -Dist release` / `.\\pack\\pack.ps1 -NoZip -Dist release`。对照：`& .\\pack\\pack.ps1 --dist release -Help` 仍报 ParameterBindingException（找不到接受实际参数 release 的位置形式参数），印证文档纠偏方向正确——`--dist` 在 PowerShell 命令模式确不可绑定，故文档不得给出该形态。

**M2 pack.ps1 帮助示例与 stop-parsing 说明 —— 已闭环**

- `.EXAMPLE`：`pack/pack.ps1:37-38` 已为 `-Dist release` / `-NoZip -Dist release`（第 34 行存量 `.\\pack\\pack.ps1` 与第 41 行 bat 示例未受影响）。
- `.DESCRIPTION`：`pack/pack.ps1:26-27` 新增「PowerShell command mode treats --dist as a stop-parsing token; call this script with -Dist (the .bat wrapper and pack.sh accept --dist / --no-zip)」，措辞与实测一致。
- 静态守卫目标保留：`.PARAMETER NoZip` 段 `pack/pack.ps1:29-31` 仍含 `--no-zip` 拼写；`tests/test_pack_spec.py:726-727` 断言 `.PARAMETER NoZip` 与 `--no-zip` 均在，守卫仍绿（命令 #7 exit 0）。
- 实测：`-Help` 输出「说明 / 参数 / 示例 1」三段完整，`-NoZip` 绑定正常、exit 0。

**M3 非 ASCII 校验行 —— 已闭环**

- 实现：`tools/pack/zip_dist.py:133-152` 的 `_checksum_bytes` 以 `read_bytes().splitlines()` 逐行取原始字节；仅 `line.decode("ascii", errors="replace").split()` 用于末列是否同名的判断（147-149 行），`lines.append(line)` 保留原字节（150 行）；新行 `f"{digest}  {archive_name}".encode("ascii")`（151 行）；返回 `b"\\n".join(lines) + b"\\n"`（152 行）。写盘改为 `sums_tmp.write_bytes(...)`（183 行），无文本层 newline 转换。
- 探针 A（复验第一轮失败场景）：预置 `b"caf\\xe9  other.zip\\r\\nold  a.zip\\n\\n*bin  a.zip\\nnoise-no-hash\\n"`，调 `_checksum_bytes(p, "a.zip", "abc")` → 返回 `b"caf\\xe9  other.zip\\n\\nnoise-no-hash\\nabc  a.zip\\n"`，不抛异常；`b"caf\\xe9  other.zip"` 原样保留；星号前缀同名行 `*bin  a.zip` 被剔除；无哈希的 `noise-no-hash` 行保留；空行保留。
- 探针 B（同名精确替换强度）：ASCII 哈希行与 UTF-8 哈希行（déad 前缀）均被替换为新行且仅 1 行；跨平台条目（...linux-x64.zip）不受影响（沿用既有用例 `test_pack_zip.py:47-58`）。
- 探针 C（确定性/幂等）：同 stage 连续归档两次，digest 稳定、`SHA256SUMS.txt` 恒 1 行且纯 ASCII、无 .tmp 残留、条目 `[st/, st/a.bin]` 正确。
- 新增单测强度：`tests/test_pack_zip.py:61-71` 断言 (a) `b"caf\\xe9  other.zip" in content`（非 ASCII 字节保留）；(b) 同名行集合精确等于 `[f"{digest}  {name}".encode("ascii")]`（精确替换 + 无重复）；(c) `len(content.splitlines()) == 2`（行数正合适）。三条断言独立可失败，强度足够，非「只断言不抛异常」的空壳。

对照方案 §5 风险表「decode(ascii, errors=replace) 仅用于判断、不写回」：实测属实——探针 A/B 返回字节中 `caf\\xe9` 与 UTF-8 字节原样出现，替换判断只影响是否 continue，不参与输出构造。

### 7.3 minor 闭环与待办登记

| 项 | 复核结论 | 证据 |
| --- | --- | --- |
| m2 目录条目固定 epoch | 已闭环 | `zip_dist.py:39-41` 定义 `_ZIP_EPOCH=(1980,1,1,0,0,0)`；`:103`、`:109` 目录条目改用之；`:116` 文件条目仍为 `time.localtime(path.stat().st_mtime)[:6]`；`:60-61` docstring 改为「deterministic entry order」。探针实测：目录条目 (1980,1,1,0,0,0)，文件条目 (2023,11,15,6,13,20) 保真、0o100777、create_system=3、testzip()=None |
| m3 LF 显式契约 | 已闭环 | `zip_dist.py:141-142` docstring 明示「deliberately uses LF line endings for sha256sum -c and shasum -c compatibility」；`write_bytes` 无 newline 转换。探针 A 显示输入 CRLF 被归一为 LF（契约行为，非缺陷） |
| m4 守卫改 AST | 已闭环 | `tests/test_pack_spec.py:926-931` 遍历 `ast.Import` / `ast.ImportFrom`，含 `node.module is not None` 保护。独立复核：对 `zip_dist.py` 提取到 12 个根名（__future__, argparse, collections, hashlib, os, pathlib, stat, sys, tempfile, time, typing, zipfile），与第一轮正则口径的 12 个完全一致 → 无漏判；allowed_roots 白名单与 Compress-Archive / subprocess 禁入断言（`:920-921`）仍在 → 无误伤放宽 |
| m5 progress 矛盾 | 已闭环 | `pack-dist-zip-progress.md:110` 改为「负向演练留待 wave-4 执行（实测结果见下文），本处不重复陈述」；`:125` 有 wave-4 实测记录（2,21p 改回 2,19p 变红 RC 1、字节级还原）。两处方向一致，不再自相矛盾 |
| m6 偏离表退出码列 | 已闭环 | `overview.md:98` 表头新增「退出码」列，6 行逐条填值（N/A（spawn 错误）、N/A（只读调研）、0（三次构建）、绑定失败 / 替代路径 0、0（zipfile -t）、0（三条验收命令 + 探针）），并新增【迭代】R1 一行 |
| m1（bat 启动期失败无提示） | 已登记待办 | `review-fixes-plan.md:149-150`，另案 |
| m7（sh sed 硬编码区间） | 已登记待办 | `review-fixes-plan.md:151-152`，守卫已充分 |
| 存量 flake（test_app_panes） | 已登记，但**性质需更正**，见 7.5 N1 | `review-fixes-plan.md:153-155` |

### 7.4 反向核查：修复是否引入新缺陷

| 核查项 | 结论 | 证据 |
| --- | --- | --- |
| decode(ascii, errors=replace) 仅判断不写回 | 属实 | 探针 A/B 输出含原始 UTF-8 字节；continue 只控制保留/剔除，不参与输出构造 |
| write_bytes 与 os.replace 顺序/清理未变 | 属实 | `zip_dist.py:184-189` 仍为「先 os.replace(zip_tmp, archive)、再 os.replace(sums_tmp, sums_path)」，finally 无条件 unlink(missing_ok=True)；探针 C 实测无 .tmp 残留 |
| _ZIP_EPOCH 是否影响文件条目 mtime 与可执行位 | 未影响 | 探针实测文件条目 mtime 保真、posix 模式位与 create_system=3 均正常，且 testzip()=None |
| AST 守卫误伤/漏判 | 无误伤无误漏 | 提取 12 根名与正则口径一致；白名单未放宽；`node.module is None`（from . import x）被跳过——该类相对导入在 tools/ 本就由 `python-coding-style.md:71` 与架构守卫另行禁止，不构成漏判 |
| 双语文档逐项对齐 | 对齐 | README en/zh 示例行数（5 条）、顺序、注释行数（2 行）与语义一一对应；手册 en/zh 澄清句一一对应；build,ts,lua 字样保留（`tests/test_pack_spec.py:437` 守卫绿，命令 #7 exit 0） |
| 提交规范 | 合规 | `fix(pack): ...` / `docs(review): ...` 两笔均为 type(scope): subject 全英文（`git-commit-message.md:3`） |

### 7.5 第二轮问题清单（已过强制自我批判）

**[minor] N1  存量 flake 定性有误：test_close_command_closes_active_pane 并非「负载下的时序假设」，同文件单进程可复现**

位置：`tests/test_app_panes.py:127-148`（断言 `assert app.is_running` 于 `:146`）；根因在 `yate/editor_components/panes.py:139`（`assert leaf is not None, f"pane leaf {leaf_id} not found"`）与 `yate/editor_components/view.py:177`（`on_focus` → `notify_focus(self.leaf_id)`）。

描述：第一轮 §一 第 6 项与修复方案 §7 均把该失败登记为「-n 1 首轮出现、重跑不复现 → 存量负载下时序假设」。本轮实测推翻该定性：单文件 `pytest tests/test_app_panes.py -q -n 1` 连续 4 次结果为 0,1,0,0（第 2 次失败），失败栈固定为 on_focus 派发到已关闭的 leaf 2 → leaf_by_id 硬断言。同文件、单进程、无并行负载仍复现，说明这是「关闭面板后迟到的 focus 事件命中已销毁 leaf」的竞态，而非负载放大效应。相反，单独跑该用例 6/6 全过，全量 -n 1 与 -n auto 本轮亦 exit 0——即复现依赖同文件内前述用例遗留的焦点状态，属确定性可触发。

为何仍判 minor 而非 major：`panes.py` / `view.py` / `test_app_panes.py` 三者均不在本分支 diff 内（`git diff master...HEAD --name-only` 24 个文件已逐一核对），属存量缺陷，不在本任务范围（`plan-before-execute.md` 的范围原则与修复方案 §1 非目标）；且不影响产品正常使用路径（需 sp + close + 迟到 focus 的特定时序）。但按 `python-coding-style.md` §4.7 与第一轮已确立的「不得记成偶发」原则，定性必须更正为「确定性的焦点竞态」并另案修用例/产品，不能以「重跑不复现」结案。

修复建议（另案，不阻塞本任务合入）：
1. 测试侧最小修复：`test_close_command_closes_active_pane` 在 close 后补一次 `await pilot.pause()` 或改用 wait_until 谓词等到 leaf 2 的 view 真正卸载，再发 cl；
2. 产品侧更稳妥：`panes.py:214-220` 的 notify_focus 对 find_leaf 返回 None（leaf 已销毁）改为静默 return 而非硬断言，把「迟到 focus」变成良性事件；
3. 建议补一条守卫用例：关闭一个 pane 后对该 leaf 的 on_focus 不得抛出。

引用：`python-coding-style.md` §4.7；第一轮 §一 第 6 项（定性更正）；`review-fixes-plan.md` §1 非目标与 §7 待办。

自我批判：**确认保留 minor**。初版曾考虑升 major（可稳定复现的断言崩溃），逐条反证后维持 minor——(a) 三处相关文件均不在本分支 diff，升 major 等于把存量缺陷记到本任务头上，违反「只报告本次范围内有依据的问题」；(b) 不属 [blocker]（非安全/数据丢失/常规使用即崩溃）；(c) 但第一轮「偶发/时序假设」的表述经实测证伪，故必须以 minor 形式落盘更正，避免下一轮继续沿用错误定性。

**[minor] N2  新增 epoch 用例未断言「文件条目 mtime 未被固定」，回归面存在缺口**

位置：`tests/test_pack_zip.py:74-82`

描述：`test_archive_stage_when_directory_entries_are_written_uses_fixed_epoch` 断言两个目录条目 `date_time == (1980,1,1,0,0,0)` 与 `file_info.create_system == 3`，但未断言文件条目的 date_time 仍等于源文件 mtime。若后续误把 `_write_archive:116` 也改成 _ZIP_EPOCH，本用例仍会全绿，而方案 §5 风险表明确把「文件条目仍保真」当作缓解措施依赖。本轮我已用独立探针实测文件条目 mtime 保真（(2023,11,15,6,13,20)），故当前实现正确；缺口仅在测试的回归防护强度。

修复建议：在既有 `with zipfile.ZipFile(...)` 块内补一条断言，比对 `file_info.date_time` 与源文件 st_mtime 的 localtime 六元组（可先 os.utime 固定 mtime 再断言常量）。

引用：`python-coding-style.md` §4.7；方案 §5 风险表「文件条目仍保真」条。

自我批判：**确认保留 minor**。初版考虑不报（当前实现正确、有独立探针背书），但「缓解措施无守卫」属可维护性实在缺口，且修复为一行的低成本增量，保留为 minor 非风格挑剔。

**[minor] N3  `_checksum_bytes` 对末列含全角空格等非 ASCII 字符的同名行不替换（残留风险）**

位置：`tools/pack/zip_dist.py:147-149`

描述：判断走 `decode("ascii", errors="replace")`，故末列若有任一非 ASCII 字节即被替换为 ?，不再等于 archive_name。实测：末尾带全角空格（U+3000）的同名行 `dead  yate-...zip + U+3000` 不会被剔除，归档后校验文件出现两行同名条目。只要 dist 根校验文件曾被以 UTF-8 编入含全角空格的行（人工编辑、从文档粘贴）即可触发，导致 sha256sum -c 出现重复条目并可能校验到旧哈希。

影响评估：触发条件为「同名 zip 行的末列带非 ASCII 字符」，正常由脚本生成的 SHA256SUMS.txt 不会出现；且方案 §5 已登记该风险并给出缓解（stage/zip 名由脚本生成为 ASCII）。故不构成 practical 缺陷，仅记录为已知边界。

修复建议（可选）：判断前先 `line.rstrip()` 去掉行尾 ASCII 空白，或改用 `decode("utf-8", errors="surrogateescape")` 后 split()——两者都能把「尾随全角空格」这类畸形行纳入同名判定。

引用：`python-coding-style.md` §4.6（边界条件）。

自我批判：**降级并保留 minor**。初版曾拟判 major（校验文件出现重复同名行 → 可能校验到旧哈希，属数据一致性问题），逐条反证后降级：(a) 触发需畸形输入（全角空格/非 ASCII 尾随），并非「边界条件缺陷」而是「畸形输入容忍度有限」；(b) 正常脚本生成的校验行为纯 ASCII，实测三次真实构建与全部单测均无此形态；(c) 方案 §5 已显式登记该风险并裁定可接受。降级理由记录于此。

**[minor] N4  偏离表「绑定失败 / 替代路径 0」把非零结果与 0 混填一栏**

位置：`.trae/documents/pack-dist-zip-plans/overview.md:102`

描述：m6 新增的「退出码」列对 wave-4 ps1 --dist 偏离行填「绑定失败 / 替代路径 0」。该行实测依据本身含两件事：`--dist release -Help` 绑定失败（异常）与 `-Dist release -Help`、bat 真实构建 exit 0。把两者写进一格，逐条核对时仍需二次解读，与 m6「增列以便直接核对」的初衷部分回退。

修复建议：拆成两行（--dist 绑定失败记 1（ParameterBindingException）；-Dist / bat 记 0），或该格改为「1（--dist 绑定）/ 0（-Dist 与 bat）」。

引用：`overview.md` §五 对偏离须给命令与退出码的要求；本轮 m6 闭环目标。

自我批判：**确认保留 minor**（不删）。属可读性问题、不影响事实准确性（原文两件事都写全了），但 m6 的目标正是免除二次解读，故作为本轮新增的收窄项记录，非重开 m6。

**[minor] N5  README 代码块内示例注释列对齐被打乱**

位置：`README.md:315-319`、`README.zh.md:331-335`

描述：本轮把 ps1 两行加宽（-Dist 形态更长），但对齐只在部分行做了（`README.md:319`、`README.zh.md:333-335` 仍停在旧列位）。实测 `README.md:315-319` 的注释起始列约为 50/50/49/49/46，视觉上不成列。

修复建议：统一该代码块内注释起始列，或去掉手工对齐（注释前保留单个空格）。

引用：无（纯可读性）。

自我批判：**确认保留 minor**，已核对行号与列位为实测而非印象；不升 major（纯外观）。

**[删除] `_checksum_bytes` 返回末尾多一个空行**

初版拟报：`b"\\n".join(lines) + b"\\n"` 在末行后补换行，若原文件已以空行结尾则产生连续空行。反证：探针 A 输入含空行，输出与预期完全一致（空行属原文件内容，splitlines() 语义正常）；sha256sum -c 与既有用例（len(splitlines())==2/3）均无异议；第一轮同函数同语义已审过且未列为问题。证据不足，删除。

**[删除] `_ZIP_EPOCH` 应为 Final 常量**

初版拟报：模块常量未标 Final。反证：同文件其余常量（_TEMP_NAMES、_EXECUTABLE_NAMES、_CHUNK_SIZE）一致地使用内联注解而非 Final，python-coding-style.md 未要求 Final；pyright strict 零诊断。属风格偏好，按「不做无谓挑剔」删除。

### 7.6 漏报自查（六维度反向扫，第二轮）

| 维度 | 复查结论 |
| --- | --- |
| 正确性 | _checksum_bytes 逐行字节保留、末列判定、新行追加均经探针 A/B 实测；write_bytes 无 newline 转换；os.replace 顺序未变；幂等（探针 C）。未发现新缺陷 |
| 边界条件 | 空文件（b"" → b"h  a.zip\\n"）、无尾换行（b"x  a.zip" → 正确替换为新行）、CRLF（归一为 LF，契约明示）、空行保留——均已实测。N3 为畸形输入容忍度边界，已登记 |
| 异常处理 | except (ZipDistError, OSError, ValueError, zipfile.BadZipFile) 未变；无裸 except；finally 清理实测无残留；M3 修复后不再有 UnicodeDecodeError 进入 ValueError 兜底 |
| 并发安全 | 仍无锁。两进程同时对同一 dist 根归档时 mkstemp 唯一、os.replace 各自原子，校验文件可能丢一次更新；打包脚本为人工串行、issue 未要求，沿用第一轮结论不计入缺陷（本轮 diff 未改变该特性） |
| 性能 | 改为全文件 read_bytes()（原 read_text）——校验文件为几行量级，无实质变化；_digest 仍 1 MB 分块流式。无新热点 |
| 类型与测试覆盖 | pyright 0 诊断；zip_dist.py 97% 分支覆盖（3 处未覆盖已逐条解释）；新增 2 用例（46 passed）。N2 为回归防护缺口，已登记 |
| 分层与编码 | zip_dist.py 仍无 Any / TYPE_CHECKING / 相对导入 / 裸 except；from __future__ 位置正确（:16）；AST 守卫绿 |
| 文档双语 | README en/zh、手册 en/zh 已逐项核对对齐（7.4 表）；build,ts,lua 保留；无本机绝对路径新增 |
| 提交规范 | 两笔均合规（7.4 表） |

### 7.7 第二轮总体结论

- **blocker：0**
- **major：0**（第一轮 M1 / M2 / M3 三条经实测逐条闭环）
- **minor：5**（N1 存量 flake 定性更正 + 建议另案修；N2 epoch 用例未断言文件 mtime 保真；N3 畸形尾随字符致同名行不替换〔由 major 降级，理由见条目〕；N4 偏离表退出码列混填；N5 README 示例列对齐）
- 已删除误报：2 条（末尾空行、Final 常量）

门禁层面：六项必测命令实测退出码全 0（pyright 0 诊断、pytest -n auto 无 F/E、架构 37、覆盖率 93.03% ≥ 75、冒烟 1464/1464、changelog check 0）；补测 -n 1 全量 exit 0、pack 两文件 46 passed、zip_dist.py 97%。

存量 flake 状态更正：第一轮登记的「负载时序假设」经本轮 4 次单文件 -n 1 实测（0,1,0,0）证伪，实际为关闭面板后迟到 focus 事件命中已销毁 leaf 的确定性竞态（panes.py:139 硬断言）。相关三文件均不在本分支 diff，不阻塞本任务，但必须另案处理且不得继续表述为「偶发」——已按 N1 给出测试侧与产品侧两条修复路径及一条建议守卫用例。

合并判断：本分支达成 blocker 0 / major 0，可合入；仅 5 条 minor 待办（N1 存量竞态另案、N2/N3/N4/N5 建议随收尾一并处理，均不阻塞）。
