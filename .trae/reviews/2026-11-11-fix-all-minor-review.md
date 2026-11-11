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
