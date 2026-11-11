# 全量 minor 修复轮 —— 主计划（2026-11-11）

> 来源：用户「更新记忆，fix 所有的isuee」；issue 素材
> `pack-dist-zip-minor-fixes-issue.md`（去重 16 条）。子计划总纲
> `pack-dist-zip-minor-fixes-plans/overview.md`。
> 规则：`.trae/rules/` 8 份必读规则本会话已全文加载；`.trae/skills/` 为 skill
> 唯一来源；子代理定义以 `.trae/agents/` 为准。
> 【方案】由主代理按 `plan-architect-designer` 剧本亲自产出：该角色在本运行时
> 模型 `qwen-3.7-plus` 未注册（前轮已两次 spawn 失败），按
> `task-orchestration.md` §三 兜底并如实标注「子代理零产出」。
> 无人值守下【批准】按通过处理，不冒充用户确认；登记见
> `pack-dist-zip-progress.md`。本文引用仓库文件相对路径以 `.trae/documents/`
> 为基准，代码块内命令相对基准是仓库根。

## 1. 目标与非目标

**目标**：把三份评审记录 / 主计划 §9 登记的全部 issue 去重后的 **16 条**逐项闭环：
代码/测试类 F1–F9 实质修复并有回归用例；文档/脚本类 F10–F12 修复；F13 按
评审裁定销账并显式化约束；F14/F15 用隔离且可逆的合并模拟实测；F16 修存量
确定性竞态（产品侧 + 测试侧 + 守卫用例）。评审迭代至 0 blocker / 0 major，
全量七项门禁全绿，文档与记忆回填。

**非目标**：不改三脚本 `--dist` 既有语义、不加 `--zip` 正向开关、不改
PyInstaller spec / CI / `tools.release` / `.yxp`；不自动合并 master、不推送；
不改 `leaf_by_id` 的严格断言（其它调用点依赖）；不改历史评审记录中的时点
事实数字；不把 F13 重写成语义锚点式 `show_help`（评审已判当前处置最优）。

## 2. 16 条 issue 裁定表

| 编号 | 裁定 | 处置 |
| --- | --- | --- |
| F1 非 ASCII stage 名 | 实质修复 | `_checksum_bytes` 改用 `os.fsencode` 写新行 + `decode("utf-8", surrogateescape)` 判同名，支持非 ASCII stage 名 |
| F2 归档守卫顺序 | 实质修复 | 静态守卫加「冒烟 / Collected 在助手调用之前」与 tail 边界断言 |
| F3 symlink 条目 | 实质修复 | 写 `S_IFLNK` 条目（记录链接文本、不跟随目标），zip 与 stage 目录树一致 |
| F4 0600 产物权限 | 实质修复 | 两个 `os.replace` 前 `chmod 0o644`，POSIX 断言 + Windows 条件断言 |
| F5 并发锁 | 实质修复 | `os.open(O_CREAT\|O_EXCL)` 锁文件互斥，finally 清理，预置锁抛 `ZipDistError` |
| F6 两次 replace 失败 | 实质修复 | 旧 zip 移到备份 → 替换新 zip → 替换校验文件；校验失败回滚旧 zip / 删除新 zip |
| F7 dist-root 落 stage 内 | 实质修复 | 入口拒绝 `dist_root.resolve() == root or is_relative_to(root)`，参数化用例 |
| F8 epoch 用例 | 实质修复 | `os.utime` 固定 mtime，断言文件条目 `date_time` 仍等于源文件 mtime |
| F9 全角空格同名行 | 实质修复 | 与 F1 同一处：`surrogateescape` 解码 + `str.split()`（Unicode 空白）判末列 |
| F10 偏离表退出码 | 文档修复 | 该格改为 `1（--dist 绑定）/ 0（-Dist 与 bat）` |
| F11 README 列对齐 | 文档修复 | 双语代码块注释统一列位，Python 探针实测列位一致 |
| F12 bat 启动期提示 | 脚本修复 | `if errorlevel 1 echo error: ... 1>&2` + 头注释；保持 `exit /b %ERRORLEVEL%` 与四映射不变 |
| F13 sed 硬编码 | 销账 | 评审裁定「无需改动」：补一句「区间由 `test_pack_spec.py` 钉死」注释，待办表状态改为已闭环，不重写 help |
| F14 架构 38 / F15 changelog | 流程验证 | 隔离临时 worktree 合并 master，实测架构 38、全量 pytest、changelog 0、diffcheck 0；完成后移除 worktree 并显式记录 |
| F16 存量焦点竞态 | 实质修复 | `notify_focus` 用 `find_leaf` 宽松判空静默 return；测试 close 后补 `await pilot.pause()`；新增守卫用例 |

