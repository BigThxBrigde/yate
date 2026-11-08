# 2026-11-08 IKTF4Y trust 修复复审（r2，收窄粒度）

- Reviewer: code-review-expert；Skill 工具返回 python-code-review not found，按角色文件回退步骤执行（与首轮先例一致）。已执行强制自我批判。
- 范围：aa72147..HEAD 中仅 f526733 （trust store 写侧拒绝＋ bridges docstring + 4 份双语图档 + test_trust 新用例）与 323d3b6（记录类）。不审 24f3ba4 的 Lua argv / shell 模块。
- 实测范围文件：yate/services/trust.py, tests/test_trust.py, yate/services/extensions/bridges.py, yate/docs/extensions.en.md, extensions.zh.md, yate/resources/manual.en.md, manual.zh.md。
- 结论：APPROVE — 新增 0 blocker / 0 major / 2 minor；首轮 major 归零（1/1 已闭合），首轮 minor #3 已修。

## 1. 实跑命令与退出码（本次评审自跑，非引用他人数字）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `pyright yate/services/trust.py yate/services/extensions/bridges.py tests/test_trust.py` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/test_trust.py -v -n 1 --no-header -rA` | 10 passed, 1 skipped（跳过项为 test_trust.py:94 POSIX 权限位） | 0 |
| `pytest tests/test_trust.py tests/test_extension_flows.py tests/test_extension_bridges.py tests/test_theme_trust.py -q -n 1` | 全绿（含 1 skip） | 0 |
| `pytest tests/test_architecture.py -q -n 0` | 37 passed | 0 |
| `python -m tools.mdlint --auto-lang --check <改动文档>` | check: 146 violation(s) in 4 files，均为存量，无新增行命中 | 0 |

- 全量六道门禁由主代理亲跑（pyright 0 / 3468 passed´10 skipped / 架构 37 / 覆盖率 92.94% / 冒烟 121·1464 / changelog 0），按指示未重跑。
- mdlint 本次检出 146 条均为存量（MD040 / MD013 / MD038 / YM003 / MD004），新增行未命中；退出码 0，与主代理“父提交基线归一化差异 0”的结论一致。

## 2. 逐条复核结论（对应任务书 5 问）

### Q1 写侧守卫位置 / 对称性 / :trust 反馈 —— 守卫本身合格，反馈文案有一处新失真（见 minor #1）

- 守卫位置合格：trust.py:122-124 的 if store.is_symlink(): log.warning(...); return False 位于 store = TRUST_FILE if path is None else path（:121）之后，且在 _has_symlink_component（:125）、root.resolve()（:132）、load_trusted_workspaces（:133）、store.parent.mkdir（:142）、store.open("a")（:145）全部之前，返回 False，且 log.warning 可见（:123）
- 对称性成立：读侧 trust.py:84-86 为同一 store.is_symlink() 条件 + return set()；写侧 :122-124 为同一条件 + return False。两侧用词亦对称（refusing to read symlinked trust store / refusing to write symlinked trust store）。
- 实测探针（退出码 0）：link.is_symlink=True，trust_workspace(root, link)=False，is_trusted(root, link)=False，target_lines 仍为单行且仅含 repo 路径——零写副作用成立。
- 边界：悬空符号链接 store（os.symlink 指向不存在目标）实测 is_symlink()=True → 写侧 False、读侧 set()，两侧同样对称拒绝。
- 日志捕获实测（pytest -rA captured log）：trust.py:123 refusing to write symlinked trust store 与 trust.py:85 refusing to read 均于实际出现。
- :trust 反馈链路：extension_flows.py:79 的 if not trust_workspace(cwd): 分支确实会因 False 触发（不再说报成功，首轮 major #2 的核心症状已消除），但文案把原因写死为 cwd 含符号链接（:84）——见 minor #1。

### Q2 新用例真实性 / 既有用例无回归 —— 合格

