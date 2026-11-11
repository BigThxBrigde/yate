# 子计划 b：静态守卫、bat 启动提示、sh 脆弱点注释（wave-1）

> 路径基准同总纲。唯一规范来源：本文件 +
> `../pack-dist-zip-minor-fixes-plan.md` §2/§3 +
> `../pack-dist-zip-minor-fixes-issue.md` F2/F12/F13。

## 1. 输入与独占文件

- 现状取证：`tests/test_pack_spec.py:736-759`（`test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist`
  只断言 tail 内助手调用次数，未钉死相对顺序）；`pack/pack.bat:47-49`
  （`:run` 直接 `powershell -File` + `exit /b %ERRORLEVEL%`，启动期失败无提示）；
  `pack/pack.sh:28-31`（`show_help` 的 `sed -n '2,21p'`，评审裁定无需改动）。
- 只改这三个文件：`tests/test_pack_spec.py`、`pack/pack.bat`、`pack/pack.sh`。
  （`tools/`、`tests/test_pack_zip.py` 由 plan-a 独占；README 双语 / overview
  由 plan-c 独占。）

## 2. F2：静态守卫钉死归档顺序与块边界

在 `test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist()` 现有
断言之后追加（英文注释、ASCII）：

```python
assert ps1_tail.index("WaitForExit(30000)") < ps1_tail.index("tools.pack.zip_dist")
assert ps1_tail.index("Remove-Item $smokeOut") < ps1_tail.index("tools.pack.zip_dist")
assert ps1_tail.index("Collected ->") < ps1_tail.index("tools.pack.zip_dist")
assert sh_tail.index("timeout 30") < sh_tail.index("tools.pack.zip_dist")
assert sh_tail.index("Collected ->") < sh_tail.index("tools.pack.zip_dist")
```

再加块边界断言：助手调用必须位于 `--dist` 块的 `fi` / 闭合 `}` 之前——
用 `sh_tail.index("tools.pack.zip_dist") < sh_tail.index("\nfi")` 与
ps1 的 `ps1_tail.index("tools.pack.zip_dist") < ps1_tail.index("finally")`
（若当前脚本结构不同，按真实结构取最接近的闭合标记，并在报告说明）。
若字符串定位不稳，改用 `_after()` 已切出的 tail + 正则，不得削弱断言强度。
docstring 补充说明「smoke test / collected message precede the archive call
and the call stays inside the dist block」。

## 3. F12：bat 启动期失败可辨识提示

`pack/pack.bat`：
1. 头注释（`:2-16` 的 `rem` 块）补一句英文：
   `rem  A non-zero PowerShell exit code is reported on stderr before return.`
2. `:run` 保持 `powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %ARGS%`，
   在它与 `exit /b %ERRORLEVEL%` 之间插入一行：
   ```bat
   if errorlevel 1 echo error: pack.ps1 failed (check parameters and ExecutionPolicy) 1>&2
   ```
   - **不得**改 `exit /b %ERRORLEVEL%`（静态守卫断言目标）；
   - **不得**改四个既有映射、`--no-zip → -NoZip`、`SCRIPT` 预解析、
     尾反斜杠处理、`shift` / `goto parse`；
   - 用 `if errorlevel 1` 而非 `%ERRORLEVEL%` 比较，规避 cmd 的延迟展开问题。

## 4. F13：sh 硬编码区间显式化（按评审裁定不改行为）

`pack/pack.sh` 在 `show_help()` 上方（第 27-28 行之间、`set -euo pipefail`
之后）加一行英文注释：
```bash
# The 2,21p range is pinned by tests/test_pack_spec.py; keep both in sync.
```
- **不改** `sed -n '2,21p'`、头注释 usage 行、`case` 分支与 `--dist` 收集块；
- 注释位于头注释之后，不改变任何 usage 行号，静态守卫 §4 仍绿；
- 待办表状态由主代理在收尾统一改为「已闭环（守卫 + 负向演练 + 显式注释）」。

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
cmd /c pack\pack.bat --help
bash pack/pack.sh -h
```
前两条退出码 0；bat `--help` exit 0 且输出含 `-NoZip`；sh `-h` exit 0 且
含 `--no-zip` / `by default`。若 bash 不在 PATH，改用本机 Git Bash 可执行
文件（路径不写入文档），如实记录实测命令与结果；完全不可用时由静态守卫
覆盖并登记偏离。

**负向演练（推荐）**：临时把 sh 的 `2,21p` 改回 `2,19p`，确认
`test_help_text_when_scripts_scanned_covers_new_switch` 变红，再字节级还原；
同时临时删掉 bat 的 `if errorlevel 1` 行，确认新增守卫（若有）变红。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `index()` 断言因脚本结构差异抛 `ValueError` | 先读脚本真实结构；用 `_after` tail + 明确标记，失败信息带脚本名 | 调整标记，不删断言 |
| bat `echo ... 1>&2` 触发 cmd 解析异常 | `cmd /c pack\pack.bat --help` 与未知参数探针实测；不改退出码传递 | 删除该行 |
| sh 新增注释改变 usage 行号 | 注释放在 `set -euo pipefail` 之后、头注释之外 | 移动注释 |

回滚：`git revert` 本波提交；plan-a / plan-c 各自独立提交，互不影响。
