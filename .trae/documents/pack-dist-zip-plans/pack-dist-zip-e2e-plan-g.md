# 子计划 g：Windows 真实构建 E2E 与跨平台等价验证（wave-4，主代理执行）

> 路径以本文件所在目录为基准：`../../../pack/pack.ps1` 即仓库根 `pack/pack.ps1`。
> 唯一规范来源：本文件 + `../pack-dist-zip-plan.md` §6/§7 + `overview.md` 波次表。
> 前置：wave-3 全部验收命令退出码 0。本波**不写源码**，只跑构建与只读校验；
> 临时构建产物落在被 `.gitignore` 忽略的 `dist/` / `build/` / `release-e2e/`。

## 1. 目标与偏离口径

- issue 验收 3 要求 Windows 真实构建产物校验；验收 4 允许「若本轮无法在两平台
  都跑完整 PyInstaller 构建，至少一平台做真实构建，另一平台由脚本级用例 +
  静态守卫覆盖，并在方案中记录偏离理由」。
- 本机 OS 为 win32，CI 不跑 pack（issue 背景表取证），故 **Windows 做真实构建，
  Linux 不做真实构建**：Linux 侧由同一份助手的 `posix=True` mode 单测、
  `pack.sh` 静态守卫、`python -m zipfile -t` 完整性检查覆盖。**不得声称跑过
  Linux 构建**；偏离理由与等价验证命令在收尾文档显式登记。
- 若 Windows 真实构建本身失败（网络 / `[build,ts,lua]` extras / PyInstaller），
  记录实测命令与退出码，启用 §5 的 pseudo-stage dry-run 等价路径，并在收尾
  明确列出未达标项，不得粉饰。

## 2. 构建矩阵（按序，逐步记录退出码）

| # | 命令 | 期望 |
| --- | --- | --- |
| 0 | `.venv\Scripts\python.exe -m pip install -e ".[build,ts,lua]"` | 退出 0；PyInstaller 可用（脚本自身也会自动安装） |
| 1 | `powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -SkipChangelog --dist release-e2e` | 退出 0；输出含 `Collected ->`、`ZIP ->`、`SHA256 ...zip`；生成 `<dist>/<stage>.zip` |
| 2 | `powershell ... -File pack/pack.ps1 -SkipChangelog -OneFile -Dist release-e2e` | 退出 0；同名 stage 先删再建、同名 zip 被覆盖；校验文件同名条目仍 1 行 |
| 3 | `powershell ... -File pack/pack.ps1 -SkipChangelog -NoZip -Dist release-e2e` | 退出 0；输出含 `ZIP skipped (-NoZip)` 与 `Collected ->`；旧 zip 不被删除/修改、校验文件不变 |
| 4 | `cmd /c "pack\pack.bat --no-zip --help"` / `cmd /c "pack\pack.bat --help"` | 退出 0；`-NoZip` 绑定成功、帮助含新开关（wave-2 已探针，本波复核） |
| 5 | `powershell ... -File pack/pack.ps1 -Help` | 退出 0；输出含 `-NoZip` / `--no-zip` / 默认生成 zip 说明 |
| 6 | `bash pack/pack.sh -h` 与 `bash pack/pack.sh --zip`（bash 可用时） | 分别退出 0 / 2；`-h` 显示 `--no-zip`，`--zip` 报 `unknown argument` |

`-SkipChangelog` 避免 `python -m tools.changelog generate --bundle-only` 改写
`yate/resources/changelog.*.md`（受 git 跟踪）。未带 `--dist` 的组合不再额外跑
一次完整构建：由 wave-3 静态守卫断言归档分支严格位于 `if ($Dist -ne "")` /
`if [ -n "$dist_arg" ]` 内部，属等价覆盖（登记于此）。

## 3. 产物校验（每条含 arrange / act / assert）

