# 子计划 d：`pack/pack.sh` 的 `--no-zip`、帮助区间与归档分支（wave-2）

> 路径以本文件所在目录为基准：`../../../pack/pack.sh` 即仓库根 `pack/pack.sh`。
> 唯一规范来源：本文件 + `../pack-dist-zip-plan.md` §4 + `overview.md` 波次表。
> 前置：wave-1 全绿；与 plan-c / plan-e 同波并行（文件互不重叠）。

## 1. 输入

- 现状：`../../../pack/pack.sh:5-11` usage 头注释；`:26-29` `show_help()` 用
  `sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'` 截头注释；`:31-62` 参数循环，
  `*:` 分支 `:56-59` 报 `unknown argument` 并 `exit 2`；`:164-209` `--dist`
  收集块，末尾 `:204-208` 计算大小、打印 `Collected ->` 与
  `sed 's/^/  SHA256 yate: /' "$stage/SHA256SUMS.txt"`，`:209` 是 `fi`。
- 硬约束（issue §三）：新增 usage 行后必须同步 `sed` 行区间，否则 `-h`
  看不到新开关；Linux `chmod 0755 "$stage/yate"`（`:189`）的可执行位由助手
  `external_attr` 写入 zip，本脚本不改该行。
- 助手契约：`"$py" -m tools.pack.zip_dist --stage "$stage" --dist-root "$dist_root"`，
  成功退出 0 打印 `ZIP -> ...` / `  SHA256 ...`，失败退出 1 写 stderr。

## 2. 独占文件清单

只改 `../../../pack/pack.sh`。**不得**改 `pack.ps1` / `pack.bat` / 测试 / 助手 /
文档（分属 plan-c / plan-e / plan-b / plan-a / plan-f）。

## 3. 具体修改（定位到行号，行数逐项可核）

1. **头注释 usage 块（原 `:5-11`）**：在原 `:11`
   `#   ./pack/pack.sh -h            show this help` 之后插入 **2 行**：
   ```bash
   #   ./pack/pack.sh --no-zip      skip the default zip archive for --dist
   # A successful --dist collection produces a zip archive by default.
   ```
   新增 2 行 → 原 `:12` 起全部下移 2 行。
2. **`show_help()`（原 `:26-29`）**：把 `sed -n '2,19p'` 改为
   `sed -n '2,21p'`（终点 = 19 + 新增 2 行），使 `-h` 输出覆盖新 usage 行与
   「默认生成 zip」说明。区间终点由 plan-b 静态守卫钉死（见 §4），不得凭记忆维护。
3. **参数默认值（原 `:31-33`）**：在 `dist_arg=""` 之后加 `no_zip=0`
   （默认生成 zip）。
4. **参数 `case`（原 `:35-62`）**：在 `--dist=*` / `-d=*` 分支之后、
   `-h|--help)` 之前插入：
   ```bash
   --no-zip)
       no_zip=1
       ;;
   ```
   `*:` 未知参数分支（原 `:56-59`）**原样保留**，`--zip` 等仍报
   `unknown argument ... (see -h)` 并 `exit 2`（issue 验收 2）。
5. **`--dist` 块末尾（原 `:208` 之后、`:209` `fi` 之前）** 插入：
   ```bash
   if [ "$no_zip" -eq 1 ]; then
       echo "zip skipped (--no-zip)"
   else
       "$py" -m tools.pack.zip_dist --stage "$stage" --dist-root "$dist_root" || {
           echo "error: failed to create zip archive for '$stage'" >&2
           exit 1
       }
   fi
   ```
   - 位置严格在 `if ! timeout 30 ...`（原 `:199-202`）冒烟成功之后、
     `Collected ->`（原 `:207`）之后，前置失败到不了归档分支；
   - `set -euo pipefail`（`:24`）保持；助手非 0 由 `|| { ...; }` 给出明确错误
     并 `exit 1`（语义与 ps1 的 `Stop-WithMessage` 对齐）；
   - 分支在 `if [ -n "$dist_arg" ]`（原 `:166`）内部，未传 `--dist` 不触发；
   - `-m tools.pack.zip_dist` 从仓库根执行（`:64-67` 已 `cd "$root"`），
     解释器是 `.venv/bin/python`（`:72`），无第三方依赖；
   - `--no-zip` 分支只 `echo`，不删除 / 不改写历史 zip 或校验文件。

