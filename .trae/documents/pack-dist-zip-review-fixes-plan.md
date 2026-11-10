# IKTRDV 第一轮评审修复方案（review-fixes）

> 来源记录：[`../reviews/2026-11-10-pack-dist-zip.md`](../reviews/2026-11-10-pack-dist-zip.md)
> （`code-review-expert` 第一轮：blocker 0 / **major 3** / minor 7，强制自我批判后清单）。
> 唯一规范来源：本文件 + 来源记录 + `.trae/rules/` 8 份必读规则 +
> `pack-dist-zip-plan.md` 及其子计划总纲。本文引用仓库文件的相对路径以
> `.trae/documents/` 为基准；代码块内命令相对基准是仓库根。
> 无人值守下【批准】按通过处理（用户「所有问题无须过问」），不冒充用户确认；
> 登记见 `pack-dist-zip-progress.md`。

## 1. 目标与非目标

**目标**：修 M1 / M2 / M3 三条 major 至归零；顺带闭环 m2 / m3 / m4 / m5 / m6
五条 minor；m1 / m7 与存量 flake 登记为待办；随后再跑一轮
`code-review-expert` 评审，直至无 blocker / major。

**非目标**：
- 不改 `pack.ps1` 的 `param()` 参数面（不给 `$Dist` 加 Alias、不引入
  `ValueFromRemainingArguments` 手工解析），不改 CI / PyInstaller spec /
  `python -m tools.release` / `.yxp`；
- 不在本轮修评审第 6 项 `-n 1` 首轮 `test_app_panes` 失败（不在本分支 diff，
  评审已判存量负载时序假设，登记为另案待办，收尾门禁若复现再按
  `python-coding-style.md` §4.7 处理，不记「偶发」）；
- 不改 Linux 构建范围裁定（第一轮评审 §五 已判「可接受」）。

## 2. 备选方案与否决理由

| 方案 | 内容 | 裁决 |
| --- | --- | --- |
| A（选中，M1/M2） | 文档纠偏：PowerShell 直接调用统一写 `-Dist release` / `-NoZip -Dist release`；bat / sh 保留 `--dist` / `--no-zip` 真实可执行形态；在 ps1 帮助与双语文档里把「双连字符在 PowerShell 命令模式是 stop-parsing 形态」写成显式说明 | 选中：修复成本最低、不改参数面、文档与实现一致，且保留 issue 验收 1 的 bat `--dist` 与 `-Dist` 两条已真实构建验证的路径 |
| B | 给 ps1 的 `$Dist` 加 `[Alias("dist")]` 等让 `--dist` 直接可绑定 | **否决**：主代理实测 `& .\pack\pack.ps1 -dist release -Help` exit 0（单连字符可前缀匹配 `-Dist`），而 `--dist release -Help` 报位置参数错误；双连字符被解析为带前导连字符的参数名 / stop-parsing 标记，别名无法匹配。要支持须引入剩余参数手工解析，破坏 `param()` 契约与 `-Help` 行为，属为既有 PowerShell 行为打补丁、超范围 |
| C | M3 改 `read_text(encoding="utf-8", errors="surrogateescape")` 并在写回时用同 errors | **否决**：可行，但「其它行原样保留」依赖 surrogateescape 往返；字节方案更直接、零编码假设 |
| D | M3 单独捕获 `UnicodeDecodeError` 转成更明确的 `ZipDistError`，要求校验文件为 ASCII | **否决**：仍硬失败，只改善错误信息；多平台 / 多次构建共存的鲁棒性（issue §二.4）未改善 |
| E（选中，M3） | `_checksum_text` → `_checksum_bytes`：按字节 `splitlines()` 逐行保留，仅用 `decode("ascii", errors="replace")` 判断末列是否同名，新行 ascii 编码，`write_bytes` 落盘 | 选中：任何编码的既有行字节级原样保留；同名条目精确替换；写盘无 newline 转换（显式 LF 契约，顺带闭环 m3） |

## 3. 分步实施（波内文件互不重叠，波间串行）

| wave | 子计划 | 独占文件 | 输出 |
| --- | --- | --- | --- |
| R1 | a（Python 侧） | `../../tools/pack/zip_dist.py`、`../../tests/test_pack_zip.py`、`../../tests/test_pack_spec.py` | M3 修复 + 2 个新用例 + m2/m3/m4 闭环 |
| R1 | b（脚本文档侧） | `../../pack/pack.ps1`、`../../README.md`、`../../README.zh.md`、`../../yate/resources/manual.en.md`、`../../manual.zh.md` | M1/M2 修复、双语同步 |
| R2 | 主代理 | 本文件、来源评审记录、`pack-dist-zip-progress.md`、`pack-dist-zip-plans/overview.md`、评审索引 | 互链、状态回填、偏离裁定、提交 |

