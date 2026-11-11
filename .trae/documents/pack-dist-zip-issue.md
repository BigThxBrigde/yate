# IKTRDV issue 素材（【领会】整理稿）

本文件是 `task-orchestration.md` §二.1 的「issue 文本读取整理」产物：只整理需求原文、
约束与既有上下文事实，**不做任务分析、不产出方案**（任务分析与方案由【方案】环节承担）。
唯一规范来源：本文件 + `.trae/rules/` 8 份必读规则。

来源：<https://gitee.com/jermaine/yate/issues/IKTRDV>（状态「待办的」，标签
`enhancement` / `feature`，评论 0，创建于 2026-11-08 18:39）。

## 一、执行环境（用户指令）

- 用户指令：「进入无人值守，所有问题无须过问，如果任务执行失败，重新更新状态继续
  执行，根据 <https://gitee.com/jermaine/yate/issues/IKTRDV> 执行新任务，所有步骤
  必须按照纪律严格执行」。
- 因此：方案批准、步骤确认、权限申请一律按通过处理；子代理 spawn 显式给
  `bypassPermissions`；**不向用户发起任何询问**；失败/中断时先更新落盘状态
  （`.trae/documents/pack-dist-zip-progress.md`）再凭记录续作，不凭记忆重建事实。
- 模型分配：未显式覆盖，按 `task-orchestration.md` §一.3 依主代理来源表格执行；
  运行时模型报未注册按 §一.3.5 重试一次、再失败按 §三 主代理兜底并如实标注。
- 主仓基线：`master` HEAD `b982c06`（与 `origin/master` 一致，工作树干净）；
  本任务 worktree 目录名 `yate-pack-dist-zip`（仓库同级），分支
  `feature/feat-pack-dist-zip`，parent 为 `master`；worktree 内已重建独立 `.venv`
  并自证 `import yate` 指向该 worktree。任务名 `pack-dist-zip`。

## 二、issue 原文（去重整理）

### 标题

FEAT: PACK --DIST RELEASE 构建结束后自动产出 ZIP 归档（默认开启，可用 --NO-ZIP 关闭）

### 术语约定

- 本 issue 的「release」指 `pack/pack.ps1` / `pack/pack.sh` 的 `--dist <dir>` 产物
  收集阶段（脚本自带示例即 `.\\pack\\pack.ps1 --dist release`、
  `pack\\pack.bat --onefile --dist release`），不是 `python -m tools.release`；后者
  只做版本号 / changelog / commit / tag / push，当前完全不调用 pack。若实际所指
  为后者，须在开工前重新界定范围。
- 「自动压缩」的粒度是**单个 stage 目录一个 zip**（不是把整个 `release/` 目录打成
  一个包），且只在 `--dist` 流程**全部成功**（复制、`SHA256SUMS.txt`、`--version`
  冒烟）之后触发；未传 `--dist` 时保持现有行为，不产出 zip。
- **开关定案**：只新增**一个**负向开关控制要不要 zip —— `pack/pack.sh` /
  `pack/pack.bat` 用 `--no-zip`，`pack/pack.ps1` 原生参数为 `[switch]$NoZip`
  （沿用 bat 现有的 `--onefile` → `-OneFile` 映射惯例）。**不传即默认生成 zip**；
  传 `--no-zip` 则跳过压缩，其余流程不变。
- 否决形态：不做 `--zip` / `--no-zip` 双向开关，也不做 `--zip=<true|false>` 带值
  参数——「一个参数」且默认值唯一，避免两个真值来源与无效的相反组合。

### 一、背景与现状（取证于当前工作区 HEAD）

