# 子计划 b：`tests/test_pack_spec.py` 静态守卫（wave-3）

> 路径以本文件所在目录为基准：`../../../tests/test_pack_spec.py` 即仓库根
> `tests/test_pack_spec.py`。唯一规范来源：本文件 +
> `../pack-dist-zip-plan.md` §6 验收映射 + `overview.md` 波次表。
> 前置：wave-2 三个脚本已落盘（守卫断言的是它们的最终形态）。

## 1. 输入

- 现状：`../../../tests/test_pack_spec.py:30-58` 已有 `_REPO_ROOT`、
  `_COMMON_PATH` / `_ONEFOLDER_SPEC` / `_ONEFILE_SPEC` / `_SPECS` 常量与
  `_parse()`（`ast.parse`，lru_cache）等辅助；`:428-443` 已有「扫描若干脚本文本」
  形态的参数化守卫（`_EXTRA_HINT_FILES`）；全文件 685 行，无任何 zip / `--dist`
  断言。
- issue 验收 6 要求：三个脚本均声明 / 映射新开关、默认值为生成 zip、
  `--no-zip` 分支跳过压缩、`pack.sh` 帮助行区间覆盖新增 usage、
  `--dist` 与冒烟语义不回归。

## 2. 独占文件清单

只改 `../../../tests/test_pack_spec.py`。**不得**改三个脚本 / 助手 /
`tests/test_pack_zip.py` / 文档。只读引用 `../../../tools/pack/zip_dist.py`
是允许的（静态断言读取），但不写入。

## 3. 具体修改（新增常量、辅助与用例）

在文件末尾追加一个新章节（英文注释与 docstring，`from __future__ import
annotations` 等文件头不动），新增：

```python
#: The three build scripts whose --no-zip contract is pinned here.
_PS1_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.ps1"
_SH_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.sh"
_BAT_SCRIPT: Path = _REPO_ROOT / "pack" / "pack.bat"
```

辅助 `_script_text(path: Path) -> str`（`read_text(encoding="utf-8")`）与
`_after(text: str, marker: str) -> str`（断言 marker 恰出现一次后返回其后文本，
失败信息带文件名；风格对齐既有 `_one_call()` 的「断言而非 next()」约定）。

### 用例（名称 / arrange / act / assert 三要素）

1. `test_no_zip_switch_when_scripts_parsed_is_declared_and_mapped_in_all_three`
   - arrange：读三个脚本全文。
   - act：逐项文本断言。
   - assert：ps1 含 `[switch]$NoZip`、`.PARAMETER NoZip`、`--no-zip` 包装拼写、
     `by default`；sh 含 `--no-zip)`、`no_zip=0`、`no_zip=1`；bat 含
     `if /i "%arg%"=="--no-zip" set "arg=-NoZip"`；三者都含 `zip`。
2. `test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist`
   - arrange：ps1 / sh 全文。
   - act：`ps1_tail = _after(ps1, 'if ($Dist -ne "")')`；
     `sh_tail = _after(sh, 'if [ -n "$dist_arg" ]; then')`。
   - assert：`tools.pack.zip_dist` 在两个 tail 中各恰出现 1 次，在 tail 之前的
     文本中 0 次；ps1 tail 含 `if ($NoZip)`、sh tail 含
     `if [ "$no_zip" -eq 1 ]; then`；两处默认分支都调用助手（即「不传开关 = 生成 zip」）。
3. `test_no_zip_when_requested_skips_archive_without_touching_existing_files`
   - arrange：切出 ps1 的 `if ($NoZip) { ... } else` 跳过分支文本与 sh 的
     `if [ "$no_zip" -eq 1 ]; then ... else` 跳过分支文本。
   - act：文本断言。
   - assert：两分支都含「skipped」提示文本；都不含 `Remove-Item` / `rm -rf` /
     `Set-Content` / `SHA256SUMS.txt` / `zip_dist`；助手调用只出现在 `else` 部分。