- tests/test_trust.py:182-208 test_trust_workspace_refuses_symlinked_store：-rA 实测为 PASSED，非 SKIPPED；-rA 的 captured log 含 trust.py:123 refusing to write symlinked trust store … linked_store，证明 link.symlink_to(real)（:197）真创建成功、未走 :198-199 的 skip 分支。
- 零写副作用有实证断言：:206 assert real.read_text(...).splitlines() == [str(root.resolve())]——若写侧未拒绝，append 会追加第二行使断言失败；配合 :202 的 is False 与 :208 的 is_trusted(...) is False。
- 既有 4 个 trust 用例全部 PASSED：test_missing_store_yields_no_trusted_workspaces、test_trust_workspace_roundtrip、test_trust_workspace_is_idempotent、test_symlinked_trust_store_is_refused，无回归。test_trust.py 共 10 passed / 1 skipped（跳过项为 :94 的 POSIX 权限位用例）。

### Q3 docstring 与 4 份双语文档 —— 合格

- 模块 docstring trust.py:14-18：明确 Both sides refuse a trust store that is itself a symbolic link，分别点名 load_trusted_workspaces → 空集、trust_workspace → False，各自告警；同时保留 A symlinked *parent* directory is unaffected -- that is a common home-directory layout。与实现（:84-86 / :122-124）逐字对应。
- 函数 docstring trust.py:111-112 补 Returning False also covers a store file that is itself a symbolic link (refused symmetrically with the read side)，与 Returns True/False 语义（:105-107）自洽。
- 4 份文档成对且措辞与实现一致：extensions.en.md:162-164（ignored on read and refused on write, :trust reports the refusal）↔ extensions.zh.md:141-142（读取侧会忽略、写入侧会拒绝（:trust 会报告该拒绝））；manual.en.md:1000-1001（refused on both the read and write sides）↔ manual.zh.md:909-910（读写两侧均拒绝）。
- 无本机绝对路径：4 份文档对 [A-Za-z]:\\ 、/home/、/Users/ 的匹配为空。
- 未过度承诺：ACL 仅以 Windows 尚未应用 ACL 加固（另案跟踪）的限制形式出现（extensions.en.md:165 / extensions.zh.md:143-144）；fingerprint 的命中是 manual.en.md:998 的 does not fingerprint，为否定式声明，符合实现。

### Q4 bridges.py docstring 与零行为变更 —— 合格

- bridges.py:466-472 同时保留了原子写说明（every write is atomic, temporary sibling file then replace）与新增的真实路径校验说明（symlinks including intermediate directories that resolve outside the data root are refused），并保留原有失败降级契约（None / False / []）。
- 行为零变更已实测：git diff aa72147..HEAD -- yate/services/extensions/bridges.py 的 +/- 行全部落在 :466-472 的 docstring 内，无一行触及 read（:475-481）/write（:483-490）/remove（:492-498）/list（:500-506）函数体。
- docstring 与实现相符：真实路径校验确在 yate/services/data_store.py:38-42 _assert_inside_data_root（比较 target.resolve() 与 data_root().resolve()），并由 resolve（:86）、write_text mkdir 后（:122）、remove unlink 前（:143）三处调用，故 including intermediate directories（Path.resolve() 解析每个分量）成立；read_text 亦经 :97 的 resolve 路径。

### Q5 新引入问题 / 首轮归零 —— 无新 blocker / major

- pyright 局部 0/0/0；新增 Python 行非 ASCII 字符计数为 0（git diff 加法行扫描，脚本退出码 0）；日志均为惰性 %s（trust.py:123 / :85）；架构守卫 37 passed；4 份文档无新增 mdlint 违规。
- 首轮 major 归零：首轮 [major] 2（trust.py:83-85 读侧空集 vs trust_workspace 追加后返回 True 的不对称）已由 trust.py:122-124 闭合，实测写侧拒绝——1/1 major 已修。
- 首轮 minor #3（bridges.py docstring 漂移）已修，见 Q4。首轮 blocker #1 属 Lua 范畴，不在本次复审范围。
- 两笔提交信息均为英文 conventional-commit 标题且带正文（git log -1 --format=%B 实测），符合 .trae/rules/git-commit-message.md。


## 3. 新发现（按严重级排序）

### [minor] 1 - :trust 拒绝 store 符号链接时给出错误的失败原因

