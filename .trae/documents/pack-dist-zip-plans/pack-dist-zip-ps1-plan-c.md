# 子计划 c：`pack/pack.ps1` 的 `-NoZip` 与归档分支（wave-2）

> 路径以本文件所在目录为基准：`../../../pack/pack.ps1` 即仓库根 `pack/pack.ps1`。
> 唯一规范来源：本文件 + `../pack-dist-zip-plan.md` §4 + `overview.md` 波次表。
> 前置：wave-1 全部验收命令退出码 0（`python -m tools.pack.zip_dist` 可用）。

## 1. 输入

- 现状：`../../../pack/pack.ps1:2-29` 头注释（`.SYNOPSIS` / `.DESCRIPTION` /
  `.EXAMPLE`，无 `.PARAMETER`）；`:31-43` `param()` 四参数；`:45-50`
  `if ($Help) { Get-Help ... -Detailed; exit 0 }`；`:175-266` `--dist` 收集块，
  末尾 `:262-265` 打印 `Collected ->` 与 `SHA256 yate.exe` 后即结束。
- 助手契约（wave-1）：`python -m tools.pack.zip_dist --stage <abs> --dist-root <abs>`，
  成功退出 0 并打印 `ZIP -> <path>  (<X.X MB>)` 与 `  SHA256 <name>.zip: <hash>`，
  失败退出 1 并写 `error: ...` 到 stderr。

## 2. 独占文件清单

只改 `../../../pack/pack.ps1`。**不得**改 `pack.sh` / `pack.bat` /
`tests/test_pack_spec.py` / 助手 / 文档（分别归 plan-d / plan-e / plan-b / plan-a / plan-f）。

## 3. 具体修改（定位到行号）

1. **头注释 `.DESCRIPTION`（`:5-20` 末尾）** 追加英文说明（不改既有文字）：
   ```
   When --dist is used, the collected stage is archived into <dist>/<stage>.zip
   by default after the copy, SHA256SUMS.txt and --version smoke test all
   succeed. Pass -NoZip to skip the archive; the wrapper spelling is --no-zip.
   ```
2. **新增 `.PARAMETER NoZip` 段**（放在 `.DESCRIPTION` 之后、`.EXAMPLE` 之前）：
   ```
   .PARAMETER NoZip
       Skip the zip archive for --dist collections. A zip is produced by default.
       Wrapper spelling: --no-zip (pack.bat); Linux equivalent: pack.sh --no-zip.
   ```
   `Get-Help -Detailed` 会渲染该段，使 `-Help` 输出同时含 `-NoZip`、`--no-zip`
   与「默认生成 zip」说明（issue 验收 1）。
3. **`.EXAMPLE`（`:22-29`）** 追加两行：
   ```
   .\pack\pack.ps1 --dist release
   .\pack\pack.ps1 -NoZip --dist release
   ```
   （第一行已存在则只补第二行 + 一行注释 `# (a zip is produced by default; -NoZip skips it)`）。
4. **`param()`（`:31-43`）** 在 `[string]$Dist = ""` 之后、`[switch]$Help` 之前插入：
   ```powershell
   [switch]$NoZip,
   ```
   不带 `[Parameter]` 特性，与既有四参数写法一致；默认 `$false`（= 生成 zip）。
5. **`--dist` 块末尾（`:265` 之后、`:266` 的 `}` 之前）** 插入唯一归档分支：
   ```powershell
   if ($NoZip) {
       Write-Host "ZIP skipped (-NoZip)" -ForegroundColor Yellow
   } else {
       & $pythonExe -m tools.pack.zip_dist --stage $stage --dist-root $distRoot
       if ($LASTEXITCODE -ne 0) {
           Stop-WithMessage "Failed to create zip archive for '$stage'."
       }
   }
   ```
   - 位置严格在 `Remove-Item $smokeOut`（`:260`）与 `Collected ->`（`:264`）之后，
     保证前置步骤失败时到达不了归档分支；
   - 不重定向 native stderr（`:83-93` 注释实证的 PowerShell 5.1 陷阱）；
   - `$stage` / `$distRoot` 均为绝对路径（`:183,192` 已算好），变量作单 token
     传参，路径含空格不会裂开；
   - 分支在 `if ($Dist -ne "")`（`:182`）内部，未传 `--dist` 时无论开关取值都不
     触发，也不打印跳过提示；
   - `-NoZip` 分支只 `Write-Host`，不删除 / 不改写任何 zip 或校验文件
     （issue 验收 5）。

