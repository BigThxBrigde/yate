# 全量 minor 修复轮 收门禁评审（2026-11-11）

范围：分支 feature/feat-pack-dist-zip，HEAD decdd769，master 18e96d2a，merge-base b982c06。
审查对象：git diff master...HEAD 中本轮 fix-all 产物（015e0eee..decdd769，含并行会话提交 1472c10b / f9a0cd4d）。
角色：code-review-expert（DeepSeek-V4.1-Flash），无人值守只读评审；未修改产品源码 / 测试 / 脚本 / 计划文档。

审查框架：.trae/skills/python-code-review 六维度 + 本剧本三级严重等级（blocker / major / minor），已执行强制自我批判。

结论摘要：blocker 0 / major 1 / minor 6；16 条待办中 14 条已闭环、F5 未闭环并引入 M1、F15 为合并时人工处置项。

## 一、实测门禁命令与退出码（本会话亲跑，未引用他人自述数字）

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | .venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/ | 0 errors, 0 warnings, 0 informations | 0 |
| 2 | .venv\Scripts\python.exe -m pytest tests/ -q -n 4 -p no:randomly | 3519 tests, failures=0, errors=0, skipped=10（junit 取证） | 0 |
| 3 | .venv\Scripts\python.exe -m pytest tests/test_architecture.py -q | 37 passed | 0 |
| 4 | .venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75 | TOTAL 19554 语句 / 93.02%，Required test coverage of 75% reached，3509 passed / 10 skipped | 0 |
| 5 | .venv\Scripts\python.exe -m tools.smoke_test run --jobs 4 | 121/121 scenarios, 1464/1464 checks, exit 0 | 0 |
| 6 | .venv\Scripts\python.exe -m tools.changelog check | released changelog sections are up to date（unreleased lag 23 属存量） | 0 |
| 7 | git diff --check master...HEAD | 无输出 | 0 |
| 8 | .venv\Scripts\python.exe -m pytest tests/test_app_panes.py -q -n 1（连跑 4 次） | 4 次全 0 | 0,0,0,0 |

备注 1（并行失败复核）：首次覆盖率门禁的 -n auto 轮出现 tests/test_app_find_replace.py::test_empty_replacement_deletes_matches_on_disk 失败。按剧本用 -n 1 复核：单文件全绿、-k 选中单次与连跑 4 次均 0、全量收集下 -n 1 选中亦 0，判定为并行负载下的时序假设问题，非本分支缺陷；随后 -n auto 重跑亦为 0。如实并列登记，不记「偶发」。

备注 2（口径）：本机 pytest -q 的汇总行在多轮后台/管道组合下会丢失（日志恒停在 100% 进度行），故以 junit-xml（tests=3519, failures=0, errors=0, skipped=10）与命令退出码为权威取证，未以「无汇总」推定通过。

备注 3（safe-delete 钩子）：本轮覆盖率 -n auto 未被 [safe-delete] 拦截（历史 count=18852 未复现），如实记录与历史两轮的同差异。

新增代码覆盖：tools/pack/zip_dist.py 168 语句 / 48 分支 / 97% 覆盖，未覆盖 4 行均属防御性或入口行（80 目录越界拒绝分支、87 POSIX mode 读取〔Windows 不执行〕、251 无备份时 unlink 回滚分支、283 __main__ 入口）。yate/editor_components/panes.py 覆盖 90%（未覆盖行与本轮改动无关）。

## 二、16 条待办逐条闭环复核（独立判断 + 文件:行号证据）

| 编号 | 独立结论 | 证据 |
| --- | --- | --- |
| F1 | 已闭环 | tools/pack/zip_dist.py:175-179 末列以 decode("utf-8", errors="surrogateescape") + str.split() 判定，新行以 os.fsencode 追加；tools/pack/zip_dist.py:239-250 用例实测非 ASCII stage 名（发布 字样）写出唯一且可反查的校验行 |
| F2 | 已闭环 | tests/test_pack_spec.py:736-774 断言 tail 内 zip_dist 调用恰好 1 次、prefix 内 0 次、WaitForExit(30000) / Remove-Item $smokeOut / Collected -> 均先于调用、调用先于块收尾（ps1 "\n}\nfinally {" / sh "\nfi"）；_after 对锚点做 count==1 断言（:701-712）|
| F3 | 已闭环（附测试保真度 minor） | tools/pack/zip_dist.py:73-75 对 symlink 记录 is_link 并 continue，:131-139 写 S_IFLNK 条目、内容为 os.readlink 文本；:138 不读目标。越界面未重开：symlink 分支不进入 :78-80 的 resolve 检查，但因从不读目标而无越界读取。:293-315 用例断言目标内容 secret 未进入 zip |
| F4 | 已闭环 | tools/pack/zip_dist.py:233-234 两个 os.replace 前 chmod 0o644；tests/test_pack_zip.py:318-327 POSIX 断言 0o644、Windows 断言 S_IWRITE，条件分支正确 |
| F5 | 未闭环（引入新缺陷，见 M1） | tools/pack/zip_dist.py:209 以 O_CREAT|O_EXCL 原子创建实现跨进程互斥，锁已存在时不删除他人锁（:210-213）——这两点正确；但锁创建（:207-214）位于 try（:225）之外，三条失败路径泄漏锁文件（实测见 M1）|
| F6 | 已闭环（有残留 minor，见 m1） | tools/pack/zip_dist.py:243-252 两次 os.replace 同处一个 try，任一失败均回滚；:342-364 校验 replace 失败用例、:367-386 首次 zip replace 失败用例均断言旧 zip 字节还原且无 tmp/bak 残留。复制式备份（:242 shutil.copyfile）修复了「移走旧 zip 后首 replace 失败丢旧 zip」|
| F7 | 已闭环 | tools/pack/zip_dist.py:204-205 以 resolved_dist == root or is_relative_to(root) 拒绝；:389-398 参数化用例覆盖 inside 与 inside/nested 且断言未创建目标目录。未误伤正常用法：release/ 与 stage 为兄弟目录，root 不含 release/ |
| F8 | 已闭环 | tests/test_pack_zip.py:76-86 以 os.utime 固定 1700000000，断言目录条目为 _ZIP_EPOCH 而文件条目等于 time.localtime(1700000000)[:6]，可拦截把 _write_archive 也改 epoch 的漂移 |
| F9 | 已闭环 | tools/pack/zip_dist.py:175 用 str.split()（Unicode 空白）切分末列；tests/test_pack_zip.py:253-262 以全角空格 \xe3\x80\x80 结尾的同名行被替换、他人行 h1 other.zip 保留 |
| F10 | 已闭环 | .trae/documents/pack-dist-zip-plans/overview.md:103 退出码格由「绑定失败 / 替代路径 0」改为「1（--dist 绑定）/ 0（-Dist 与 bat）」，非零与 0 不再混填（提交 1472c10b） |
| F11 | 已闭环 | README.md:315-319 与 README.zh.md:331-335 注释起始列统一，双语逐行对应（5 条示例 + 2 行说明）；实测列位一致 |
| F12 | 已闭环（守卫偏松，见 m2） | pack/pack.bat:49 在 exit /b 前追加 if errorlevel 1 echo error: pack.ps1 failed ... 1>&2；实测 pack\pack.bat --bogus-flag 在 stderr 打出该提示且 exit /b 语义未变，pack\pack.bat --help 仍 0 |
| F13 | 已闭环（裁定可接受） | pack/pack.sh:28 增加「2,21p 区间由 tests/test_pack_spec.py 钉住」注释；tests/test_pack_spec.py:800-846 已把 usage / --no-zip / by default 各行号与端点比较并把旧 2,19p 列入黑名单。sed 无稳定语义锚点，硬编码不可消除，此前裁定「无需改动」成立 |