- 位置：yate/flows/extension_flows.py:79-88（本提交未改动该文件，但 f526733 新增了第二个 False 来源，使其文案失真）。
- 证据：trust_workspace 在 f526733 前只有「root 含符号链接分量」一条 return False 路径（trust.py:125-131），故 :84 的 it contains a symlink component; trust the resolved directory instead 当时准确。新增 store.is_symlink() 分支（trust.py:122-124）后出现第二条 False 路径，extension_flows.py 仍把全部 False 归因于 cwd。
- 实测探针（退出码 0）：构造链接 store 后 trust._has_symlink_component(root)=False 而 trust_workspace(root, link)=False，此时 flows 会输出 refused to trust <repo>: it contains a symlink component; trust the resolved directory instead——cwd 明明不含链接，用户按提示重试必然再次失败。
- 触发条件：默认 store（path=None）本身为符号链接，即 dotfiles 用户把 ~/.yate/trusted_workspaces 软链进仓库的常见布局，正是首轮 major #2 描述的场景。
- 影响面：仅错误文案，fail-closed 行为正确，不构成功能/安全缺陷，故定为 minor 而非 major。
- 修复建议：让 trust_workspace 的失败原因可区分（返回枚举/结果对象，或在 extension_flows 中前置 store.is_symlink() 检查给出专门文案），并在 tests/test_extension_flows.py 补一条 store-为链接 的用例；该文件不在本次允许改动范围，建议登记为后续 minor。

### [minor] 2 - extensions.zh.md 第 144-145 行断行生硬

- 位置：yate/docs/extensions.zh.md:144-145。
- 证据：:144 结尾为「Lua 扩展适用同一」、:145 起为「信任级别——见下文第 6 节」，把「同一信任级别」这一词组从中间拆开；同段 :142-143 的其余断行均未拆分词组。属 f526733 重排该段时引入。
- 影响：仅排版可读性，语义无歧义，md lint 未命中。
- 修复建议：把换行移到「同一」之前或「信任级别」之后。

## 4. 强制自我批判记录

| # | 初版候选 | 状态 | 依据 |
|---|---|---|---|
| 1 | :trust 失败文案失真（store 链接被误报为 cwd 含链接） | 确认保留（minor） | 回读 extension_flows.py:79-88 与 trust.py:122-124 两次；实测探针锁定 _has_symlink_component(root)=False 与 trust_workspace=False 的组合真实可达。未升级为 major：行为 fail-closed 正确，用户仍被拒绝且未获虚假信任，只是原因文案错误。 |
| 2 | extensions.zh.md 断行生硬 | 确认保留（minor） | 逐行读取 :144-145 核对；不涉及语义，维持 minor。 |
| 3 | 候选：写侧守卫与读侧不完全对称（守卫不在同一函数内） | 删除 | 位置差异是实现自然结果（trust_workspace 需先解析 store），两侧条件与返回语义完全一致；刷新 is_trusted 经读侧继承该拒绝。凭「守卫不在同一函数」报问题属无实证挑剔。 |
| 4 | 候选：拒绝 store 链接会破坏 dotfiles 用户既有信任 | 删除 | 该策略是首轮 major #2 的既定裁决（读侧已先拒绝，写侧对齐），且文档已明示；不是缺陷而是设计取舍。 |
| 5 | 候选：bridges docstring 称 real-path validation lives in the same module 但实际在 data_store | 删除 | the same module 指的是 yate.services.data_store（:465 上一句已点名），语义正确。 |
| 6 | 候选：新用例未断言 store 本身未被创建 | 删除 | 该用例传的是已存在的 real 及其链接，store.parent 已存在；「不创建」由 test_trust_refuses_a_symlinked_root:59 覆盖，重复断言无增量。 |
| 7 | 候选：manual.en.md 与上句间缺空行导致段落粘连 | 删除 | 原文为同一段落内的续句，换行属该文件既有排版，md lint MD013 未新增命中。 |

反向漏报自查：正确性（写侧拒绝正确、读侧不变）、边界条件（悬空链接实测对称）、异常处理（is_symlink() 不抛异常，OSError 仍由既有分支处理）、并发安全（未新增共享可变状态，守卫为纯读取）、性能（is_symlink() 为一次 lstat，非热路径）、类型（pyright 0）、测试覆盖（新增分支被新用例覆盖，captured log 证明走了 trust.py:123）——未见遗漏。

## 5. 裁决

**APPROVE**：新增 0 blocker / 0 major / 2 minor。首轮 major 1/1 归零，首轮 minor #3 已修。2 条 minor 均非阻塞（一条为跨文件文案精化、一条为断行排版），可另行登记。

> 说明：本记录为只读事实文档，未修改任何产品代码 / 测试 / 其它评审记录 / README.md 索引，未提交。
