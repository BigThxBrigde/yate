# 子计划 e：`pack/pack.bat` 的 `--no-zip` → `-NoZip` 映射（wave-2）

> 路径以本文件所在目录为基准：`../../../pack/pack.bat` 即仓库根 `pack/pack.bat`。
> 唯一规范来源：本文件 + `../pack-dist-zip-plan.md` §4 + `overview.md` 波次表。
> 前置：wave-1 全绿；与 plan-c / plan-d 同波并行（文件互不重叠）。

## 1. 输入

- 现状：`../../../pack/pack.bat:2-13` 头注释列出用法示例；`:16-19` 在解析
  循环前解析 `%~dp0pack.ps1` 到 `%SCRIPT%`；`:21-26` 注释说明「kebab-case
  参数无法被 `powershell -File` 绑定，故显式映射」；`:28-41` `:parse` 循环
  逐参数重引号，已有 `--onefile` → `-OneFile`、`--skip-changelog` →
  `-SkipChangelog`、`--dist` → `-Dist`、`--help` → `-Help`；`:35-38` 尾反斜杠
  处理；`:43-45` `powershell -NoProfile -ExecutionPolicy Bypass -File
  "%SCRIPT%" %ARGS%` 与 `exit /b %ERRORLEVEL%`。
- 既有惯例：`--no-zip` 属 kebab-case，必须显式映射为 `-NoZip`，否则
  `powershell -File` 会报 `NamedParameterNotFound`。
- 助手契约：`-NoZip` 由 ps1（plan-c）消费，bat 不改 ps1。

## 2. 独占文件清单

只改 `../../../pack/pack.bat`。**不得**改 `pack.ps1` / `pack.sh` / 测试 /
助手 / 文档（分属 plan-c / plan-d / plan-b / plan-a / plan-f）。

## 3. 具体修改（定位到行号）

1. **头注释（`:6-12` 示例块）** 追加两行（英文，与既有 `rem` 风格一致）：
   ```bat
   rem    pack\pack.bat --dist release
   rem                                collect + produce a zip archive by default
   rem    pack\pack.bat --no-zip --dist release
   rem                                collect without producing a zip archive
   ```
   若 `--onefile --dist release` 示例（`:10-11`）已存在，只补 `--no-zip`
   两行 + 一行 `rem` 说明「a zip is produced by default」即可。头注释必须
   同时出现 `--no-zip` 与「默认生成 zip」语义（issue 验收 1 / 6）。
2. **`:parse` 循环（`:31-34` 映射组）** 在 `--help` 映射之后插入一行：
   ```bat
   if /i "%arg%"=="--no-zip" set "arg=-NoZip"
   ```
   - 保持 `if /i` 大小写不敏感与既有映射写法一致；
   - 位置在 `:35-38` 尾反斜杠处理与 `set "ARGS=..."` **之前**（与既有映射同组）；
   - `shift` / `goto parse` / `:run` / `%ERRORLEVEL%` 一律不动，未知参数仍
     原样透传给 ps1。

**不改**：`%SCRIPT%` 预解析、尾反斜杠双写逻辑（`:35-38`）、
`powershell -File` 调用、`exit /b %ERRORLEVEL%`。

## 4. 验证方案与测试用例（静态守卫由 plan-b 落地）

| 用例 / 探针 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_no_zip_switch_when_scripts_parsed_is_declared_and_mapped_in_all_three`（plan-b） | bat 文本 | 文本断言 | 恰有 `if /i "%arg%"=="--no-zip" set "arg=-NoZip"` 映射；头注释含 `--no-zip` 示例 |
| `test_help_text_when_scripts_scanned_covers_new_switch`（plan-b） | bat 文本 | 文本断言 | 头注释含 `--no-zip` 与 `by default` / `zip archive` 说明 |
| `test_bat_wrapper_when_mapping_scanned_keeps_existing_mappings`（plan-b） | bat 文本 | 文本断言 | 既有 `--onefile` / `--skip-changelog` / `--dist` / `--help` 四映射与 `SCRIPT` 预解析、尾反斜杠处理仍在 |
| `--help` 透传探针（本波手工） | plan-c 已落盘 | `cmd /c "pack\pack.bat --help"` | 退出码 0；输出含 `-NoZip` 与默认生成 zip 说明（bat `--help` → `-Help` → ps1 `Get-Help -Detailed`） |
| `--no-zip` 绑定探针（本波手工） | plan-c 已落盘 | `cmd /c "pack\pack.bat --no-zip --help"` | 退出码 0；无 `NamedParameterNotFound`（`-NoZip` 被 ps1 正确绑定；`-Help` 抢先退出，不触发构建） |

**注意**：bat 的 `--help` 输出来自 ps1 的 `Get-Help -Detailed`，不是 bat 头注释；
头注释里的 `--no-zip` 由静态守卫覆盖，二者共同满足 issue 验收 1。

## 5. 可执行验收命令

```powershell
cmd /c "pack\pack.bat --help"
cmd /c "pack\pack.bat --no-zip --help"
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
```

三条退出码全 0。`--help` / `-Help` 在 ps1 的 `if ($Help)` 分支 `exit 0`，
**不触发 PyInstaller 构建**。真实 `--dist` 构建在 wave-4 覆盖。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `cmd.exe` 里 `--no-zip` 未映射导致 `NamedParameterNotFound` | 显式 `if /i` 映射；`--no-zip --help` 探针实测 | 补映射 |
| 映射行放在重引号之后导致 `%arg%` 已被引用包裹 | 钉在 `:31-34` 映射组内、`set "ARGS=..."` 之前 | 移动行 |
| 头注释示例与 ps1 `.EXAMPLE` 措辞漂移 | 两处都写「默认生成 zip / --no-zip 跳过」，plan-b 守卫断言 | 同步措辞 |
| 误改 `exit /b %ERRORLEVEL%` 丢失助手失败退出码 | 该行明确不动 | 恢复原行 |

回滚：`git revert` 本波提交；ps1 的 `[switch]$NoZip` 仍可独立通过
直接调用使用。