| F14 | 已闭环（合并模拟实测 + 结构依据） | 临时 worktree 合并模拟实测架构 38 passed、全量 pytest -n 1 通过、diffcheck 0；本会话独立补证：git diff b982c06 18e96d2a -- tests/test_architecture.py 显示 master 新增 1 个守卫 test_hover_key_is_shared_and_identical，本分支 37 + 1 = 38 成立 |
| F15 | 未冒充已修复，裁定「合并时人工处置」充分 | 本会话独立实测：本分支 tools.changelog check = 0；主仓 master 同命令 = 0；合并树红项来自合并提交重算 v0.2.18 已发布段，generate 后转绿（见进度记录）。PR diff 不含 CHANGELOG，按非目标不改。处置路径明确（合并时运行 python -m tools.changelog generate），登记为人工项而非已修复 |
| F16 | 已闭环（附断言细节 minor，见 m4） | yate/editor_components/panes.py:218-221 改用 find_leaf 宽松判空后静默 return；:135-140 leaf_by_id 仍为严格 assert；与既有 leaf_for（:128-133）语义一致，未新增概念。tests/test_app_panes.py:141 补 pilot.pause()；:152-181 新增守卫用例；四次 tests/test_app_panes.py -q -n 1 连续全 0 |

判定：16 条中 14 条已闭环，F5 未闭环并引入新缺陷（M1），F15 属流程项且处置披露充分。此前的 16 条与本次新发现不重叠。

## 三、问题清单（按严重程度排序，含自我批判状态）

### [major] M1 锁文件在三条失败路径上残留，导致后续重试永久失败

位置：tools/pack/zip_dist.py:207-214（锁创建）与 :217-222（锁创建之后、try 之前的抛错点）；受影响断言点 :218-219。

描述：锁以 O_CREAT|O_EXCL 创建（:209）后，try 块自 :225 才开始，finally 的 lock_path.unlink（:259）因此不覆盖三条在 :225 之前抛错的路径：

1. stage 无文件（:218-219），实测抛出「stage has no files to archive」后 dist 目录残留 .empty.lock；
2. _stage_files 抛 ZipDistError（:217 调用的 :80 越界条目拒绝），实测残留 .st.lock；
3. tempfile.mkstemp 失败（:220，如磁盘满 / 权限不足），实测残留 .st.lock。

影响：由于 O_EXCL 语义，残留锁使同一 stage 的任何后续归档都报 another archive is in progress（:210-213），必须人工删除 .<stage>.lock 才能恢复。这是常规重试场景（打包失败 -> 修复 -> pack.bat / pack.sh）即会命中的路径，与剧本对 major 的定义「边界条件缺陷」相符。此外 :190 的 docstring 声称 all temporary/lock files are cleaned up，与实测不符。

本缺陷由本轮 F5 修复新引入（前轮无锁），属回归。既有用例 test_archive_stage_when_stage_empty_raises_zip_dist_error 只断言抛错，未断言锁被清理，故 CI 未拦截。

修复建议：把锁创建纳入 try 的覆盖范围，例如在 :214 之后立即进入 try，并把 lock 创建本身写成 try/except 后再统一由 finally 清理；或把 stage 校验与 _stage_files 调用整体移到加锁之前。并补三条用例断言失败后 list(dist.glob(".*.lock")) == []。

引用：python-coding-style.md（with / finally 资源清理纪律）；skill Error Handling 维度「Missing finally or with for resource cleanup」。

自我批判：确认保留 major。初版曾考虑 blocker（常规重试即失败），但首次调用本身能正常完成，失败仅发生在需要人工干预的错误路径上，未造成数据丢失，故按 major；已实测三条路径与残留文件名，非推测。

### [minor] m1 回滚 os.replace 二次失败会掩盖原始错误原因

位置：tools/pack/zip_dist.py:246-252（尤其 :248）。

描述：except OSError 分支内直接执行 os.replace(backup, archive) 回滚。若回滚本身失败，新的 OSError 会替换原始异常成为对外异常；main()（:274-276）只打印 f"error: zip archive failed: {exc}"，不打印 traceback，因此命令行用户只看到回滚失败，看不到真正的首个失败原因。实测：注入首个 replace 失败 + 回滚 replace 失败，输出 RAISED: rollback replace failed，原始 first replace failed 不可见。

影响面有限：实测该情况下旧 zip 仍在（archive exists: True），无 bak/tmp 残留，无数据丢失；仅诊断信息退化。若直接调用 archive_stage（不经 main），Python 的异常链仍保留 __context__。

修复建议：在回滚外层再包一层 try/except，把回滚失败并入消息（如 raise ZipDistError(f"swap failed: {exc}; rollback also failed: {rb}") from exc），或在 main 打印时附 exc.__context__。

引用：python-coding-style.md §4.5（异常须可读、不得只给笼统信息）；skill Error Handling 维度。

自我批判：初版定级 major（异常原因丢失 + 可命中常规异常注入），复核后降级为 minor——触发需要两次连续 OSError（第二个替换失败且回滚亦失败），属双重故障叠加；数据安全无损、旧 zip 完好、异常链在库调用层仍可见，且仅在 CLI 层被简化。降级理由登记在此。

### [minor] m2 F12 静态守卫未钉住「提示行先于 exit /b」的相对位置

位置：tests/test_pack_spec.py:913-915。

描述：守卫只断言 exit /b %ERRORLEVEL%、if errorlevel 1、error: pack.ps1 failed 三个子串分别存在，不校验先后顺序。若日后有人把提示行移到 exit /b 之后，提示永远不会执行，而守卫仍然通过，等于回归到 F12 修复前的行为。同类问题在 F2 的处理中已被正确规避（用 index 比较顺序），此处属遗漏。

修复建议：补 assert bat.index("if errorlevel 1") < bat.index("exit /b %ERRORLEVEL%")。

引用：skill Step 2 Correctness 边界条件；本轮 F2 已确立同类「顺序即契约」的守卫范式。

自我批判：确认保留 minor。无夸大——当前实现顺序正确，实测提示可达，故非缺陷而是守卫强度不足，不构成 blocker/major。

### [minor] m3 F3 的两个 symlink 用例以 monkeypatch 模拟而非真实符号链接

位置：tests/test_pack_zip.py:265-315（monkeypatch Path.is_symlink 与 zip_dist.os.readlink）。

描述：用例把普通文件伪装成 symlink 并伪造 readlink 返回值，未创建真实符号链接。因此以下真实行为未被覆盖：真实 symlink 的 lstat().st_mtime 取值、os.readlink 返回相对路径时的字节编码、以及 Windows 上真实 symlink 的目录链接语义。考虑到 Windows 创建 symlink 需要特权、Linux 构建不在 CI，这一妥协可理解，但应在用例 docstring 或跳过条件中显式登记，否则读者会误以为已测真实链接。

修复建议：在 POSIX 上为真实 symlink 增加一条用例（pytest.mark.skipif(os.name != "posix")），或至少在现有用例 docstring 注明「simulated, real symlink covered only on POSIX builds」。

引用：skill Step 2 Correctness 边界条件；issue 验收判据 2（F3 若选 symlink 条目须断言 external_attr 与内容）。

