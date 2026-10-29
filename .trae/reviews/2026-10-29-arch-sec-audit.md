# arch-sec-audit wave-3 评审记录（code-review-expert）

> 来源方案：[arch-sec-audit-plans/overview.md](../documents/arch-sec-audit-plans/overview.md)
> （总纲 + plan-a~e）。处置结果见文末「处置结果」节（主代理收尾回填）。

- 评审范围：`git rev-list --count master..HEAD` = **10 笔**（任务书写 11 笔，实测 10）。
- 评审方式：只读（git diff/读文件），未改任何产品/文档/测试代码。
- skill：`use_skill("python-code-review")` 未注册（Skill 工具报 "not found"），按项目规则
  §1.3 直接读 `.trae/skills/python-code-review/SKILL.md` 作为评审框架（6 维度 + 三级）。

## 门禁实测（本机 Windows，worktree .venv）

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| pyright | `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| pytest 全量 | `pytest tests/ -q -n auto` | 全绿（无汇总行） | 0 |
| 架构 | `pytest tests/test_architecture.py -q` | 37 passed（与基线一致） | 0 |
| 覆盖率 | `pytest tests/ --cov=yate --cov-branch -n auto` | 3165 passed, 10 skipped, **92.24%**（基线 92.31），fail_under 75 通过 | 0 |
| 冒烟 | `python -m tools.smoke_test run --jobs 4` | 117/117 scenarios, 1407/1407 checks | 0 |
| 定向 | `pytest tests/test_yxp.py tests/test_theme_trust.py -q -rs` | 70 passed, **0 skip**（本机可建 symlink，新用例真实执行） | 0 |

改动文件未覆盖行（`coverage report --show-missing`）：
`logs.py:196-197,206-207`（POSIX-only chmod 分支，Windows 本机不可覆盖，POSIX CI 腿由
`test_logs_dirs_restrict_on_posix` 覆盖）；`theme_files.py:89-90,131`（既存 gap，非本次新增）；
`yxp.py` 新增行 380-385、443-447 均被覆盖。

## 结论清单（自我批判后终版，F1 已实证）

F1 实证：临时目录内构造 manifest 成员 `sub/x.py` + `ext/sub -> outside`（目录符号链接），
`yxp.install_package` **返回成功**，`outside/x.py` 内容 = 包内 payload（父目录链接写穿成立）。

## 结论清单（初版）

[major] yxp 符号链接卫语句只查叶子 → 父目录符号链接仍可写穿（yxp.py:443-451 / 20-22 / 531-544）
[minor] 主题文档三处与实现不符（themes.en.md:82,155,311-312；themes.zh.md:77,141,292-293）
[minor] theme_files.py:9-11 / theme.py:19-21 的 import 面自述已过时
[minor] logs.py:191-208 chmod 只落叶子目录，`~/.yate`、`~/.yate/data` 仍随 umask
[minor] yxp.py:380-385 无校验告警早于所有权校验（失败的安装也告警）
[minor] user_setup.py:86-88 仍自行拼 join，未用 yate_home()
[minor] theme_files.py:67-70 判定用 resolved cwd、加载用未 resolved 路径（与 loader.py:292-296 自述不变式相反）
[minor] test_theme_trust.py:58 否定断言口径过弱
[minor] overview.md:107 回填区仍为 [待回填]

## 已核查并排除（自我批判删除项）

- cli.py 新增 import：实测 diff 仅调用行（cli.py:410-413），零新增 import。
- editor_view → services.trust 非法跨层：规则依赖图已有 `EV --> LEAVES`（architecture-boundaries.md:82-102），services/* 在 LEAVES 内。
- ~~yxp 回滚不完整：`_extract_payload` 抛错后 `_rollback_files(extracted, previous)` 状态自洽；stale/record 尚未触碰。~~
  **（第 1 轮口径，已被第 2 轮 N1 推翻：修复把 stale 清理并入 try 后，多成员 stale 中途 abort 会丢已删内容，见下）**
- USER_DIRNAME 残留：yate/ tests/ tools/ pack/ 零命中；yate/ 内唯一 `.yate` 字面量是 paths.py:39。
- CI permissions 影响既有 job：YAML 解析 permissions={'contents':'read'}，jobs=test/smoke/lint 全部只读。
- tests/README 统计：实测 134 非 __init__、150 总 .py、36 有同名测试 → 98/134 与文本一致。
- Lua 文档声明：runtime.py:112 `lupa.lua54.LuaRuntime` 无 attribute_filter，stdlib 全开；api.app 存在（api.py:252）。
- tmp_path 未 resolve 导致 `dirs[0] == ws/"themes"` 失败：`_pytest/tmpdir.py:199` 已 resolve，且 CI 无 macOS 腿。

## 第 2 轮：迭代修复定向复核（2026-10-29）

范围：F1（yxp 父链 + 回滚）、F2/F3/F8。全量门禁按指示留给主代理。

- 代码状态：F2/F3/F8 已提交 `82bf6a7`（11 笔）；工作区未提交仅 `yate/services/yxp.py`、`tests/test_yxp.py`。
- 实测：定向 pyright（5 文件）0 诊断 exit 0；`pytest tests/test_yxp.py tests/test_theme_trust.py -q -rs` = 72 passed / 0 skip exit 0。
- 探针：A 顶层常规安装 ×2 成功（不过度收紧）；B 原 F1 写穿场景被拒（`outside/x.py` 未生成）→ **F1 原缺口闭合**；
  C 多成员 stale 中途撞链接 → 拒绝但 `a.py`/`b.py` 已被删且未还原、record 仍列三者 → **N1 实证**。
- 判定：F1 原 major 归零；本轮 major = 1（N1，修复新引入）、minor = 4（N2 uninstall/`_manifests` 未扫尾、
  N3 `_has_symlink_component` 同名不同义、N4 themes.en.md:165 / themes.zh.md:149-150 未加 `yaterc: ` 前缀、
  N5 themes.en.md:152-157 / themes.zh.md:142 优先级顺序被改反——`default_theme_dirs` 是 cwd 先 home 后，
  `register_theme` last-wins，实际 home 覆盖工作区）。
- N1 修法：`_remove_stale_files` 改两步式（先全量校验再删除）+ 补多成员 stale 用例。

## 第 3 轮：N1 放行复核（2026-10-29）

- 判定：**N1 归零**。探针 C：拒绝 + `a.py`=b'A'/`b.py`=b'B' 仍在 + record `['a.py','b.py','zz.py']` 与磁盘一致 + `d.py` 回滚 + 外部文件未动。
- N2 闭合：探针 D（uninstall 拒删穿链接，`keep.txt`/`x.py` 未动、record 保留）、探针 F（`_manifests` 为链接 → install 拒绝、目标目录为空）。
- N3 闭合：旧名仅存 `trust.py:39,88`（其自有函数）；yxp 内 6 处均为 `_resolves_through_symlink`。
- N4/N5 亦已修：`themes.en.md:156-158,166` / `themes.zh.md:142-143,150`（优先级顺序恢复为 `./themes` → home 且注明同名胜出；错误原文加 `yaterc: ` 前缀）。
- 实测：pyright（yxp.py+test_yxp.py）0 诊断 exit 0；`pytest tests/test_yxp.py tests/test_theme_trust.py -q -rs` = 74 passed / 0 skipped exit 0（5 条 symlink 用例真实执行）；`pytest tests/test_yxp.py --cov=yate.services.yxp --cov-branch` = 90.55%，Missing 含 `396`、`654`。
- 新发现（均 minor，不阻塞）：M1 两处 `_manifests` 链接守卫分支无用例覆盖（覆盖报告 Missing 396/654）；M2 `records.mkdir(exist_ok=True)` 先于 `records.is_symlink()`，悬空链接时报 "cannot prepare <ext_dir> ([WinError 183])"（指向错误对象）。
- major 计数：**0**。

## 处置结果（主代理收尾回填，2026-10-29）

- F1（major）→ 已修复（父链两阶段 stale 清理 + uninstall/records 入口守卫 + 回滚尽力而为告警跳过），N1（修复引入的升级路径状态丢失）经第二轮修复后探针 C 判定归零。
- 已修 minor：F2/F3/F8（迭代一）、N4/N5（迭代二）、M1/M2（迭代三，records 守卫用例补齐 + is_symlink 检查前移）。
- 登记待办（minor 不修，随下次修改逐步处置）：F4（logs chmod 只落叶子目录）、F5（无校验告警早于所有权校验）、F6（user_setup.default_base_dir 仍自拼 join）、F7（主题门控 resolved 不变式与 loader.py 表述不一致）、uninstall 中途 OSError 非原子（存量语义）、yxp.py:398-399 既有 OSError 分支缺口。
- 结构处置：yxp.py 830 行越线 → `SIZE_EXEMPT_FILES` 与规则 §三.7 同步登记豁免、拆分另行立项（提交 8d7d5eb）。
- 收尾门禁（主代理亲测，并行口径）：pyright 0 诊断 exit 0；pytest 全量 exit 0；架构 37 passed；覆盖率 **92.22%** exit 0（基线 92.31%，-0.09pp 为 POSIX-only chmod 分支与新增语句基数所致）；冒烟 117/117（1407 checks）exit 0；`tools.changelog check` exit 0。