| 校验 | arrange | act | assert |
| --- | --- | --- | --- |
| zip 命名与位置 | 构建 1 产物 | 列出 `release-e2e/` | 恰有 `<stage>.zip`，`<stage>` == `yate-<yate.__version__>-windows-<x64\|arm64>`，与 stage 目录同名同级 |
| 顶层目录与内容 | 同上 | `zipfile.ZipFile(...).namelist()` | 所有条目以 `<stage>/` 开头；含 `<stage>/SHA256SUMS.txt`、可执行文件与 `runtime/`（构建 1）或单个 exe（构建 2）；不含 `smoke-out.txt`、不含任何 `.tmp` |
| 完整性 | 同上 | `python -m zipfile -t <zip>` + `ZipFile.testzip()` | 退出 0 / 返回 `None`（等价 Linux `unzip -t` / `python -m zipfile -t`） |
| 目录树一致（issue 验收 3） | `Expand-Archive -Path <zip> -DestinationPath <tmp>` | 递归比较解压目录与 stage 的相对路径集合与文件字节 | 集合完全相等、字节一致；`Expand-Archive` 退出 0 |
| zip SHA256 校验条目 | 同上 | `Get-FileHash -Algorithm SHA256 <zip>` 与 `release-e2e/SHA256SUMS.txt` | 该 zip 的条目 hash 与 `Get-FileHash` 一致；同名条目恰好 1 行；其它平台 / 版本行保留 |
| 可执行文件冒烟 | 解压目录 | `& <解压>/<stage>/yate.exe --version` | 退出 0；输出含 `yate.__version__` |
| stage 保留与内部校验不变 | 构建 1 后记录 stage 内 `SHA256SUMS.txt` 字节 | 构建 1/2/3 后复查 | stage 目录始终存在；其内部 `SHA256SUMS.txt` 字节与记录一致 |
| 重复执行覆盖 + 条目幂等 | 构建 1 记录 zip hash，构建 2 重跑 | 比较两次 | zip 被覆盖（hash 变化或内容随 onefile 变化）；`SHA256SUMS.txt` 同名条目仍 1 行且 hash 与新 zip 一致 |
| `--no-zip` 跳过语义 | 构建 2 后记录 zip 字节 hash 与校验文件全文 | 构建 3 | 输出含 `ZIP skipped (-NoZip)`；zip 字节 hash 与校验文件全文**逐字节不变**；`Collected ->` 与冒烟仍执行 |
| Linux 可执行位等价 | plan-a 单测 `test_archive_stage_when_posix_mode_flag_set_marks_executable_bit` | `python -m pytest tests/test_pack_zip.py -q` | 退出 0；`external_attr` 含 `0o755` 且 `create_system == 3` |

校验逻辑用一次性 Python 探针脚本（放仓库根 `_verify_dist_zip.py`，
`/ _*.py` 已被 `.gitignore` 忽略，验证完删除）或
`.venv\Scripts\python.exe -c "..."` 短表达式实现，不把逻辑塞进 PowerShell
命令行拼接（`misc-rules.md` §二）。PowerShell 侧只跑 `Expand-Archive` /
`Get-FileHash` / 可执行冒烟三条原生命令。

## 4. 可执行验收命令（汇总，退出码逐条记录）

```powershell
.venv\Scripts\python.exe -m pip install -e ".[build,ts,lua]"
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -SkipChangelog --dist release-e2e
.venv\Scripts\python.exe -m zipfile -t release-e2e\<stage>.zip
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -SkipChangelog -OneFile -Dist release-e2e
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -SkipChangelog -NoZip -Dist release-e2e
cmd /c "pack\pack.bat --no-zip --help"
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -Help
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py tests/test_pack_spec.py -q
```

## 5. 失败降级路径（pseudo-stage dry-run）

若构建矩阵任一步非 0：
1. 记录该步命令、stderr 摘要与退出码到 `../pack-dist-zip-progress.md` 与
   收尾回填；
2. 用 Python 在临时目录构造伪 stage（含 `yate.exe`、`runtime/base.dll`、
   `SHA256SUMS.txt`、`smoke-out.txt`），直接调用
   `.venv\Scripts\python.exe -m tools.pack.zip_dist --stage <stage> --dist-root <dist>`
   三次（默认 / 追加文件后再跑 / 校验条目幂等），并跑
   `python -m zipfile -t`、`ZipFile.testzip()`、`namelist()` 断言；
3. 三脚本参数矩阵改由 wave-2/3 的 `-Help` / `--help` 静态守卫与助手 CLI 覆盖；
4. 收尾文档把「Windows 真实构建产物校验」列为**未达标**，附实测错误，不得
   以等价验证冒充真实构建。

## 6. 收尾与清理

- `git status --short` 确认除本波已提交的源码 / 文档外无意外改动；
- `dist/` / `build/` / `release-e2e/` 均被 `.gitignore` 忽略：可用 Python
  `shutil.rmtree` 分批清理（不删 `.codebuddy/`，不用仓库内 basetemp）；清理
  与否都须在收尾记录；
- 主代理随后统一跑五项全量门禁 + `python -m tools.changelog check`，回填
  主计划 §6 验收映射的真实结果与 §7 偏离记录，按 `git-commit-message.md`
  逐步提交（只提交、不推送、不自动合流）。