4. `test_help_text_when_scripts_scanned_covers_new_switch`
   - arrange：sh / ps1 / bat 全文；用
     `re.search(r"sed -n '2,(\d+)p'", sh)` 取 help 区间终点 N。
   - act：枚举 sh 头注释前 40 行（行号从 1 起），收集所有
     `#   ./pack/pack.sh` usage 行、所有含 `--no-zip` 的行、所有含
     `by default` 的行。
   - assert：`match is not None`；`max(usage_lines) <= N`；
     `max(no_zip_lines) <= N`；`max(default_lines) <= N`；
     `sed -n '2,19p'` 已从全文消失（防旧区间回退）；
     ps1 含 `.PARAMETER NoZip` 与 `by default`；
     bat 头注释含 `--no-zip` 与 zip 默认说明。
5. `test_unknown_arguments_when_sh_parsed_still_exit_two`
   - arrange：sh 全文。
   - act：定位 `*)` 分支文本（从 `*)` 到 `;;`）。
   - assert：分支含 `unknown argument` 与 `exit 2`；全文不含 `--zip)` 或
     `--zip=` 正向 / 带值开关（issue 否决形态）。
6. `test_dist_and_smoke_semantics_when_scripts_scanned_are_unchanged`
   - arrange：ps1 / sh 全文。
   - act：文本断言（参数化两个脚本各自的固定清单）。
   - assert：ps1 仍含 `WaitForExit(30000)`、`SHA256SUMS.txt`、
     `Remove-Item $smokeOut`、`Collected ->`、`yate-$version-windows-$arch`、
     `Set-Content -Encoding ascii`；sh 仍含 `timeout 30`、
     `sha256sum yate > SHA256SUMS.txt`、`chmod 0755`、
     `yate-$version-linux-$arch`、`Collected ->`、`cp -a`。
7. `test_bat_wrapper_when_mapping_scanned_keeps_existing_mappings`
   - arrange：bat 全文。
   - act：文本断言。
   - assert：`--onefile` / `--skip-changelog` / `--dist` / `--help` 四个既有映射、
     `set "SCRIPT=%~dp0pack.ps1"`、尾反斜杠双写 `set "arg=%arg%\"`、
     `exit /b %ERRORLEVEL%` 全部仍在（防止新映射挤掉旧逻辑）。
8. `test_zip_helper_when_scanned_keeps_atomic_replace_and_unix_mode`
   - arrange：读 `../../../tools/pack/zip_dist.py` 全文（只读）。
   - act：文本断言。
   - assert：含 `os.replace(`、`external_attr`、`ZIP_DEFLATED`、
     `smoke-out.txt`、`mkstemp`、`unlink(missing_ok=True)`；
     不含 `Compress-Archive` / `subprocess` / `import zipfile` 之外的第三方依赖。

守卫全部是静态文本 / AST 断言，不执行三个脚本、不触发 PyInstaller 构建；
用 `re` 与 `Path.read_text`，不引入新依赖（文件已 `import re` 与 `Path`）。

## 4. 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py tests/test_pack_zip.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
```

判定：三条退出码 0；架构 37 用例不变；pyright 零诊断（新守卫的常量注解、
`Path` / `str` 返回类型完整，不用 `Any` / `# type: ignore`）。
负向演练（可选但推荐）：临时把 sh 的 `sed -n '2,21p'` 改回 `'2,19p'`，
确认用例 4 变红后还原——证明守卫真能拦截漂移。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 文本断言过松（只查子串，漏掉分支位置） | 用例 2/3 用 `_after` 切片 + 计数断言，跳过分支与 else 分支分开 | 收紧断言 |
| `_after` 的 marker 漂移导致 `AssertionError` 难读 | 断言 marker 恰出现一次并在失败消息里带文件名 | 更新 marker（须同步 plan-c/d 定位） |
| sh 头注释继续新增 usage 后区间再次漂移 | 用例 4 解析 sed 终点并断言 ≥ 所有 usage / `--no-zip` / `by default` 行号 | 同步 sed 区间（守卫会红） |
| 新增守卫误伤既有参数化守卫 | 不改文件头、`_EXTRA_HINT_FILES` 与既有用例；验收跑整个文件 | `git revert` |

回滚：`git revert` 本波提交；脚本与助手各自独立提交，不受影响。