自我批判：确认保留 minor（测试保真度，非功能缺陷；Windows 产物不含 symlink，Linux 产物才含）。

### [minor] m4 F16 守卫用例未断言 stale_ids 非空

位置：tests/test_app_panes.py:174-177。

描述：stale_ids 由 ids 过滤 survivor 得到，循环体为唯一触发点；若 stale_ids 意外为空，for 循环零次迭代，测试仍全绿，形成空过（vacuous pass）。当前 ids 长度已断言为 2（:168）且 id 源自 count() 唯一，风险低，但守卫用例应自证其触发路径。

修复建议：循环前补 assert len(stale_ids) == 1。

引用：skill Step 2 Correctness；本轮 F2 的 _after 断言 count==1 是同类「守卫须自证触发」范式。

自我批判：确认保留 minor。降级过一版：初版曾想并入 F16 结论，因风险低且非功能缺陷，独立列为 minor 更便于跟踪。

### [minor] m5 不同 stage 并发归档同一 dist 根时 SHA256SUMS.txt 可能丢更新

位置：tools/pack/zip_dist.py:207（锁粒度为 stage 名）与 :216 / :232 / :245（共享 SHA256SUMS.txt）。

描述：锁名 .<stage>.lock 只互斥同一 stage，两个不同 stage 并发归档同一 dist 根时都会读取并替换同一份 SHA256SUMS.txt，后写者可能覆盖前写者新增的行（读-改-写竞态）。实测串行两个 stage 时两行均保留（无问题）；并发为理论竞态，打包脚本是人工串行调用。

修复建议：把锁粒度提升到 dist 根（如 .<dist>.lock 或 SHA256SUMS.txt.lock），或在 docstring 显式声明「同一 dist 根不支持并行归档」。

引用：skill Step 2 并发安全；F5 原始 issue 描述即为此类丢失。

自我批判：确认保留 minor。本轮 F5 已解决「同一 stage 并发」这一被点名场景，本项为其残余面且实际调用串行，不夸大。

### [minor] m6 陈旧锁无自愈机制，进程被强杀后需人工清理

位置：tools/pack/zip_dist.py:209-213。

描述：锁文件无 PID / 时间戳内容，也无 TTL 或 stale 检测。打包进程若被 taskkill / kill -9 / 断电终止，锁不会由 finally 清理（finally 仅在正常异常展开时执行），后续归档永久报 another archive is in progress，与 M1 的表现一致但根因不同（M1 是 finally 覆盖不足，本条是设计层面缺少陈旧锁识别）。结合 M1，建议修复 M1 时一并考虑。

修复建议：锁文件写入 pid 与启动时间，检测到锁存在时校验 pid 是否存活（POSIX os.kill(pid, 0)），或提供 --force-unlock / 在错误信息中直接给出「删除该锁文件」的指引。

引用：skill Step 2 并发安全 / Maintainability；Error Handling「Error messages that leak implementation details」反向要求——此处错误信息未给出处置办法。

自我批判：初版曾与 M1 合并，复核后独立登记——M1 是本轮实现的确定性缺陷（三条可达路径），本条是设计层面的可维护性缺口（需外部强杀才触发），两者修复可合并但性质不同。确认保留 minor。

## 四、反向核查：本轮修复是否引入新缺陷

| 核查面 | 结论 |
| --- | --- |
| shutil.copyfile 复制大 zip 的成本 / 失败面 | 实测复制 64 MB 耗时 0.035s，对约 22 MB 交付 zip 可忽略；copyfile 中途失败时 backup 已赋值但 finally 只删 bak，旧 archive 完好，无数据丢失。可接受 |
| 锁残留（进程崩溃） | 崩溃时锁不被清理——与 M1 同源；已单列 m6 跟踪设计层面缺口 |
| os.fsencode 跨平台编码 | Windows 上 os.fsencode 走 mbcs 严格模式（实测 os.fsdecode(b"\xff") 直接抛 UnicodeDecodeError），因此非 UTF-8 字节文件名在 Windows 不可达；POSIX 走 surrogateescape 可逆。实测 surrogateescape 语义下旧行 yate-\xff-x.zip 被正确识别并替换，新行字节与平台编码自洽。跨平台边界无缺陷，但「Windows 产物上的校验文件名恒为合法 UTF-8」应视为隐含前提 |
| symlink 条目对 Windows Expand-Archive / 解压的影响 | 实测 zipfile.extractall 在 Windows 上把 S_IFLNK 条目解为普通文件（内容为链接目标文本，is_symlink=False）。因 Windows 构建产物不含 symlink，此差异只影响「Linux 产物在 Windows 上解压」这一非交付路径；不构成 blocker，建议在 README 或手册注一句「链接条目须在类 Unix 上解压」|
| surrogateescape 解码任意字节的可逆性 | decode(errors="surrogateescape") 对任意字节可逆，但本实现从不把解码结果写回（:175 仅用于比较，:179 用 os.fsencode 重新编码），因此不涉可逆性风险；行内容以原始 bytes 保留（:178），其它行字节原样 |
| panes 宽松判空的边界 | find_leaf 返回 None 恰等于「该叶已不在树中」，静默 return 是正确语义，不会掩盖状态错误；leaf_by_id 的 strict 断言保留给 owned-invariant 调用点。无边界问题 |
| 静态守卫过严 / 过松 | 过严：zip_dist.py 的 stdlib 白名单（tests/test_pack_spec.py:939-950）是显式清单，新增 stdlib 需同步更新——属有意摩擦力，符合 stdlib-only 契约，不算误伤。过松：m2 已登记（F12 顺序未钉）；其余守卫经复核（F2 顺序 / _after 唯一性 / catch-all 锚定 \s+\*\)\s*$）强度充分 |
| type: ignore / Any / 相对导入 / 非 ASCII 注释残留 | 实测 tools/pack/zip_dist.py 与 tests/test_pack_zip.py 中 type: ignore / Any 命中均为 0；无相对导入；架构守卫 test_comments_and_docstrings_stay_ascii 与 test_no_relative_imports 通过（37 项架构守卫全绿） |
| git diff --check master...HEAD | 0 |

## 五、强制自我批判登记（结论可追溯）

| 条目 | 初版定级 | 最终 | 状态 | 理由 |
| --- | --- | --- | --- | --- |
| M1 锁残留 | blocker | major | 降级保留 | 首次调用可正常完成，失败仅在需人工干预的错误路径，无数据丢失；已实测三条可达路径 |
| m1 回滚掩盖异常 | major | minor | 降级保留 | 需双重 OSError 叠加，数据安全无损，异常链在库层仍可见 |
| m2 F12 守卫顺序 | minor | minor | 确认保留 | 当前实现正确，属守卫强度不足 |
| m3 symlink 用例保真度 | minor | minor | 确认保留 | 真实符号链接未覆盖，已在理由中说明平台限制 |
| m4 stale_ids 空过 | minor | minor | 确认保留 | 守卫未自证触发路径 |
| m5 跨 stage 并发丢更新 | major | minor | 降级保留 | 脚本为人工串行调用；F5 已解决被点名的同 stage 场景，本项为残余面 |
| m6 陈旧锁无自愈 | minor | minor | 确认保留 | 与 M1 性质区分：设计缺口 vs 实现缺陷 |

已删除 / 未报条目（避免无实证断言）：