**不改**：stage 命名 `yate-$version-windows-$arch`（`:191`）、先删再建
（`:199-201`）、复制（`:203-212`）、stage 内 SHA256SUMS.txt（`:214-229`）、
`WaitForExit(30000)`（`:249`）、`Remove-Item $smokeOut`（`:260`）、
`Collected ->`（`:264`）、`ErrorActionPreference`、`Push-Location/Pop-Location`。

## 4. 验证方案与测试用例（静态守卫由 plan-b 落地，本波先跑脚本级探针）

| 用例 / 探针 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_no_zip_switch_when_scripts_parsed_is_declared_and_mapped_in_all_three`（plan-b） | 读取三个脚本文本 | 文本断言 | ps1 含 `[switch]$NoZip`、`.PARAMETER NoZip`、`-NoZip` 字样与 `--no-zip` 包装拼写、默认生成 zip 说明 |
| `test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist`（plan-b） | 切出 `if ($Dist -ne "")` 之后的文本 | 文本断言 | `tools.pack.zip_dist` 只出现在该块内；`if ($NoZip)` 跳过分支存在 |
| `test_no_zip_when_requested_skips_archive_without_touching_existing_files`（plan-b） | ps1 文本 | 文本断言 | `-NoZip` 分支不含 `Remove-Item` / `Set-Content` / 助手调用 |
| `test_dist_and_smoke_semantics_when_scripts_scanned_are_unchanged`（plan-b） | ps1 文本 | 文本断言 | `WaitForExit(30000)`、`SHA256SUMS.txt`、`Remove-Item $smokeOut`、`Collected ->`、`yate-$version-windows-$arch` 全部仍在 |
| 参数绑定探针（本波手工） | 无构建需求 | `powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -NoZip -Help` | 退出码 0；`-NoZip` 被正确绑定、无 `NamedParameterNotFound` |
| 帮助探针（本波手工） | 同上 | `powershell ... -File pack/pack.ps1 -Help` | 输出含 `-NoZip`、`--no-zip`、`.PARAMETER NoZip` 段与 `by default` |
| 助手可达探针（本波手工） | wave-1 助手已落盘 | `.venv\Scripts\python.exe -m tools.pack.zip_dist --help` | 退出码 0，usage 含 `--stage` / `--dist-root` |

## 5. 可执行验收命令（退出码 0 才算通过）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -Help
powershell -NoProfile -ExecutionPolicy Bypass -File pack/pack.ps1 -NoZip -Help
.venv\Scripts\python.exe -m tools.pack.zip_dist --help
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
```

`-Help` 与 `-NoZip -Help` 都在 `if ($Help)` 分支 `exit 0`，**不会触发
PyInstaller 构建**，是安全的参数绑定探针；真实构建在 wave-4。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `--dist` 直接传给 ps1 时参数绑定漂移 | 沿用既有 `.EXAMPLE` 的 `--dist` 形态，`-NoZip` 为独立 switch；`-NoZip -Help` 探针实测绑定 | 删除 `[switch]$NoZip` 及分支 |
| PowerShell 5.1 把助手 stderr 当终止错误 | 不重定向 stderr；失败时助手自身已打印可读 error，再经 `$LASTEXITCODE` → `Stop-WithMessage` | 助手错误改 stdout |
| `$LASTEXITCODE` 被其它表达式覆盖 | 调用后立刻判断，中间无其它 native 命令 | 紧邻判断 |
| 归档分支误放在冒烟之前 | 明确插入点 `:265` 之后；plan-b 守卫断言顺序 | 移动分支 |

回滚：`git revert` 本波提交即可；助手仍在 wave-1（单独提交，可独立保留）。
