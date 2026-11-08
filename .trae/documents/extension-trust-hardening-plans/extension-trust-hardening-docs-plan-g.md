# 子计划 g — 双语文档同步：信任模型 / 包 / shell / 依赖 / 诊断（wave-3）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[issue](../extension-trust-hardening-issue.md)、
> [inventory](../extension-trust-hardening-inventory.md) 各文档章节行号。
> 只改 8 个文档文件；纯文档子计划，按 `misc-rules.md` §三 说明豁免口径
>（整任务含代码，最终全量门禁仍由主代理步骤 7 统一执行）。

## 一、目标与非目标

- 目标：把 wave-1/2 的真实行为同步到中英双语用户文档，并补上 S-06 / S-08
  的文档澄清与另案登记；文案必须与实现一致，不得承诺未实现能力。
- 非目标：不改 `pyproject.toml` / CI / 打包工具 / 任何代码；不新建文档；
  不写本机绝对路径；不批量清扫存量文档路径。

## 二、独占文件清单

1. `yate/docs/extensions.en.md`
2. `yate/docs/extensions.zh.md`
3. `yate/docs/themes.en.md`
4. `yate/docs/themes.zh.md`
5. `yate/resources/manual.en.md`
6. `yate/resources/manual.zh.md`
7. `README.md`
8. `README.zh.md`

## 三、逐文件改动（章节锚点来自 inventory）

### 3.1 `yate/docs/extensions.en.md` / `.zh.md`

- **Trust model**（en `:134-157` / zh `:118-137`）：保留现有「trusted code /
  未裁剪 Lua 5.4 / 无沙箱」表述；在门控列表之后新增一段：
  - en: "Trust is a permanent grant for a **resolved directory path**, not for
    its contents. Replacing a trusted workspace (re-clone, shared directory,
    a new `*.py` / `*.lua` file) still auto-loads its code. Remove the matching
    line from `~/.yate/trusted_workspaces` to revoke it. A trust store that is
    itself a symlink is ignored; on POSIX the store permissions are best-effort
    and a chmod failure is logged, while Windows ACL hardening is not applied
    yet (tracked separately)."
  - zh 对应中文镜像（同一段落、同样要点，不得漏项）。
  - 明确本节与 Lua 章节的交叉引用（一句即可）。
- **§7 Extension packages**（en `:1096-1169` / zh `:999-1066`）：
  - `checksum` 条目：格式上仍可选，但**安装默认要求**；官方打包器总是写入。
  - 安装示例增补 `yate --install-extension FILE --allow-unverified`，并说明
    该开关仅用于自己构建、确认无误但没有 checksum 的包。
  - "What install does" 增补一条：缺 checksum 的包在写盘前被 `YxpError` 拒绝；
    `:install-extension` 命令不提供放宽开关（用 CLI）。
  - "Security notes" 首条补一句：**安装 `.yxp` 等于安装可执行代码**
    （顶层 `*.py` / `*.lua` 下次启动自动加载）；把原
    "Packages without a `checksum` member install unverified" 改为
    "are rejected by default; `--allow-unverified` opts in"，并保留
    "`--verify` 只校验完整性、不是签名" 的结论。
- **Shell / Lua API 章节**（先 grep `api.shell` / `yate.shell` 定位；en 约
  `:1233-1251` 附近为 manual，docs 内另有 API 表）：新增一句：
  `:!` / `api.shell(cmd)` / `yate.shell(cmd)` 是完全权限接口，字符串直接交给
  系统 shell；`api.shell_argv(argv)` / `yate.shell_argv(argv)` 使用 argv 向量、
  不解释 shell 元字符，但仍以当前用户权限运行程序。中英同步。
- **Lua 章节**（en `:897` / zh `:820` 起）：加一句「Lua 与 Python 扩展同为
  完全受信任代码，运行时不是沙箱」，指向 Trust model。

### 3.2 `yate/docs/themes.en.md` / `.zh.md`

- "Workspace themes and trust" 章节（en `:308-317` / zh `:288-296`）补一句：
  主题信任与扩展信任共用同一永久路径授权；替换受信任工作区内容不会撤销信任；
  详见扩展指南 Trust model。中英同步，不重复写完整段落。

### 3.3 `yate/resources/manual.en.md` / `.zh.md`