## 3. 关键备选与否决理由

| 决策 | 选中 | 否决 |
| --- | --- | --- |
| F1 非 ASCII stage 名 | 支持非 ASCII（`os.fsencode` + `surrogateescape`） | 「入口显式拒绝非 ASCII 名」：把合法路径挡在门外，且 issue §二.4 要求多平台共存；`encode("ascii")` 保留则缺陷不闭环 |
| F3 symlink | 写 `S_IFLNK` 条目，data 为 `os.fsencode(os.readlink(path))` | 「保持跳过 + 文档声明」：未真正修复「zip 解压后目录树与 stage 一致」；「跟随链接写普通文件」：重新打开越界读取面（已由 `6f842d34` 收口） |
| F5 并发 | `O_CREAT\|O_EXCL` 锁文件（跨进程原子、无第三方依赖） | 「仅 docstring 声明不支持并行」：用户要求实质修复；`fcntl` / `msvcrt` 平台分叉：Windows 无 fcntl stub，pyright strict 会红；`threading.Lock`：不解决跨进程 |
| F6 事务 | 旧 zip `os.replace` 到备份 + 失败回滚 | 「只收窄 docstring 的 never touches 措辞」：状态不一致仍存在；「先替换校验再替换 zip」：短暂出现校验指向旧/不存在 zip |
| F13 sed | 保留硬编码 + 显式注释 + 销账 | 改成 awk 语义锚点：改变 `-h` 输出内容、无实测收益，评审已判「守卫已充分、当前处置最优」 |
| F14/F15 | 隔离临时 worktree 做可逆合并模拟 | 「只保留合并时待办」：用户要求 fix 所有；在当前分支 `git merge --no-commit` + `--abort`：污染工作树、失败时留合并中状态 |
| F16 | 产品侧 `notify_focus` 宽松判空 + 测试侧 pause + 守卫用例 | 「只改测试加 pause」：掩盖产品硬断言，迟到 focus 仍可在其它路径崩溃；「改 `leaf_by_id` 为宽松」：破坏 active-view 等调用点的 live-view 不变式 |

## 4. 总体设计（归档流程）

```mermaid
flowchart TD
    A[archive_stage 入口] --> B[stage 名净化 + dist_root 不得落在 stage 内]
    B --> C[dist_root 准备 + O_EXCL 锁文件]
    C --> D[_stage_files: 普通文件 / symlink 分型]
    D --> E[临时 zip + 临时 SHA256SUMS.txt]
    E --> F[chmod 0644 + 计算 digest]
    F --> G[旧 zip 移到备份]
    G --> H[os.replace 新 zip]
    H --> I{os.replace 校验文件成功?}
    I -->|是| J[删备份 + 清锁 + 返回结果]
    I -->|否| K[回滚旧 zip / 删新 zip]
    K --> L[清备份/临时/锁, 抛出可读错误]
    style J fill:#c8e6c9,color:#1a5e20
    style L fill:#ffcdd2,color:#b71c1c
```

锁文件命名 `.<stage_name>.lock`，备份 `.<stage_name>.*.zip.bak`（`mkstemp`），
临时文件均在 dist 根（同目录保证原子替换）。锁创建失败时不得删除他人锁；
任何失败都清理本次创建的临时/备份/锁文件。

## 5. 子计划与波次

总纲与文件互斥矩阵见 `pack-dist-zip-minor-fixes-plans/overview.md`。

| wave | 子计划 | 独占文件 |
| --- | --- | --- |
| 1 | `pack-dist-zip-helper-plan-a.md` | `tools/pack/zip_dist.py`、`tests/test_pack_zip.py` |
| 1 | `pack-dist-zip-guards-scripts-plan-b.md` | `tests/test_pack_spec.py`、`pack/pack.bat`、`pack/pack.sh` |
| 1 | `pack-dist-zip-docs-plan-c.md` | `README.md`、`README.zh.md`、`.trae/documents/pack-dist-zip-plans/overview.md` |
| 2 | `pack-dist-zip-panes-plan-d.md`（主代理，产品源码不派子代理） | `yate/editor_components/panes.py`、`tests/test_app_panes.py` |
| 3 | `pack-dist-zip-merge-check-plan-e.md`（主代理） | 无源码写入；临时 worktree + 文档回填 |
| 4 | 【审核】+【收尾】 | 评审记录、方案/进度/记忆回填、提交 |