| 现状 | 证据 |
| --- | --- |
| `--dist release` 把 PyInstaller 产物复制到 `<dist>/yate-<version>-windows-<arch>/`（Linux 为 `yate-<version>-linux-<arch>/`），写 `SHA256SUMS.txt`、跑 `--version` 冒烟，最后打印 `Collected -> <stage>` 即结束；**没有任何压缩步骤，交付物是目录** | `pack/pack.ps1:181-192,203-209,214-229,241-265`；`pack/pack.sh:164-209` |
| 版本号取 `yate/__init__.py::__version__`，stage 目录同名先删再建（重复构建会覆盖） | `pack/pack.ps1:185,190-201`；`pack/pack.sh:169,175-184` |
| 唯一的产物输出开关是 `--dist / -d / -Dist`（目录），没有 `--zip` / `--output` 之类归档开关 | `pack/pack.ps1:31-43`；`pack/pack.sh:31-62` |
| `pack.bat` 逐参数重引号并做显式映射（`--onefile` → `-OneFile`、`--dist` → `-Dist` 等），未知参数原样透传给 ps1 | `pack/pack.bat:21-44` |
| `python -m tools.pack` 只有 `icon` / `rosters` / `wiki` 三个子命令，无 release / zip | `tools/pack/cli.py:3-13,41-47` |
| 全仓唯一写 zip 的代码在 `.yxp` 扩展包（`ZipFile(..., "w", ZIP_DEFLATED)`），与发布产物无关，不可直接复用 | `tools/yxp/cli.py:224-231` |
| CI 两个配置都不调用 pack，也没有发布产物上传；唯一 artifact 是冒烟报告 | `.github/workflows/test.yml:166-178`；`.workflow/test.yml:65-72` |
| `tests/test_pack_spec.py` 已有 spec / 打包脚本级守卫，但没有覆盖 `--dist` 收集逻辑或 zip 行为 | `tests/test_pack_spec.py` |

即：目前 `--dist release` 结束后需要**额外步骤**（脚本外手工压缩或另写命令）
才能得到可分发的 zip。

### 二、目标（What）

1. **默认自动产出**：`.\\pack\\pack.ps1 --dist release`（及 `pack.bat` 透传形态、
   `./pack/pack.sh --dist release`，任意 `--dist` 目录同理）成功结束后，无需人工
   干预即生成 `<dist>/<stage-name>.zip`，例如
   `release/yate-<version>-windows-x64.zip`；终端输出 zip 路径与大小。
2. **可关闭**：传入 `--no-zip`（ps1 直接调用为 `-NoZip`）时跳过压缩，其余步骤
   （stage 复制、`SHA256SUMS.txt`、`--version` 冒烟、`Collected -> ...` 输出）与
   现有行为逐项一致；终端明确提示 zip 已跳过。不主动删除历史遗留的同名 zip，
   也不追加/修改 `<dist>/SHA256SUMS.txt` 中的 zip 条目。
3. **产物形态**：zip 与 stage 目录同名、同级；zip 内顶层保留 `<stage-name>/`
   目录，解压后目录树与当前 stage 完全一致（one-folder 的 `yate.exe` +
   `runtime/`、或 onefile 的单个可执行文件、`SHA256SUMS.txt`），不含
   `smoke-out.txt` 等临时文件。
4. **可校验**：生成 zip 时，其 SHA256 以可校验形式给出——终端打印，并在
   `<dist>/SHA256SUMS.txt` 追加 `<hash> <stage-name>.zip` 一行；不得覆盖该文件
   已有条目（多平台 / 多次构建共存），也不改变 stage 内既有
   `SHA256SUMS.txt` 的语义。
5. **可靠性**：压缩失败必须让脚本以非 0 退出并给出明确错误，且不留半截 zip
   （临时文件 + 成功后原子替换）；前置步骤（复制 / 冒烟）失败时不得产出 zip；
   重复执行按现有 stage 语义覆盖同名 zip。stage 目录默认**保留**，zip 是附加产物。
6. **跨平台一致**：Windows / Linux 两侧的开关名（各脚本自身形态）、zip 命名、
   顶层目录、压缩方式、成功/失败退出码与输出信息语义对齐；
   `pack.ps1 -Help` / `pack.sh -h` / `pack.bat --help` 均能看到新开关与
   「默认生成 zip」的说明。

### 三、约束与风险

- 不得破坏 `--dist` 现有语义：stage 目录结构、命名规则
  `yate-<version>-<os>-<arch>`、`SHA256SUMS.txt`、`--version` 冒烟 30s 超时、
  版本号单源均保持不变（`pack/pack.ps1:185-265`、`pack/pack.sh:169-208`）。
- 新增开关必须三处同步：`pack.ps1` 的 `param()` 加 `[switch]$NoZip` 与
  `.PARAMETER` / `.EXAMPLE` 注释；`pack.sh` 的 `case` 加 `--no-zip` 分支
  （未知参数仍按 `pack/pack.sh:56-59` 报错退出 2）；`pack.bat` 的解析循环加
  `--no-zip` → `-NoZip` 映射并同步头注释（`pack/pack.bat:21-39`）。