**不改**：`set -euo pipefail`、`show_help()` 的 `sed 's/^# \{0,1\}//'`、
`--dist|-d` / `--dist=*` / `-d=*` 分支、未知参数 `exit 2`、stage 命名
`yate-$version-linux-$arch`（原 `:180`）、`[ -e "$stage" ] && rm -rf "$stage"`
（原 `:184`）、`cp -a` / `chmod 0755`（原 `:186-193`）、
`( cd "$stage" && sha256sum yate > SHA256SUMS.txt )`（原 `:195`）、
`timeout 30`（原 `:199`）、`Collected ->`（原 `:207`）。

## 4. 验证方案与测试用例（静态守卫由 plan-b 落地）

| 用例 / 探针 | arrange | act | assert |
| --- | --- | --- | --- |
| `test_no_zip_switch_when_scripts_parsed_is_declared_and_mapped_in_all_three`（plan-b） | sh 文本 | 文本断言 | 含 `--no-zip)` case、`no_zip=0` 默认、`no_zip=1` 赋值 |
| `test_help_text_when_scripts_scanned_covers_new_switch`（plan-b） | 解析 `show_help()` 的 `sed -n '2,(\d+)p'` 终点 N；枚举头注释前 30 行 | 文本断言 | N ≥ 所有 `#   ./pack/pack.sh` usage 行最大行号；含 `--no-zip` 的行号 ≤ N；含 `by default` 的行号 ≤ N |
| `test_unknown_arguments_when_sh_parsed_still_exit_two`（plan-b） | sh 文本 | 文本断言 | `*:` 分支仍含 `exit 2`；case 中不存在 `--zip)` 正向分支 |
| `test_zip_default_when_dist_used_is_enabled_and_guarded_by_dist`（plan-b） | 切出 `if [ -n "$dist_arg" ]` 之后文本 | 文本断言 | `zip_dist` 只在该块内；`if [ "$no_zip" -eq 1 ]` 跳过分支存在 |
| `test_dist_and_smoke_semantics_when_scripts_scanned_are_unchanged`（plan-b） | sh 文本 | 文本断言 | `timeout 30`、`sha256sum yate > SHA256SUMS.txt`、`chmod 0755`、`yate-$version-linux-$arch`、`Collected ->` 全部仍在 |
| 帮助探针（本波手工，bash 可用时） | 无构建需求 | `bash pack/pack.sh -h` | 退出码 0；输出含 `--no-zip` 与 `by default` |
| 未知参数探针（本波手工，bash 可用时） | 无构建需求 | `bash pack/pack.sh --zip` | 退出码 2；stderr 含 `unknown argument: --zip` |
| 助手可达探针（本波手工） | wave-1 助手已落盘 | `.venv\Scripts\python.exe -m tools.pack.zip_dist --help` | 退出码 0 |

**偏离预案**：本机为 Windows，若 `bash` 不可用，上述两个手工探针无法执行，
由 plan-b 静态守卫 + plan-a 助手单测覆盖，并在 `overview.md` §六登记
「bash 不可用」的实测命令与退出码；不得声称跑过 Linux 构建或 bash 帮助输出。

## 5. 可执行验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m tools.pack.zip_dist --help
bash pack/pack.sh -h
bash pack/pack.sh --zip
```

前两条必须退出码 0；后两条在 bash 可用时分别期望 0 / 2（`--zip` 的退出码 2
是预期值，用 PowerShell 显式检查 `$LASTEXITCODE -eq 2`，不视为失败）。
`-h` 与 `--zip` 都在参数解析阶段退出，**不触发 PyInstaller 构建**。

## 6. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| `sed -n '2,19p'` 硬编码区间漏新 usage | 同步改 `2,21p`；plan-b 守卫解析终点并断言覆盖所有 usage 行 | 修区间（守卫会红） |
| `--no-zip` 与 `--dist=DIR` / `-d=DIR` 组合解析错位 | case 分支独立、循环末尾统一 `shift`；未知参数仍 `exit 2` | 调整 case |
| `|| { ...; }` 与 `set -e` 交互导致错误被吞 | 显式 `exit 1` + stderr；`set -e` 下 `||` 块是唯一失败出口 | 改回 `if ! ...; then` |
| zip 内 Linux 可执行位丢失 | 不改 `chmod 0755`；助手 `posix=True` 分支读真实 mode 写 `external_attr`（plan-a 单测覆盖） | 修助手，非本脚本 |
| 归档分支误放在冒烟之前 | 插入点钉在 `:208` 之后；plan-b 守卫断言顺序 | 移动分支 |

回滚：`git revert` 本波提交；助手与 ps1 / bat 各有独立提交，互不影响。