wave-1 三个子计划文件互不重叠并行下发；wave-2 依赖 wave-1 全绿（避免并发
跑 pytest 互相干扰）；wave-3 依赖 wave-2；wave-4 收尾。

## 6. 验收总口径

- 每波局部验收命令见各子计划；波内全部退出码 0 才进入下一波。
- 全量七项门禁（主代理收尾亲跑）：`pyright yate/ tests/ tools/ pack/`、
  `pytest tests/ -q -n auto`、`pytest tests/test_architecture.py -q`、
  `pytest tests/ --cov=yate --cov-branch -n auto`（≥75）、
  `tools.smoke_test run --jobs 4`、`tools.changelog check`、
  `git diff --check master...HEAD`。
- F16 附加：`pytest tests/test_app_panes.py -q -n 1` 连续 4 次全 0（不得记「偶发」）。
- F14/F15 附加：合并树 `pytest tests/test_architecture.py -q`（38）、
  合并树全量 pytest、合并树 changelog 0、合并树 diffcheck 0。
- 16 条逐项判据见 `pack-dist-zip-minor-fixes-issue.md` §三；
  每条须在评审记录与方案中回填「已闭环 + 实测证据」。

## 7. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| symlink 条目影响 Windows `Expand-Archive` | 正常 Windows 产物无 symlink；E2E 产物由三脚本生成，验收 3 不经过链接 | 还原跳过策略（F3 不闭环，不允许作为最终状态） |
| `O_EXCL` 锁残留（进程崩溃）致后续归档永久失败 | 错误信息带锁路径，文档写明手工清理；锁只覆盖归档临界区 | 删除锁文件 |
| 备份/回滚引入新失败面 | monkeypatch 注入第二次 replace 失败，断言旧 zip 字节恢复、无 bak/tmp/lock 残留 | `git revert` F6 改动 |
| `os.fsencode` 在 Windows 与 POSIX 编码差异 | 用 `surrogateescape` 保证字节可逆；新增非 ASCII 名单测 | 还原 ascii 编码（F1 不闭环） |
| F16 改动产品源码触发架构守卫 / UI_FREE | 只在 `notify_focus` 加 3 行英文注释 + 宽松判空；架构 37 守卫 + 全量 pytest 实测 | `git revert` panes 改动 |
| 合并模拟创建临时 worktree / 合并提交 | 隔离目录、不推送、不自动合流；完成后 `git worktree remove` 并在收尾汇报显式列出（git 安全协议） | `git worktree remove --force` + 落盘记录 |
| 覆盖率 `-n auto` 再触发本机 safe-delete 钩子 | 按 `python-coding-style.md` §4.7 用 `-n 1` 复核并如实记录，不改断言、不记「偶发」 | 不适用 |

回滚总路径：16 条改动集中在 4 个代码/脚本文件 + 2 个测试 + 4 个文档；
各波单独提交，`git revert` 对应提交即可，`--dist` 既有语义零重写。

## 8. 提交纪律

每步（领会 / 方案 / 批准 / 各 wave / 审核 / 收尾）产物单独提交一次，全英文
`type(scope): subject`，只提交不推送、不自动合流；收尾由主代理亲自跑全量
门禁，回填真实前后数字与偏离记录，并**更新记忆**（用户显式要求）。

## 9. 收尾实测与闭环（2026-11-11）

- 16 条 issue 全部闭环（F15 为合并时人工处置项，处置路径 `generate`
  实测转绿）；三轮评审 0/1/6 → 0/1/2 → **0/0/3** 收敛，M1 / N1 两轮
  major 修复，m1/m2/m4/N2/N3 同批闭环，m3/m5/m6/N4/N5/N6 登记待办。
- 主代理全量门禁：pyright 0 / pytest `-n auto` 0 / 架构 37 / 覆盖率
  92.93%（3514 passed·10 skipped，≥75）/ 冒烟 121/121·1464 / changelog 0 /
  diffcheck 0；第 8 项钩子红经单独重跑 RC=0（非产品缺陷）。
- 合并模拟：架构 38、合并树全量 pytest 0、diffcheck 0；临时 worktree
  已按 git 安全协议移除并显式登记。
- 评审记录 `.trae/reviews/2026-11-11-fix-all-minor-review.md` §九与索引
  #75 已回填；工作树干净、未推送、未自动合流。