- **帮助文本的硬编码行区间**：`pack/pack.sh:26-29` 的 `show_help` 用
  `sed -n '2,19p'` 截取头注释；新增 usage 行后必须同步调整该区间，否则新开关
  不会出现在 `-h` 输出里（验收需覆盖）。
- **Linux 可执行位是硬要求**：`pack/pack.sh:189` 的 `chmod 0755 yate` 必须体现在
  zip 解压结果里；标准库 `zipfile` 默认不写 Unix mode，需显式处理
  `external_attr`，否则发布包解压后不可运行。
- 不引入新的第三方依赖，也不要求预装 `zip` / 7-Zip 等系统工具；优先复用脚本
  已有的 `.venv` Python + 标准库 `zipfile`。若 Windows 侧选 `Compress-Archive`，
  需评估其 2 GB 上限与跨平台实现分叉，并在方案中说明。
- 若两平台分别实现，须有测试保证开关行为一致；若抽取共享 Python 助手，须落在
  `tools/` 或 `pack/` 且遵守 pyright strict、无 `Any` / `TYPE_CHECKING` /
  相对导入、注释与 docstring 全英文（`misc-rules.md` §四）。
- onefile / one-folder 在同一平台产出同名 stage，压缩沿用「先删再建」的覆盖
  策略，不额外做版本化命名。
- 若同步公开 `--dist` / `--no-zip` 用法到 README，须 `README.md` +
  `README.zh.md` 双语同步。

### 四、验收标准

1. **参数矩阵（Windows，均以 `.venv\\Scripts\\python.exe` 环境执行）**：
   - `.\\pack\\pack.ps1 --dist release` → 生成 zip；
   - `.\\pack\\pack.ps1 -NoZip --dist release` → 不生成 zip，stage /
     `SHA256SUMS.txt` / 冒烟 / 终端 `Collected ->` 与改动前一致，且提示已跳过；
   - `.\\pack\\pack.bat --dist release` → 生成 zip；
     `.\\pack\\pack.bat --no-zip --dist release` → 与 `-NoZip` 等效；
   - `.\\pack\\pack.ps1 -Help`、`.\\pack\\pack.bat --help` 输出包含 `-NoZip` /
     `--no-zip` 与「默认生成 zip」说明；
   - 未带 `--dist` 时，无论是否传 `-NoZip` 都不产出 zip。
2. **参数矩阵（Linux）**：`./pack/pack.sh --dist release` → 生成 zip；
   `./pack/pack.sh --no-zip --dist release` → 不生成；
   `./pack/pack.sh -h` 显示新开关；`./pack/pack.sh --zip` 等未知参数仍按现有
   规则报错退出 2。
3. **Windows 真实构建产物校验**：`Expand-Archive` 解压 zip 到临时目录后，目录树
   与 stage 逐项一致、含 `SHA256SUMS.txt`、无 `smoke-out.txt`；
   `Get-FileHash -Algorithm SHA256` 与 `<dist>/SHA256SUMS.txt` 中该 zip 条目
   一致；`& <解压目录>\\yate.exe --version` 输出与 `yate.__version__` 相同；
   stage 目录仍存在且其 `SHA256SUMS.txt` 内容不变。
4. **Linux 同构验证**：`python -m zipfile -t <zip>`（或 `unzip -t`）通过；解压后
   `test -x yate` 成立、`./yate --version` 输出正确；zip 命名 / 顶层目录 /
   校验条目与 Windows 侧约定一致。若本轮无法在两平台都跑完整 PyInstaller
   构建，至少一平台做真实构建，另一平台由脚本级用例 + 静态守卫覆盖，并在
   方案中记录偏离理由。
5. **失败与边界**：用可控桩模拟压缩失败（目标不可写 / 压缩过程抛错），断言
   非 0 退出、无残留半截 zip、错误信息可读；冒烟失败路径不得产出 zip；
   `--no-zip` 且 dist 根已存在上次构建的同名 zip 时，不删除、不修改该 zip 且
   提示已跳过；重复执行默认模式覆盖同名 zip 且不重复追加校验条目。
6. **回归用例**：`tests/test_pack_spec.py` 新增守卫——三个脚本均声明 / 映射
   新开关、默认值为生成 zip、`--no-zip` 分支跳过压缩、`pack.sh` 帮助行区间
   覆盖新增 usage、`--dist` 与冒烟语义不回归；执行
   `.venv\\Scripts\\python.exe -m pytest tests/test_pack_spec.py -q`。