- `--diag` 选项（en `:90` / zh `:88`）与示例（en `:108` / zh `:106`）附近：
  说明报告为本机诊断设计，含绝对路径、`sys.executable` / `sys.prefix` 与
  终端环境变量，贴到 issue 前请复核；开启 tracing 时本地 trace 文件还会记录
  完整 `sys.argv` 与 cwd。报告头本身也有 privacy note。中英同步。
- Lua 支持段落（en `:1305-1311` / zh `:1173-1177`）：明确「Lua 扩展与 Python
  扩展同一信任级别：未裁剪 Lua 5.4 运行时，标准库 `io` / `os` / `package` /
  `debug` 与 Python 桥接可用，没有沙箱、没有 API 白名单」。
- Shell Integration（en `:1233-1251` / zh `:1112-1126`）：在
  `api.shell(cmd)` 行后补完全权限说明 + `api.shell_argv(argv)` / Lua
  `yate.shell_argv(argv)` 用法（含「无 shell 元字符解释，但仍是完全权限」）。
- `:trust` 章节（grep `:trust`）：补永久路径授权说明与 store 位置；不承诺
  内容指纹 / 自动过期。
- `:install-extension` 命令条目（grep 命令表）：补「缺 checksum 默认拒绝；
  需放宽请用 CLI `--allow-unverified`」。

### 3.4 `README.md` / `README.zh.md`

- "Requirements / 环境要求"（en `:60-64` / zh `:87-92`）增补依赖供应链政策：
  运行时依赖只声明下界，仓库不提交 lockfile，CI 未接入 `pip-audit` /
  `osv-scanner`；需要可复现 / 可审计安装时自行生成带哈希的锁文件并在发布前
  本地做 SCA。明确这是**已知限制、已登记另案**，不是「已加固」。中英同步。
- "Bilingual project wiki generator / 双语项目 Wiki 生成"（en `:491-517` /
  zh `:485-508`）的 `--translate-cmd` 条目改写为显式警告：该参数经系统 shell
  执行，**等价于任意命令执行**；只传自己编写的命令，不要来自下载的配置、
  脚本或不可信输入。保留 stdin/stdout 协议描述。中英同步。

### 3.5 文档规范

- 引用仓库内文件一律相对路径；不得出现盘符 / 用户目录 / 仓库根绝对路径。
- 中英两份章节结构对齐、要点一一对应；语言各自自然，不机翻。
- 文件名不改；`README.md` / `README.zh.md` 根级命名不动。
- 注释 / 代码块里的命令示例用可移植写法，不写本机真实路径。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m tools.mdlint --auto-lang --check README.md README.zh.md yate/docs/extensions.en.md yate/docs/extensions.zh.md yate/docs/themes.en.md yate/docs/themes.zh.md yate/resources/manual.en.md yate/resources/manual.zh.md
.venv\Scripts\python.exe -c "from pathlib import Path; pairs=[('yate/docs/extensions.en.md','yate/docs/extensions.zh.md','--allow-unverified'),('yate/resources/manual.en.md','yate/resources/manual.zh.md','shell_argv'),('README.md','README.zh.md','pip-audit')]; [(print(a, b, key, key in Path(a).read_text(encoding='utf-8'), key in Path(b).read_text(encoding='utf-8'))) for a,b,key in pairs]"
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py tests/test_changelog_view.py -q
.venv\Scripts\python.exe -m tools.changelog check
```

通过判定：mdlint 退出码 0（若命中**存量**违规，须在报告中逐条列出且不得
顺手改无关章节）；双语锚点检查三对全为 `True`；相关测试与 changelog check
退出码 0。纯文档子计划在此不跑 pyright / 全量 pytest，由步骤 7 统一门禁。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 文案承诺未实现能力（如「已签名」「已沙箱」） | 逐条对照 wave-1/2 实际 diff 写；S-04/S-06/S-08 明确写「另案 / 未加固」 | `git checkout -- <8 个文档>` |
| `manual.*.md` 是打包资源，改动影响冒烟基线 | 收尾跑冒烟；不删既有章节、只增补 | 同上 |
| mdlint 命中存量违规 | 只报告不批量修；新增段落遵守规则 | 同上 |
| 中英不同步 | 锚点脚本 + 人工逐点核对 | 补齐缺失一侧 |

## 六、报告格式

改动清单（文件 + 新增段落主题）、实跑命令与退出码、mdlint 存量命中清单
（如有）、双语锚点结果、未解决项与原因。
