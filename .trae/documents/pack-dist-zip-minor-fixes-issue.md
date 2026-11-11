# 全量 minor 修复轮 —— issue 素材（【领会】整理稿）

用户指令（2026-11-11）：「更新记忆，fix 所有的isuee」。按无人值守上下文延续：
不询问、审批按通过处理、失败先落盘状态再续作。本文只整理全部登记 issue 的
原文要点、来源与验收判据，不产出方案；方案见 `pack-dist-zip-minor-fixes-plan.md`。

唯一规范来源：本文件 + `.trae/rules/` 8 份必读规则（本会话已全文加载）+
下列三份评审/计划文档。分支 `feature/feat-pack-dist-zip`，HEAD `a8db1324`
（16 笔提交），master `18e96d2a`，merge-base `b982c06`，工作树干净。

## 一、issue 去重总表（16 条）

来源缩写：`PR` = `.trae/reviews/2026-11-10-pr-review-feature-feat-pack-dist-zip.md`
§四 7 条 + §九 2 条；`R2` = `.trae/reviews/2026-11-10-pack-dist-zip.md` §7.4
N1–N5；`R1` = 同文件 m1/m7；`PLAN` = `pack-dist-zip-plan.md` §9 遗留。

| 编号 | 来源 | 位置 | 摘要 | 类别 |
| --- | --- | --- | --- | --- |
| F1 | PR#1 | `tools/pack/zip_dist.py:158` | 非 ASCII stage 名时 `encode("ascii")` 抛错，且 upsert 同名判断用 `errors="replace"` 解码永不匹配 | 代码 |
| F2 | PR#2 | `tests/test_pack_spec.py:746` | 归档分支守卫未钉死「冒烟之后 / `--dist` 块之内」的相对顺序与块边界 | 测试 |
| F3 | PR#3 | `tools/pack/zip_dist.py:68` | symlink 采用「跳过」，未写 `S_IFLNK` 条目，Linux 产物含合法链接时 zip 与 stage 目录树不一致 | 代码 |
| F4 | PR#4 | `tools/pack/zip_dist.py:184` | `mkstemp` 0600 临时文件直接 `os.replace`，POSIX 交付 zip / 校验文件仅属主可读写 | 代码 |
| F5 | PR#5 | `tools/pack/zip_dist.py:196` | 无锁 read-modify-write，两进程并发归档同一 dist 根可出现「zip 是 B、校验写 digest_A」 | 代码 |
| F6 | PR#8 | `tools/pack/zip_dist.py:196-197` | 两次 `os.replace` 之间失败留下「新 zip + 旧 SHA256SUMS.txt」；建议旧 zip 备份并回滚，或收窄 docstring 后事务化 + monkeypatch 用例 | 代码 |
| F7 | PR#9 | `tools/pack/zip_dist.py:178-179` | `--dist-root` 落在 stage 内时重跑把上次 zip 当普通文件再打进新包；入口拒绝 `dist_root.resolve().is_relative_to(root)` + 参数化用例 | 代码 |
| F8 | R2-N2 | `tests/test_pack_zip.py:74-82` | epoch 用例只断言目录条目，未断言文件条目 mtime 保真；若误把 `_write_archive:116` 也改 epoch 仍全绿 | 测试 |
| F9 | R2-N3 | `tools/pack/zip_dist.py:147-149` | 末列含全角空格等非 ASCII 字符的同名行不被替换，校验文件出现两行同名条目 | 代码 |
| F10 | R2-N4 | `.trae/documents/pack-dist-zip-plans/overview.md:102` | 偏离表退出码列「绑定失败 / 替代路径 0」把非零与 0 混填一格 | 文档 |
| F11 | R2-N5 | `README.md:315-319`、`README.zh.md:331-335` | 代码块示例注释列对齐被打乱（列位 50/50/49/49/46） | 文档 |
| F12 | R1-m1 | `pack/pack.bat:48-49` | bat 对 powershell 启动期失败（参数绑定、执行策略）无可辨识提示，cmd 里拿到 0 会误判成功 | 脚本 |
| F13 | R1-m7 | `pack/pack.sh:28-31` | `sed -n '2,21p'` 硬编码；评审裁定「守卫已充分，无需改动，仅记录为已知脆弱点」 | 已裁定 |
| F14 | PR#6 | 合并时 | 分支文档「架构 37」是 merge-base 时点事实；合并到 `18e96d2a` 后守卫 38，须在合并树上重跑门禁 | 流程 |
| F15 | PR#7 | 合并时 | `tools.changelog check` 分支侧与 master 侧均 0、PR diff 不含 CHANGELOG，按历史惯例仍列合并时人工确认 | 流程 |
| F16 | R2-N1 | `tests/test_app_panes.py:127-148`、`yate/editor_components/panes.py:139,214-220`、`view.py:177` | 存量确定性竞态：关闭 pane 后迟到 `on_focus` 命中已销毁 leaf，`leaf_by_id` 硬断言使应用崩溃；单文件 `-n 1` 连跑 4 次得 0,1,0,0，不得记「偶发」 | 存量产品 |