- 「_write_archive 每文件重复 stat + 整文件 read_bytes() 内存峰值」——前两轮已按 python-coding-style.md §6.1 判为无实测依据的预优化并删除，本会话无 profiler 证据，不重提。
- 「stage.is_dir() 与 resolve() 之间的 TOCTOU」——构建脚本为单进程人工调用，无外部并发改写 stage 的实证场景，证据不足，不报。
- 「_checksum_bytes 用 str.split() 会把含全角空格的合法文件名切开」——实测该方向只会漏删、不会误删他人行（aa  yate\u3000x.zip 被保留），属安全方向，不构成缺陷。

## 六、总体结论

- blocker：0
- major：1（M1 锁文件三条失败路径残留，本轮 F5 引入的回归）
- minor：6（m1 回滚掩盖原始异常、m2 F12 守卫顺序未钉、m3 symlink 用例保真度、m4 stale_ids 空过、m5 跨 stage 并发丢更新、m6 陈旧锁无自愈）

门禁层面：八项实测退出码全 0（pyright 0 诊断、全量 pytest 3519/0 failures、架构 37、覆盖率 93.02% 高于 75、冒烟 1464/1464、changelog 0、diffcheck 0、panes -n 1 四连 0）。门禁全绿但 M1 未被现有用例拦截，说明 test_archive_stage_when_stage_empty 系列缺少「失败后无锁残留」断言。

合并判断：当前不应直接合入。M1 必须先修——它把「空 stage / 越界条目 / 磁盘满」这三类可恢复错误变成需要人工介入的永久失败，与 F5 让锁更安全的初衷相反；修复面很小（调整 try 起点 + 补 3 条断言）。m2 / m4 建议同批补，成本一行；m1 / m3 / m5 / m6 可与 M1 同批或另案。修完 M1 即达仅 minor 待办状态。

F14 / F15 仍按前轮裁定：合并树上重跑门禁（架构 38 已由本会话独立取证）、changelog 在合并时人工运行 generate；本轮不宣称这两项已修复。

已撤销：本会话临时探针与日志文件已清理；产品源码 / 测试 / 脚本 / 计划文档零改动（git status 仅含另一会话未提交的 progress 文档修改，本评审未触碰）。

修复方案：[pack-dist-zip-minor-fixes-review-iteration-plan.md](../documents/pack-dist-zip-minor-fixes-review-iteration-plan.md)（M1 迭代修复，双向互链）。

## 七、第二轮迭代复核（M1）

范围：仅提交 729a2c6e 的 4 个文件（tools/pack/zip_dist.py、tests/test_pack_zip.py、tests/test_pack_spec.py、tests/test_app_panes.py），不重跑第一轮 16 条全量审查。
角色：code-review-expert（DeepSeek-V4.1-Flash），无人值守只读复核；产品源码 / 测试 / 脚本 / 计划文档零改动。
审查框架：.trae/skills/python-code-review 六维度 + 剧本三级严重等级，已执行强制自我批判。

结论摘要：blocker 0 / major 1 / minor 2；M1 的三条原失败路径已闭环，但 M1 目标（所有失败路径释放锁）在 finally 内部异常隔离上仍未闭环（见 N1）。

### 7.1 实测命令与退出码（本会话亲跑）

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | .venv/Scripts/python.exe -m pytest tests/test_pack_zip.py -q | 30 passed | 0 |
| 2 | .venv/Scripts/python.exe -m pytest tests/test_pack_spec.py -q | 32 passed | 0 |
| 3 | .venv/Scripts/python.exe -m pytest tests/ -q -n auto | 全绿（仅 skipped，无 failed/error） | 0 |
| 4 | .venv/Scripts/python.exe -m pyright yate/ tests/ tools/ pack/ | 0 errors, 0 warnings, 0 informations | 0 |
| 5 | .venv/Scripts/python.exe -m pytest tests/test_architecture.py -q | 37 passed | 0 |
| 6 | .venv/Scripts/python.exe -m pytest tests/test_app_panes.py -q -n 1 | 27 passed | 0 |
| 7 | git diff --check master...HEAD | 无输出 | 0 |
| 8 | 相关用例连跑 5 次（mkstemp/releases_lock/copyfile/replace） | 5 次全 7 passed | 0,0,0,0,0 |

备注：并行 -n auto 轮无失败，故无需 -n 1 复核；本轮未跑覆盖率与冒烟（按任务约定由主代理收尾统一执行）。

### 7.2 M1 是否闭环：逐路径独立探针实证

探针在仓库外临时目录独立编写，直接调用 tools.pack.zip_dist.archive_stage，失败后断言 list(dist.glob(.*.lock)) == []，并同时检查 *.tmp / *.bak / 隐藏文件。

| 失败路径 | 注入方式 | 实测异常 | 锁/临时文件残留 | 结论 |
| --- | --- | --- | --- | --- |
| 空 stage（第一轮原路径 1） | 空目录 + dist | ZipDistError: stage has no files to archive | locks=[] tmp=[] bak=[] hidden=[] | 闭环 |
| 修复后重试（补文件） | 同 stage 再调一次 | 无异常 | 归档成功，locks=[] | 闭环 |
| _stage_files 抛错（原路径 2） | monkeypatch _stage_files | ZipDistError: stage entry escapes stage root | 全空 | 闭环 |
| 首个 mkstemp 失败（原路径 3） | monkeypatch tempfile.mkstemp | OSError: disk full | 全空 | 闭环 |
| 第二个 mkstemp（sums tmp）失败 | 计数桩第 2 次抛错 | OSError: sums disk full | 全空（已建 zip tmp 亦清） | 闭环 |
| 首次 zip os.replace 失败（有旧 zip） | monkeypatch os.replace | OSError: zip replace failed | 全空，旧 zip 字节仍为 old | 闭环 |
| sums os.replace 失败（无旧 zip，backup=None） | monkeypatch os.replace | OSError: sums replace failed | 全空，新 zip 已回滚删除 | 闭环 |
| shutil.copyfile 失败（有旧 zip） | monkeypatch copyfile | OSError: copy failed | 全空，旧 zip 仍为 old | 闭环 |
| zip tmp 已建后中途抛非 OSError | monkeypatch _digest 抛 RuntimeError | RuntimeError | 全空 | 闭环 |
| 他人已持锁（FileExistsError） | 预置 .yate-0.2.18.lock | ZipDistError: another archive is in progress | 他人锁保留（FOREIGN_LOCK_PRESERVED=True） | 闭环（未误删他人锁） |

#### 新增用例有效性反向验证（非空过的决定性证据）

把父提交 4a4ce9a7 的 tools/pack/zip_dist.py（修复前）复制到仓库外独立包目录，以同一段断言逻辑复跑三条新增用例：

- case1（空 stage）：修复前 C1_NEW_TEST_PASSES=False，修复后 True
- case2（_stage_files 抛错）：修复前 False，修复后 True
- case3（mkstemp 失败）：修复前 False，修复后 True

即三条新用例在修复前**必然变红**，修复后转绿 —— 用例真实拦截回归，不是空跑。

### 7.3 m2 / m4 是否真能拦截漂移（负向演练）


#### m2（tests/test_pack_spec.py:916-918）

- 进程内实测真实文本偏移：if errorlevel 1 在 2352，exit /b %ERRORLEVEL% 在 2440，前者在前，守卫成立。
- 负向演练：在内存副本中把提示行挪到 exit /b 之后（不写盘、不改仓库文件），同样断言算出 DRIFT_GUARD_HOLDS=False。
- 结论：**m2 已闭环**，顺序契约被真实钉住。


#### m4（tests/test_app_panes.py:175）