## 4. 详细修改与验收命令

### 4.1 R1-a：Python 侧（只改三个文件）

1. `tools/pack/zip_dist.py`
   - 新增模块常量 `#: ZIP epochs ...`：`_ZIP_EPOCH: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)`；
   - `_write_archive` 两处目录条目 `date_time=time.localtime()[:6]` → `date_time=_ZIP_EPOCH`（m2）；文件条目仍用源文件 `st_mtime`；
   - `_stage_files` docstring 把「deterministic output」明确为「deterministic entry order」（m2 语义澄清）；
   - `_checksum_text(...) -> str` 改为
     `_checksum_bytes(sums_path: Path, archive_name: str, digest: str) -> bytes`：
     `sums_path.read_bytes().splitlines()` 逐行；匹配时
     `line.decode("ascii", errors="replace").split()`，仅剔除末列
     `.lstrip("*") == archive_name` 的行；其余行 `append(line)` 原字节；
     末尾追加 `f"{digest}  {archive_name}".encode("ascii")`；返回
     `b"\n".join(lines) + b"\n"`；docstring 明示「deliberately LF for
     `sha256sum -c` / `shasum -c`」（m3 显式契约）；
   - `archive_stage` 中 `sums_tmp.write_text(..., encoding="ascii", newline="\n")`
     → `sums_tmp.write_bytes(_checksum_bytes(sums_path, archive.name, digest))`；
   - 不改 `os.replace` 顺序、`finally` 清理、`ZipDistError`、CLI 异常捕获表。
2. `tests/test_pack_zip.py` 新增两个用例（三要素）：
   - `test_archive_stage_when_checksum_rows_contain_non_ascii_bytes_preserves_them`：
     arrange 预置 dist 根 `SHA256SUMS.txt` 为 `b"caf\xe9  other.zip\n"`（并含一条
     同名旧 zip 条目）；act `zip_dist.archive_stage(stage, stage.parent)`；
     assert 不抛异常、`b"caf\xe9  other.zip"` 仍在字节内容中、同名旧条目被替换、
     新行 hash == `result.digest`、行数符合预期。
   - `test_archive_stage_when_directory_entries_are_written_uses_fixed_epoch`：
     arrange stage fixture；act 归档；assert 顶层 `<stage>/` 与 `<stage>/runtime/`
     目录条目的 `date_time == (1980, 1, 1, 0, 0, 0)`，文件条目显式 `create_system == 3`。
3. `tests/test_pack_spec.py` 用例 8（m4）：把 `import_roots` 的
   `re.findall(r"^import ...")` / `re.finditer(r"^from ...")` 替换为
   `ast.parse(helper)` 遍历 `ast.Import` / `ast.ImportFrom` 取根模块名
   （`alias.name.split(".")[0]`、`node.module`），保留
   `allowed_roots` 白名单断言与 `Compress-Archive` / `subprocess` 禁入断言。
   文件已 `import ast`，无需新增导入。

**验收命令**（退出码 0 才算通过）：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_zip.py tests/test_pack_spec.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

### 4.2 R1-b：脚本与双语文档（只改五个文件）

1. `pack/pack.ps1` 头注释：
   - `.EXAMPLE` 的 `.\\pack\\pack.ps1 --dist release` → `.\\pack\\pack.ps1 -Dist release`；
     `.\\pack\\pack.ps1 -NoZip --dist release` → `.\\pack\\pack.ps1 -NoZip -Dist release`；
     注释行 `# (a zip is produced by default; -NoZip skips it)` 保留；
   - `.DESCRIPTION` 追加一句英文：`PowerShell command mode treats --dist as a
     stop-parsing token; call this script with -Dist (the .bat wrapper and
     pack.sh accept --dist / --no-zip).`；
   - 不动 `param()`、`.PARAMETER NoZip`（其中 `--no-zip` 拼写说明是静态守卫
     断言目标，必须保留）、归档分支。