## 二、原文给出的修复路径（逐条）

- F1/F9：`_checksum_bytes` 改字节级 `os.fsencode` 比较，或 `decode("utf-8", errors="surrogateescape")` + `split()`；F1 亦可入口显式拒绝非 ASCII 名（二选一，方案须裁定）。
- F2：守卫加 `index("Remove-Item $smokeOut") < index("tools.pack.zip_dist")`（ps1）、`index("timeout 30") < index("zip_dist")`（sh）、tail 边界断言。
- F3：评审标「需产品决策」：写 `S_IFLNK` 条目（记录链接文本、不跟随）或跳过并显式文档化为契约。
- F4：`os.replace` 前 `chmod 0o644`（POSIX），补单测。
- F5：文档声明不支持并行，或加文件锁 / 旁置校验文件；补并发用例。
- F6：保留旧 zip 备份并回滚；或收窄 docstring `never touches` 措辞后另案事务化并补 monkeypatch 用例。
- F7：入口拒绝 `dist_root.resolve().is_relative_to(root)`（含相等），补参数化用例。
- F8：`os.utime` 固定源文件 mtime，断言 `file_info.date_time` 等于该常量。
- F10：拆成两行，或该格改「1（--dist 绑定）/ 0（-Dist 与 bat）」。
- F11：统一注释起始列，或去掉手工对齐。
- F12：bat 头注释补说明，或在 `:run` 前加 `-Help` 探针校验命令行；须保持 `exit /b %ERRORLEVEL%` 传递不变。
- F13：评审建议「无需改动（当前处置已达最优），仅记录为已知脆弱点」；负向演练已验证守卫变红。
- F14/F15：合并树上重跑门禁（架构 38）与 changelog；分支文档保留时点数字不改。
- F16：① 测试侧 close 后补 `await pilot.pause()` 或 wait_until 卸载谓词；② 产品侧 `notify_focus` 用 `find_leaf` 宽松判空、None 静默 return（`leaf_by_id` 保持 strict）；③ 补守卫用例「关闭 pane 后对已销毁 leaf 的 on_focus 不得抛」。

## 三、验收判据（每条必须可实测）

1. 代码类 F1–F9：pyright strict 0 诊断、全量 pytest 0、覆盖率 ≥75、新增用例覆盖成功/边界/失败注入，`tests/test_pack_zip.py` 与 `tests/test_pack_spec.py` 全绿。
2. F3 若选 symlink 条目：zip 内链接条目 `external_attr` 含 `S_IFLNK`、data 为链接文本且不含链接目标文件内容；越界链接仍不得读取目标。
3. F5/F6/F7：monkeypatch 注入（预置锁文件、第二次 `os.replace` 抛错、`dist_root` 落 stage 内）分别断言抛 `ZipDistError`、旧 zip 回滚/无残留 tmp、无异常产物。
4. F10/F11：文档 diff 可读、双语逐项对齐、`git diff --check` 0。
5. F12：`cmd /c pack\pack.bat --help` exit 0；不可绑定参数时 bat 给出可读 stderr 提示且退出码可被检查（不破坏既有映射守卫）。
6. F13：按评审裁定不新增行为改动，需把待办表状态更新为「已闭环（守卫 + 负向演练）」并给出依据。
7. F14/F15：合并模拟（隔离临时 worktree 或可逆 merge）实测架构 38、changelog 0、diffcheck 0，结果落盘；合并树验证后清理临时产物并显式记录。
8. F16：`pytest tests/test_app_panes.py -q -n 1` 连续多次全 0；新增守卫用例通过；`yate/editor_components/panes.py` 改动不破坏架构守卫（UI_FREE、ASCII 注释、行宽）。
9. 收尾：全量七项门禁（pyright / pytest -n auto / 架构 37 / 覆盖率 / 冒烟 / changelog / diffcheck）全 0；工作树干净；评审记录与方案回填；**记忆更新**（用户显式要求）。

## 四、非目标与约束

- 不改三脚本 `--dist` 既有语义、不加 `--zip` 正向开关、不改 PyInstaller spec / CI / release 工具；
- 不自动合并 master、不推送；F14/F15 的合并模拟须隔离且可逆；
- 不动 `leaf_by_id` 的严格断言（其它调用点依赖），F16 只在 `notify_focus` 处宽松判空；
- 不改历史评审记录里的时点事实数字（架构 37 等），只在回填章节登记合并后 38；
- 每步单独提交（全英文 `type(scope): subject`），只提交不推送、不自动合流。