- 实测 exec 一段等价断言，stale_ids 为空列表时抛 AssertionError 且带消息 guard must exercise at least one closed leaf。
- 结论：**m4 已闭环**，空过（vacuous pass）被阻断。
- 备注：第一轮建议写成 assert len(stale_ids) == 1，实际用 assert stale_ids。两者都能拦截空集；后者不锁定具体数量，更耐受 pane id 分配变化，判定可接受。

### 7.4 反向核查：Path / None 改造是否覆盖所有使用点


#### 三个可选变量的使用点

- zip_tmp（tools/pack/zip_dist.py:217 声明 None，:229 赋值为 zip_path，:260-261 判空后 unlink）。所有使用点都在赋值之后，finally 判空齐全。
- sums_tmp（:218 声明，:236 赋值，:262-263 判空）。同上。
- backup（:219 声明，:246 赋值，:253 判空判断，:264-265 判空 unlink）。:253 的 if backup is not None 让回滚分支在 backup 为 None 时正确走 archive.unlink(:257)，已由「sums replace 失败（无旧 zip）」路径实证：新 zip 被回滚删除、无残留。
- zip_path / sums_path_tmp / backup_path 三个非 None 局部变量仅在 try 内使用，作用域足够，pyright strict 0 诊断（实测）。


#### return ArchiveResult 的位置与变量赋值


- return 位于 :267，在 try / finally 之外；异常路径不会到达（异常向上传播），正常路径下 size / digest 必已在 :231-232 赋值。无 UnboundLocalError 风险。
- 实测 10 条失败路径全部正确抛出预期异常，无 UnboundLocalError / NameError。


#### mkstemp monkeypatch 对 pytest 的影响


- 实证 zip_dist.tempfile is tempfile 为 True，故 monkeypatch.setattr(zip_dist.tempfile, mkstemp, ...) 实际替换的是**全局 tempfile.mkstemp**（PATCHED_GLOBAL=True），monkeypatch 退出时自动还原（RESTORED=True）。
- 稳定性实测：相关用例连跑 5 次全部 7 passed；全量 -n auto 通过。xdist 为进程级隔离、同进程内串行执行，未观察到对 pytest 自身或其它用例的影响。
- 判定：**不构成缺陷**（无失败实证），但作用面大于用例意图，登记为说明而非问题。

### 7.5 问题清单（按严重程度排序，含自我批判状态）


#### [major] N1 finally 内任一 unlink 抛错会跳过后续清理，锁仍残留（M1 目标未完全闭环）

位置：tools/pack/zip_dist.py:259-266（finally 块，四个 unlink 顺序执行，彼此无异常隔离）。

描述：：260-266 依次清理 zip_tmp / sums_tmp / backup / lock，但任一 unlink 抛出 OSError（Windows 上文件被杀毒软件或其它进程短暂占用即触发 PermissionError 是现实场景）时，finally 会在此处中断，**后面的清理全部不执行**，包括第 266 行的 lock_path.unlink。

实测两条独立路径（仓库外探针，monkeypatch Path.unlink 定向抛 PermissionError）：

- zip tmp 的 unlink 抛 PermissionError: locked by another process → 抛该异常，且 locks=[.stg.lock] 残留；
- backup 的 unlink 抛 PermissionError: bak locked → 抛该异常，且 locks=[.stg.lock]、bak 文件同时残留。

影响：与 M1 同一后果 —— 残留锁使同一 stage 的任何后续归档永久报 another archive is in progress（:210-213），必须人工删锁。M1 的既定目标是「所有失败路径都经 finally 释放锁」，本路径说明该目标尚未完全达成。

归因：**存量缺陷，非本轮 729a2c6e 引入**（在父提交 4a4ce9a7 上同样探针同样残留），但属 M1 修复范围应覆盖而未覆盖的残余面。

修复建议：给 finally 内每个清理动作各自包一层 try/except OSError，或至少把 lock_path.unlink 提到最前 / 用单独 try 包裹，保证锁一定被尝试删除；可参考：

    finally:
        for tmp in (zip_tmp, sums_tmp, backup):
            if tmp is None:
                continue
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

并补两条用例：monkeypatch Path.unlink 让 *.tmp / *.bak 抛 PermissionError，断言 lock 已删除。

引用：skill Error Handling 维度「Missing finally or with for resource cleanup」；python-coding-style.md 资源清理纪律。

自我批判：初版定级 blocker（常规重试即永久失败 + Windows 文件占用常见），复核后降为 **major** —— 触发需外部进程占用临时文件这一额外条件，非确定性失败；且不造成数据丢失（旧 zip 完好、异常如实抛出）。确认保留 major。

#### [minor] N2 新用例的 fail_once 实际无条件抛错，命名与行为不符

位置：tests/test_pack_zip.py:424-425。

描述：函数名 fail_once 暗示「只失败一次」，实现却是无条件 raise OSError(disk full)，且返回类型标注为 None（不返回 fd/路径），与 mkstemp 契约不符。命名会让后来者误以为覆盖了「首次失败后重试成功」的场景（实际没有）。

修复建议：改名为 fail_always / reject_mkstemp，或真的实现「首次抛错、后续透传原名 mkstemp」以同时覆盖重试路径。

自我批判：确认保留 minor。非功能缺陷，属可读性 / 命名准确性。


#### [minor] N3 空 stage 的两条用例前半段断言完全重复

位置：tests/test_pack_zip.py:164-170（test_archive_stage_when_stage_empty_raises_zip_dist_error）与 :390-400（test_archive_stage_when_stage_is_empty_releases_lock）。

描述：:168-170 与 :394-396 都是「空 stage 抛 no files，再断言 list(dist.glob(.*.lock)) == []」，逐字等价。新增用例的增量价值只在后半段（补文件后重试成功），前半段属重复。

修复建议：把新增用例收敛为「重试成功」单一诉求，或让既有用例只保留抛错断言、把无锁断言集中到新用例一处。

自我批判：确认保留 minor。第一轮 M1 的修复建议要求「既有空 stage 用例补 *.lock 断言」，本轮照做后又新建了同样断言的用例，属演进中的冗余，非错误。

### 7.6 第一轮待办 minor 是否升级

- m1（回滚二次失败掩盖原始异常）：代码路径 tools/pack/zip_dist.py:252-258 本轮未改动，无新实证，不升级，维持 minor。
- m3（symlink 用例为 monkeypatch）：相关代码与用例未改动，不升级，维持 minor。
- m5（跨 stage 并发共享 SHA256SUMS.txt 丢更新）：锁粒度仍为每 stage 一个锁（:207），未改动，不升级，维持 minor。
- m6（陈旧锁无进程号与过期时间自愈）：锁创建逻辑（:208-214）未改动，不升级，维持 minor。

附注：N1 与 m6 表现相同（后续归档永久失败）但根因不同 —— N1 是 finally 内部异常隔离缺失（可修），m6 是缺少陈旧锁识别（设计层）。二者修复可合并考虑。

### 7.7 强制自我批判登记（结论可追溯）