2. `README.md` / `README.zh.md`：把两条 ps1 示例改为 `-Dist release` /
   `-NoZip -Dist release`；在说明段补一句（英文 / 中文逐项对齐）：PowerShell
   直接调用使用 `-Dist`，`--dist` / `--no-zip` 由 `pack.bat` / `pack.sh`
   提供；bat / sh 示例保持原样。
3. `yate/resources/manual.en.md` / `manual.zh.md`：「Collect artifacts」段落补
   一句等价澄清（PowerShell 直接调用 `-Dist`；bat/sh 的 `--dist` / `--no-zip`
   由包装脚本映射），不改既有 `-OneFile -Dist release -NoZip` 示例（已是
   `-Dist` 形态）、不动 `build,ts,lua` 字样、不动章节编号；中英逐项对齐。

**验收命令**：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_spec.py -q
& .\pack\pack.ps1 -NoZip -Dist release -Help
.venv\Scripts\python.exe -m tools.changelog check
```
`-Help` 探针须 exit 0 且输出示例为 `-Dist` 形态；`-NoZip` 绑定正常。

### 4.3 R2：主代理文档回填

- 本文件回填真实结果；来源评审记录末尾加互链（doc-conventions.md §二.2）；
- `pack-dist-zip-progress.md`：删除 m5 指出的「负向演练尚未执行」矛盾陈述，
  改为指向 wave-4 已执行记录；登记迭代轮次与 major 归零判据；
- `pack-dist-zip-plans/overview.md` §六：新增「退出码」列（m6），并登记
  M1/M2 的修复路径与实测依据；
- `.trae/reviews/README.md` 索引登记第一轮评审记录（收尾统一做）。

## 5. 风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 字节方案改变校验文件换行语义 | 显式 `b"\n"` + docstring 契约；单测断言其它行字节原样 | 还原 `_checksum_text` |
| `decode("ascii", errors="replace")` 判断末列时非 ASCII 文件名被替换 | 仅用于「是否同名」判断，不写回；stage/zip 名由脚本生成为 ASCII | 改用 latin-1 判断 |
| 固定 epoch 让解压后目录 mtime 变 1980 | 目录条目本无内容，mtime 无业务语义；文件条目仍保真 | 还原 `time.localtime()` |
| 改 `.EXAMPLE` 后静态守卫用例 1 找不到 `--no-zip` | `.PARAMETER NoZip` 段仍含 `--no-zip`；验收命令实测 | 在 `.PARAMETER` 补回拼写 |
| 双语文档措辞漂移 | 中英逐项对齐，人工核对 + `test_pack_spec.py` 的 `build,ts,lua` 守卫 | `git revert` |

回滚总路径：本轮改动集中在 8 个文件，`git revert` 本轮提交即可；不触碰
上一轮已验证的归档流程与三脚本执行分支。

## 6. 验收映射与迭代判据

| 评审项 | 修复后判据 |
| --- | --- |
| M1 | README / README.zh 的 ps1 示例为 `-Dist` 形态并实测可绑定；手册补澄清；`--dist` 仅出现在 bat / sh 的可执行示例 |
| M2 | `pack.ps1 -Help` 打印的示例为 `-Dist` 形态；`-NoZip -Dist release -Help` exit 0 |
| M3 | 含非 ASCII 行的 `SHA256SUMS.txt` 归档成功、其它行字节原样、同名条目仍精确替换；新增单测覆盖 |
| m2/m3/m4/m5/m6 | 目录条目固定 epoch、LF 契约注释、ast 守卫、进度文档矛盾消除、偏离表退出码列 |
| 门禁 | 第二轮评审重跑六项（pyright / pytest -n auto / 架构 37 / 覆盖率 ≥75 / 冒烟 / changelog check），退出码全 0 |
| 迭代终点 | 第二轮 `code-review-expert` 结论 blocker 0 / major 0；仅 minor 登记待办 |

## 7. 待办登记（不阻塞合入）

- m1：`pack.bat` 对 `powershell.exe` 启动期失败（参数绑定 / 执行策略）无
  可辨识提示——既有行为，另案；
- m7：`pack.sh` 的 `sed -n '2,21p'` 仍为硬编码区间——守卫已充分并有负向
  演练背书，登记为已知脆弱点；
- 评审 §一第 6 项：`-n 1` 首轮 `test_app_panes.py::test_close_command_closes_active_pane`
  存量负载时序假设，不在本分支 diff，另案；收尾门禁若复现按
  `python-coding-style.md` §4.7 修用例，不记「偶发」。