7. **全量门禁**（与仓库总纲同口径，全部退出码 0）：
   `.venv\\Scripts\\python.exe -m pyright yate/ tests/ tools/ pack/`、
   `.venv\\Scripts\\python.exe -m pytest tests/ -q -n auto`、
   `.venv\\Scripts\\python.exe -m pytest tests/test_architecture.py -q`
   （37 用例）、
   `.venv\\Scripts\\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto`
   （`--cov-fail-under=75`）、
   `.venv\\Scripts\\python.exe -m tools.smoke_test run --jobs 4`；
   若改 README，追加 `python -m tools.changelog check`。

### 五、非目标

- 不改 `python -m tools.release`（版本 / changelog / tag / push），不自动上传
  release 附件、不改发布流程编排；
- 不给 `python -m tools.pack` 新增 `release` / `zip` 子命令（现有 `icon` /
  `rosters` / `wiki` 保持不变）；
- 不做 `--zip` 正向开关、带值参数或配置文件开关；开关默认值不可通过
  环境变量 / rc 覆盖（避免默认值来源扩散）；
- 不改 `.yxp` 扩展包格式与 `tools/yxp/cli.py`；
- 不在 CI 新增打包矩阵 / 产物上传（当前 CI 不跑 pack，另案）；
- 不改 PyInstaller spec 与 onefile / one-folder 产物结构，不改 `--dist` 目录
  语义，不删除 stage 目录，不引入新第三方依赖；
- 不做签名 / 公证、不做增量或分卷压缩、不做多平台产物合并归档。

### 六、预估涉及文件

| 文件 | 改动 |
| --- | --- |
| `pack/pack.ps1` | `param()` 加 `[switch]$NoZip`；头注释 `.PARAMETER` / `.EXAMPLE` 说明默认生成 zip；收集 + 冒烟成功后按开关生成 zip（临时文件原子替换、失败退出）、zip 校验值输出 |
| `pack/pack.sh` | `case` 加 `--no-zip`；Linux 同构 zip 实现，显式保留 `yate` 可执行位；同步 `show_help` 的 `sed` 行区间与头注释 |
| `pack/pack.bat` | 解析循环加 `--no-zip` → `-NoZip` 映射，头注释列出新示例 |
| `tests/test_pack_spec.py` | 新增开关默认值 / 映射 / 跳过语义 / 帮助文本 / zip 命名 / 顶层目录 / 失败清理守卫 |
| `tools/` 或 `pack/`（可选） | 若抽取共享压缩助手，按架构与编码规则落地并补测 |
| `README.md` / `README.zh.md`（可选） | 若公开 `--dist` / `--no-zip` 用法，双语同步 |

## 三、【领会】补充的只读事实（不分析）

- `pack/pack.ps1` 共 271 行；`param()` 位于 31-43 行；`--dist` 收集块位于
  175-266 行，末尾输出 `Collected -> ...` 与 `SHA256 yate.exe`；冒烟临时文件
  `smoke-out.txt` 在成功路径被 `Remove-Item`（260 行）。
- `pack/pack.sh` 共 209 行；`show_help()` 位于 26-29 行（`sed -n '2,19p'`）；
  参数 `case` 位于 35-62 行；`--dist` 收集块位于 164-209 行；stage 内
  `SHA256SUMS.txt` 由 `( cd "$stage" && sha256sum yate > SHA256SUMS.txt )` 生成
  （195 行）；Linux stage 可执行文件名为 `yate`，onefile 模式在 189 行
  `chmod 0755`。
- `pack/pack.bat` 共 45 行；解析循环 `:parse` 位于 28-41 行；头注释 2-13 行。
- `tests/test_pack_spec.py` 共 685 行，已有 `_REPO_ROOT` / `_COMMON_PATH` /
  `_SPECS` 等静态守卫常量与 `_parse` / `_load_common` 辅助；当前不含任何
  `--dist` / zip 相关断言。
- 规则约束：`.trae/rules/` 8 份必读规则已全文加载；`architecture-boundaries.md`
  §三.7 单文件 800 行阈值；`misc-rules.md` §四 代码注释 / docstring 全英文；
  `doc-conventions.md` §五 文档内引用仓库文件用相对路径、真实本机路径脱敏。