| 条目 | 初版定级 | 最终 | 状态 | 理由 |
| --- | --- | --- | --- | --- |
| N1 finally 内 unlink 抛错致锁残留 | blocker | major | 降级保留 | 触发需外部进程占用临时文件这一额外条件，非确定性失败；旧 zip 完好，无数据丢失 |
| N2 fail_once 命名与行为不符 | minor | minor | 确认保留 | 非功能缺陷，仅命名准确性 |
| N3 空 stage 两条用例断言重复 | minor | minor | 确认保留 | 演进产生的冗余，非错误 |
| M1 三条原失败路径 | — | — | 确认闭环 | 8 条路径探针全清 + 修复前版本反证 False/True 翻转 |
| m2 顺序守卫 | — | — | 确认闭环 | 真实偏移正确 + 内存漂移演练变红 |
| m4 stale_ids 非空 | — | — | 确认闭环 | 空列表实测触发 AssertionError |
| mkstemp monkeypatch 全局作用面 | minor | 删除 | 删除 | 5 次连跑 + 全量并行均无失败实证，按剧本不留无实证断言 |
| 三组双变量 zip_path/zip_tmp 等 | minor | 删除 | 删除 | pyright strict 收窄所需的惯用写法，属风格偏好而非缺陷 |

已删除 / 未报条目：

- 测试与产品代码之间的 glob 通配符写法差异（.*.lock 与 .* 混用）：逐条核对后均能命中目标文件，无漏断言，不报。
- test_archive_stage_when_stage_files_reject_entry_releases_lock 用整体替换 _stage_files 而非构造真实越界条目：用例语义是「_stage_files 抛错时锁是否清理」，与真实越界路径等价，不报。
- 新增用例未断言 ArchiveResult 字段：与本次修复目标无关，既有用例已覆盖，不报。


### 7.8 总体结论


- blocker：0
- major：1（N1 finally 内任一 unlink 抛错会跳过后续清理，锁仍残留；存量缺陷、非本轮引入，但属 M1 修复目标未覆盖的残余面）
- minor：2（N2 fail_once 命名与行为不符、N3 空 stage 两条用例断言重复）


#### M1 是否已闭环


**部分闭环。**


- 已闭环：第一轮点名的三条失败路径（空 stage、_stage_files 抛错、首个 mkstemp 失败）以及本轮追加核查的另外七条路径（sums mkstemp 失败、zip replace 失败、sums replace 失败且 backup 为 None、copyfile 失败、中途非 OSError、他人已持锁）全部经 finally 清理，锁与临时文件零残留；锁创建失败时不误删他人锁。
- 未闭环：finally 内部四个 unlink 之间没有异常隔离，任一抛 OSError 会跳过 lock_path.unlink，锁仍残留（N1，tools/pack/zip_dist.py:259-266）。
- 因此「所有失败路径都释放锁」这一 M1 验收口径尚未达成；修复面很小 —— finally 内逐项 try/except，或把 lock_path.unlink 提到最前并用独立 try 包裹。


#### 合并判断


本轮 729a2c6e 的改动方向正确、三条原路径与 m2 / m4 均已实证闭环，且新增用例经修复前版本反证确非空跑。但 M1 的验收口径是「所有失败路径释放锁」，N1 属于同一口径下的漏网路径，建议与 N1 一并修复后再收门禁；N2 / N3 可与 N1 同批，成本各一两行。修复 N1 后即达 0 blocker / 0 major / 2 minor。


#### 无副作用的证据


- 产品源码 / 测试 / 脚本 / 计划文档零改动：git status 仅含另一会话未提交的 .trae/documents/pack-dist-zip-progress.md 修改，本评审未触碰；tools / pack / tests / yate 下无未跟踪残留。
- 本会话临时探针目录与导出文件已在系统临时目录下清理，仓库内无残留。
- 探针与负向演练全部在仓库外临时目录或内存中完成，未对仓库文件做任何写入（唯一写入是本评审记录的本章节）。

## 八、第三轮迭代复核（N1 收敛）

范围：仅提交 `66540333` 的 2 个代码/测试文件（`tools/pack/zip_dist.py`、`tests/test_pack_zip.py`），前两轮已复核内容不重复审。
角色：code-review-expert（DeepSeek-V4.1-Flash），无人值守只读复核；产品源码 / 测试 / 脚本 / 计划文档零改动。
审查框架：`.trae/skills/python-code-review` 六维度 + 剧本三级严重等级，已执行强制自我批判。

结论摘要：blocker 0 / major 0 / minor 3；N1、m1、N2、N3 全部闭环，达到收门禁条件。

### 8.1 实测命令与退出码（本会话亲跑）

| # | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 1 | `.venv/Scripts/python.exe -m pytest tests/test_pack_zip.py -q` | 32 passed | 0 |
| 2 | `.venv/Scripts/python.exe -m pytest tests/test_pack_spec.py -q` | 32 passed | 0 |
| 3 | `.venv/Scripts/python.exe -m pytest tests/ -q -n auto` | 全绿（仅 1 skipped，无 failed/error） | 0 |
| 4 | `.venv/Scripts/python.exe -m pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| 5 | `.venv/Scripts/python.exe -m pytest tests/test_architecture.py -q` | 37 passed | 0 |
| 6 | `.venv/Scripts/python.exe -m pytest tests/test_app_panes.py -q -n 1` | 27 passed | 0 |
| 7 | `git diff --check master...HEAD` | 无输出 | 0 |
| 8 | `tests/test_pack_zip.py` 连跑 5 次 | 5 次全 32 passed | 0,0,0,0,0 |

备注：并行 `-n auto` 轮无失败，故无需 `-n 1` 复核；本轮按任务约定未跑覆盖率与冒烟（由主代理收尾统一执行）。

### 8.2 N1 是否闭环：逐路径独立探针实证

探针在仓库外系统临时目录独立编写，直接调用 `tools.pack.zip_dist.archive_stage`，定向 monkeypatch `Path.unlink` 让指定后缀抛 `PermissionError`，失败后断言 `list(dist.glob(".*.lock")) == []`。

| 注入路径 | 实测对外异常 | 锁残留 | tmp 残留 | bak 残留 | 结论 |
| --- | --- | --- | --- | --- | --- |
| zip tmp 的 `unlink` 抛 `PermissionError` | 无（归档成功） | `[]` | `[]` | `[]` | 闭环 |
| backup 的 `unlink` 抛 `PermissionError` | 无（归档成功） | `[]` | `[]` | 注入所致残留（预期） | 闭环 |
| 锁自身 `unlink` 抛 `PermissionError` | 无（归档成功） | `[.yate-0.2.18-windows-x64.lock]` | `[]` | `[]` | 锁无法删除，属注入的必然结果，非缺陷 |

修复前反证（决定性证据）：把父提交 `4a4ce9a7` 的 `zip_dist.py` 导出到仓库外独立目录，以同一段断言逻辑复跑 zip tmp unlink 失败场景：

- 修复前：`raised=PermissionError: busy`、`locks=[.yate-0.2.18-windows-x64.lock]`（锁残留）；
- 修复后：`raised=None`、`locks=[]`。

即 `tests/test_pack_zip.py` 的两条新增用例在修复前必然变红、修复后转绿，用例真实拦截回归，不是空跑。

清理异常是否掩盖原始业务异常（同时注入 swap 失败 + 清理失败）：实测 `raised=OSError: business swap failed`、`locks=[]` —— 对外异常仍是原始业务异常，锁已释放。**N1 闭环**。

### 8.3 m1 是否闭环：回滚失败不掩盖首次失败

注入「首次 `os.replace(zip_tmp, archive)` 失败 + 回滚 `os.replace(backup, archive)` 也失败」：

| 版本 | 对外异常 | 旧 zip 字节 | 残留 |
| --- | --- | --- | --- |
| 修复前（`4a4ce9a7`） | `OSError: rollback replace failed`（原始错误被掩盖） | `b"old"` | 无 |
| 修复后（`66540333`） | `OSError: first replace failed`（原始错误保留） | `b"old"` | 无 tmp / bak / lock |

代码证据：`tools/pack/zip_dist.py:253-261` —— 回滚动作整体包进 `try/except OSError`，`:259-260` 捕获后 `pass`，`:261` 无条件 `raise` 重抛原始 swap 异常。**m1 闭环**。

### 8.4 N2 / N3 是否闭环

- **N2（已闭环）**：`tests/test_pack_zip.py:423` 函数名已由 `fail_once` 改为 `fail_mkstemp`，与「无条件抛错」实现（`:424`）一致；`:426` monkeypatch 目标同步更新。命名不再暗示「只失败一次」。
- **N3（已闭环）**：职责已分离 —— 既有 `test_archive_stage_when_stage_empty_raises_zip_dist_error`（`:164-169`）只断言 `pytest.raises(ZipDistError, match="no files")`，锁断言已移除；新增 `test_archive_stage_when_stage_is_empty_releases_lock`（`:389-399`）专职覆盖「抛出后锁释放 + 补文件后重试成功」。两条用例不再逐字重复。

### 8.5 反向核查

| 核查面 | 结论 |
| --- | --- |
| `for temporary in (zip_tmp, sums_tmp, backup)` 可选 Path 循环 | `tools/pack/zip_dist.py:266-271`，三元组含三个可选变量，逐项 `is not None` 判空后 unlink，无漏项；`backup` 在回滚成功时被置 None（`:256`），finally 判空后跳过，正确 |
| 三处 `except OSError: pass` 的英文注释 | `:259`「a failed rollback must not hide the swap error」、`:270`「cleanup is best effort; keep the original error」、`:274`「a busy lock must not hide the original error」，均说明「不掩盖原始异常 / 不跳过删锁」，意图清晰 |
| 裸 `except:` / `except Exception` | 实测两文件均无；全部为具体 `except OSError` / `except FileExistsError` |
| `Path.unlink` monkeypatch 是否影响 pytest 自身 | 连跑 5 次全 32 passed；桩按 `self.suffix` 定向，实测 `.tmp` / `.bak` / `.lock` 后缀判定正确，`.lock` 不被误拦，未干扰 pytest 的 tmp_path 清理 |
| `Any` / `type: ignore` / 相对导入 / 非 ASCII 注释 | 实测：无 `typing.Any`（源码中 3 处 `Any` 均为英文散文）、无 `type: ignore`、无 `noqa`、无相对导入、两文件均含 `from __future__ import annotations` |

### 8.6 问题清单（按严重程度排序，含自我批判状态）

本节无 blocker、无 major。以下 3 条均为 minor。

#### [minor] N4 `os.close` 失败路径不在清理覆盖内，可致临时文件或锁残留

位置：`tools/pack/zip_dist.py:214`（`os.close(lock_fd)`，位于 try 之前）、`:227`（`os.close(fd)`，`zip_tmp` 到 `:229` 才赋值）、`:234`（`os.close(fd2)`，`sums_tmp` 到 `:236` 才赋值）。

描述：`mkstemp` / `os.open` 成功产出的 fd，若 `os.close` 抛 `OSError`，临时文件或锁已落盘但尚未登记到可选 Path 变量，`finally` 无从清理。实测三次定向注入 `os.close` 失败：

- 第 1 次（`:214` 锁 fd）：`files=[.yate-0.2.18-windows-x64.lock, ...]` —— **锁残留**，后果与 N1 相同（后续归档报 another archive is in progress）；
- 第 2 次（`:227` zip tmp fd）：`files=[.yate-0.2.18-windows-x64.360u2ky0.zip.tmp, ...]` —— zip tmp 残留，锁正常释放；
- 第 3 次（`:234` sums tmp fd）：`files=[.SHA256SUMS.6bm5lzwy.tmp, ...]` —— sums tmp 残留，锁正常释放。

影响评估：`os.close` 对刚成功打开的 fd 极少失败（`EBADF` 不可能；POSIX 上 `close` 可被 `EINTR` 中断且 CPython 不重试；Windows 上无 `EINTR` 语义，实际不可达）。因此触发条件比 N1 的「文件被外部进程占用」罕见得多，不构成常规重试失败路径；无数据丢失（旧 zip 完好，异常如实抛出）。

修复建议（可选，非阻塞）：把 fd 关闭写成 `try: os.close(fd) finally:` 或改用 `contextlib.closing(os.fdopen(fd, ...))`；或先赋值 Path 变量再 close，让 `finally` 至少能删除已落盘的空临时文件。

引用：`.trae/rules/python-coding-style.md` §4.5（资源清理纪律）；skill Error Handling 维度「Missing finally or with for resource cleanup」。

自我批判：初版曾想升为 major（后果与 N1 同型：锁残留 → 永久失败）。反证后维持 minor —— N1 判 major 的前提是「Windows 文件占用常见、常规重试即命中」，本条需 `close()` 系统调用失败，两者概率不在同一量级；且属存量设计形态 —— 父提交 `4a4ce9a7` 的 `:214` / `:221` / `:230` 同样是「先 close 后赋值」，非本轮 `66540333` 引入。确认保留 minor。

#### [minor] N5 三处 `except OSError: pass` 未记日志，偏离 §4.5「禁止静默吞异常」

位置：`tools/pack/zip_dist.py:259-260`、`:270-271`、`:274-275`。

描述：`.trae/rules/python-coding-style.md` §4.5 规定「`except` 块内至少记录日志或向用户反馈；禁止静默吞异常」，§6.1 进一步明确「silenced 只指显式捕获并记录」。三处 `pass` 均未记录日志，仅有注释说明意图。

反证与限定：静默在此处是**正确取舍** —— 记录日志本身可能抛错或改变异常链，反而违背「清理失败不得掩盖原始异常」的既定目标。因此本条不是功能缺陷，而是「规则字面 vs 实际必要性」的偏离，且注释已交代原因。

修复建议（可选）：`except OSError as exc:` 后用惰性 `%` 记录到 `logging`（`tools/` 下已有先例：`tools/pack/errors.py:23`、`tools/mdlint/lint.py:10` 直接 `import logging`），或保留 `pass` 并在 `.trae/rules/` 登记该场景为显式豁免。

自我批判：初版考虑删除（理由是注释已说明意图，且规则 §6.3 允许必要例外）。复核后保留为 minor —— 规则原文是「禁止 / 必须」，两个文件均适用于 `tools/`，属客观偏离；降级理由已写明「非功能缺陷、正确取舍」。确认保留 minor。

#### [minor] N6 `os.close` 三处失败路径无测试覆盖

位置：`tests/test_pack_zip.py` 全文（无 `os.close` 相关用例）。

描述：N4 暴露的三条路径（`:214` / `:227` / `:234` 的 close 失败）无用例钉住。与 N4 区别：N4 是代码形态，N6 是守卫空缺 —— 若将来有人把「先赋值再 close」改成「先 close 后赋值」的反向顺序，或用例外的清理方式，CI 不会报警。

修复建议：若采纳 N4 的「先赋值再 close」修复，补一条 `monkeypatch os.close` 抛 `OSError` 的用例，断言锁与临时文件不残留（与 N1 的两条用例同型）。

自我批判：与 N4 同根因，本可合并。独立登记的理由是「代码修复」与「补守卫」是两件事，分开便于跟踪；但若主代理认为合并更清晰，可并入 N4 一并处置，不强求。确认保留 minor。

### 8.7 第一轮 / 第二轮存量 minor 是否升级

| 条目 | 状态 | 本轮裁定 |
| --- | --- | --- |
| m1 回滚掩盖原始异常（第二轮降为 minor） | 已修 | 闭环（§8.3） |
| m3 symlink 用例为 monkeypatch 模拟 | 未改动 | 维持 minor；设计层/平台限制（Windows 建 symlink 需特权），按收敛判据登记待办、不升级 |
| m5 跨 stage 并发共享 SHA256SUMS.txt 丢更新 | 未改动 | 维持 minor；锁粒度仍为每 stage 一把（`:207`），打包脚本人工串行调用，无并发实证 |
| m6 陈旧锁无 PID/TTL 自愈 | 未改动 | 维持 minor；设计层缺口，需外部强杀才触发 |

### 8.8 强制自我批判登记（结论可追溯）

| 条目 | 初版定级 | 最终 | 状态 | 理由 |
| --- | --- | --- | --- | --- |
| N1 finally 内 unlink 无隔离 | major（上轮） | — | 确认闭环 | 三条注入路径锁均释放；修复前反证 `locks=[.lock]` → 修复后 `locks=[]` |
| m1 回滚掩盖原始异常 | minor（上轮） | — | 确认闭环 | 修复前抛 `rollback replace failed`，修复后抛 `first replace failed` |
| N2 `fail_once` 命名 | minor（上轮） | — | 确认闭环 | 已改 `fail_mkstemp`，与无条件抛错一致 |
| N3 空 stage 用例断言重复 | minor（上轮） | — | 确认闭环 | 既有用例只断言抛错，新用例专职锁释放与重试 |
| N4 `os.close` 失败致残留 | major → minor | minor | 降级保留 | 后果同 N1 但触发需 `close()` 失败，概率量级远低；存量形态非本轮引入 |
| N5 `except OSError: pass` 无日志 | minor | minor | 确认保留 | 属性正确取舍 vs 规则字面的偏离，非功能缺陷 |
| N6 `os.close` 路径无守卫 | minor | minor | 确认保留 | 与 N4 同根因但「修代码」与「补守卫」分列 |
| 三处 `except OSError` 注释是否充分 | minor | 删除 | 删除 | 三处注释均明确写出「不掩盖原始异常 / 不跳过删锁」，符合剧本对注释的要求，无实证不足 |
| `Path.unlink` 桩影响 pytest 自身 | minor | 删除 | 删除 | 连跑 5 次全绿，后缀定向正确，无失败实证，按剧本不留无依据断言 |
已删除 / 未报条目（避免无实证断言）：

- 「`except OSError` 三处注释不够充分」：逐条核对 `:259` / `:270` / `:274`，注释均显式覆盖「不掩盖原始异常」与「不跳过删锁」两个要点，删除。
- 「`Path.unlink` monkeypatch 全局作用面影响 pytest」：连跑 5 次全绿，`.lock` 不被后缀桩误拦，删除。
- 「`_write_archive` 整文件 `read_bytes()` 内存峰值」：前两轮已按 §6.1 判为无实测依据的预优化，本轮无 profiler 证据，不重提。
- 「`stage.is_dir()` 与 `resolve()` 之间的 TOCTOU」：构建脚本单进程人工调用，无外部并发改写 stage 的实证，不报。
- 「CALL4（`:244` bak fd close）残留」：实测 `raised=None`，因新目录无旧 zip、`archive.exists()` 为假未走 backup 分支，该路径未被触发，不成立，删除。

### 8.9 总体结论

- blocker：**0**
- major：**0**
- minor：**3**（N4 `os.close` 失败路径未纳入清理、N5 三处 `except OSError: pass` 未记日志、N6 `os.close` 路径无守卫用例）

#### N1 / m1 / N2 / N3 闭环结论

- **N1：已闭环。** `finally` 内三个临时文件 `unlink` 各自独立 `try/except OSError`（`tools/pack/zip_dist.py:266-271`），`lock_path.unlink` 独立包裹（`:272-275`）。独立探针实证：zip tmp / backup 的 `unlink` 抛 `PermissionError` 时 `locks=[]`；同时注入 swap 失败 + 清理失败时对外异常仍为原始业务异常且锁已释放；修复前版本反证锁残留。
- **m1：已闭环。** `:253-261` 回滚段包 `try/except OSError` 后无条件 `raise`；实证注入双失败时对外异常为 `first replace failed`（修复前为 `rollback replace failed`）。
- **N2：已闭环。** `tests/test_pack_zip.py:423` 已改名为 `fail_mkstemp`，与无条件抛错一致。
- **N3：已闭环。** `:164-169` 只断言抛错，`:389-399` 专职锁释放与重试成功，职责已分离。

#### 是否达到收门禁条件

**达到。** 0 blocker / 0 major；3 条 minor 均为平台限制或规则字面偏离类，不阻塞合入。八项实测命令退出码全 0（pyright 0 诊断、全量 pytest 全绿、架构 37 passed、panes 27 passed、diffcheck 无输出），新增两条用例经修复前版本反证确非空跑。

#### 无副作用的证据

- 产品源码 / 测试 / 脚本 / 计划文档零改动：`git status --porcelain` 输出为空（本会话曾误建一个工作树临时文件，已即时删除并复核为空）。
- 探针脚本、父版本源码导出与结果日志全部位于系统临时目录（仓库外）；探针在仓库外临时目录内构造 stage / dist 并自清理。
- 本会话唯一写入仓库的文件是本评审记录的本章节（追加，不覆盖既有内容）。

## 九、收尾门禁与闭环结论（主代理，2026-11-11）

- 三轮评审：第一轮 0 blocker / 1 major (M1) / 6 minor；第二轮 0 / 1 (N1) / 2；
  第三轮 **0 / 0 / 3**（N4/N5/N6），达到收门禁条件。M1（锁创建后 `try`
  覆盖不足）与 N1（`finally` 内 `unlink` 无异常隔离）均经独立探针反证
  修复后闭环；m1 / m2 / m4 / N2 / N3 同批闭环。
- 16 条登记 issue：F1–F14、F16 全部闭环；F15 裁定为合并时人工处置项
  （合并树 changelog 红、master 侧 0、`generate` 后转绿 0，处置路径已
  实测），不冒充已修复。
- 合并模拟（隔离临时 worktree，已按 git 安全协议移除）：架构 38 passed、
  全量 pytest 0、diffcheck 0；`tools.changelog generate` 后 check 0。
- 主代理收尾全量门禁：pyright 0 errors / pytest `-n auto` 0 / 架构 37 /
  覆盖率 92.93%（3514 passed·10 skipped，阈值 75）/ 冒烟 121/121·
  1464 checks / changelog 0 / diffcheck 0；第八项 `test_app_panes.py -n 1`
  用例全绿后被本机 `[safe-delete]` 钩子（count=10024 > 9999）杀收尾清理，
  单独重跑 RC=0，非产品缺陷、不记「偶发」。
- 遗留 minor（按 §二.6 登记待办、不阻塞）：m3 真实 symlink（Windows 权限）、
  m5 跨 stage 并发校验文件、m6 陈旧锁 PID/TTL 自愈、N4 `os.close` 失败
  路径（存量形态）、N5 清理异常未记日志（静默为正确取舍）、N6 close
  路径无守卫用例；F15 为合并时流程项。
- 评审索引登记 #75；工作树干净、未推送、未自动合流；推送 / 合入 master
  须用户显式要求。
