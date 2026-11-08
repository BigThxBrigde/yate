# IKTF4Y 素材整理（扩展执行边界与信任模型，8 项发现）

> 本文件只整理 issue 文本、约束与上下文，不做任务分析；任务分析与方案设计归
> 【方案】环节。来源：<https://gitee.com/jermaine/yate/issues/IKTF4Y>
> （Gitee API v5 取回正文，2026-11-07 抓取；issue 状态「待办的」，评论 0 条）。

## 一、环境基线（本任务）

- worktree：`yate-extension-trust-hardening`（相对主工作区同级目录）
- 分支：`feature/enh-extension-trust-hardening`，parent = `develop` @ `af81d11`
  （已与 `origin/develop` 同步，`rev-list --left-right --count` = `0 0`）
- 审计日期：2026-11-06；审计方式：源码静态审计，未执行代码 / 未跑门禁 / 未做 SCA
- 定级前提：yate 为本地 TUI 编辑器，「用户主动安装 / 配置的代码即受信任代码」是现行设计；
  多数条目属权限边界与信任模型问题，未发现可直接远程触发的 RCE

## 二、发现清单（issue 原文摘要）

| # | 问题 | 严重度 | 优先级 | 主要证据 |
|---|---|---|---|---|
| S-01 | Lua 扩展运行时非沙箱，注释措辞易误读 | 中高 | P1 | `yate/services/extensions/lua/runtime.py:111-113` |
| S-02 | `.yxp` 包无来源认证、checksum 可选，安装即执行代码 | 中 | P1 | `yate/services/yxp/manifest.py:185-192`、`install.py:77-82` |
| S-03 | `shell=True` 完全权限接口暴露给扩展 API | 中（设计使然） | P2 | `yate/services/shell.py:74-84` |
| S-04 | trust 为永久路径字符串，读侧宽于写侧 | 中低 | P2 | `yate/services/trust.py:104-119` |
| S-05 | `api.data` 词法校验未防符号链接 | 低中 | P2 | `yate/services/data_store.py:69-73` |
| S-06 | 依赖无上界、无 lockfile/哈希 | 低 | P3 | `pyproject.toml:12-15` |
| S-07 | 诊断/日志泄露本机路径与 argv | 低 | P3 | `yate/cli.py:466`、`diagnostics.py:241-245` |
| S-08 | 构建工具 `shell=True` | 低 | P3 | `tools/pack/wiki/translate.py:251-253` |

### S-01（P1 / 中高）

- 现状：`create_runtime` 用 `lupa.lua54.LuaRuntime(unpack_returned_tuples=True)`，
  未传 `register_builtins=False`，未设 `attribute_filter` / `max_memory`，未裁剪 Lua 标准库；
  lupa 默认开放 `io` / `os` / `package` / `debug` 并暴露 Python 桥接。
  模块注释 "no package.path entry and no Lua-side file I/O" 只说明未把内置 lib 挂进
  `package.path`，不等于禁用文件 I/O；「每个扩展一个 runtime」只是扩展间隔离。
- 影响：第三方 `.lua` 扩展可读写任意文件、执行系统命令、经 Python 桥接逃逸，权限与 `.py` 等价。
- 附注：`runtime.py:77` 把 `chunkname` 用 f-string 拼入 Lua 字符串字面量；当前来源为常量或经
  `_MODULE_NAME_RE` 校验，暂无注入，未来放宽命名即成注入点。
- 建议（二选一）：① 手册明确声明 Lua 与 Python 扩展同为完全受信任代码，并修正该注释；
  ② 若定位低信任脚本，显式移除 `io`/`os`/`package`/`debug`/`python` 全局，加
  `attribute_filter` 与 `max_memory`。
- 建议验证（未实测）：临时 `.lua` 扩展调用 `os.execute` / `io.open` 写文件，用 `--ext` 加载观察。

### S-02（P1 / 中）

- 现状：`checksum` 成员可选，缺失时仅 `log.warning` 后继续安装；digest 表与 payload 同处
  一个归档且无签名，替换两者即可通过校验；写盘二次 digest 校验防 TOCTOU，不防伪造包。
- 影响：安装目标 `~/.yate/extensions` 是启动扫描目录，顶层 `*.py` / `*.lua` 会被
  `exec_module` 执行，安装 `.yxp` 等价于执行任意代码；CLI 接受任意本地路径，无发布者 / 指纹确认。
- 建议：缺 `checksum` 默认拒绝并提供显式 `--allow-unverified`；引入签名，或至少打印指纹二次确认；
  手册标注 `.yxp` 为可执行代码包。

### S-03（P2 / 中，设计使然）

- 现状：`:!` 命令与 `api.run_shell` / `api.shell` 直接把字符串交给系统 shell；元字符按设计透传。
  静态扫描未发现把文件名 / 路径自动拼进命令的调用点，不是「打开恶意文件名即执行」的注入。
- 残余风险：`cwd` 取自 workspace root / 当前文件目录；扩展可无确认调用该接口。
- 建议：文档明确其为完全权限接口；为扩展 API 提供 argv 形态（`shell=False`）变体或显式确认。

### S-04（P2 / 中低）

- 现状：项目 rc / `./themes` / `./extensions` 三处均已正确接入 trust 闸门（正面）；但
  `is_trusted` 只比较 `root.resolve()` 是否在集合中，无内容指纹 / 过期 / 二次确认；
  `trust_workspace` 拒绝 symlink root 只保护写入侧，读侧对每条记录一律 `.resolve()`；
  `chmod` 失败被 `suppress(OSError)` 静默吞掉，Windows 分支无 ACL 加固。
- 影响：被 `:trust` 的目录内容被替换后新内容自动执行；能写 `~/.yate/trusted_workspaces`
  的本地攻击者可把任意目录标为可信（前提：已有 home 写权限）。
- 建议：trust 记录目录内容指纹，或对新增可执行文件二次确认；Windows 用 ACL；`chmod` 失败显式告警。
- 另注：`yaterc.py:193-195` 与 `theme/files.py:103-106` 对用户文件 `compile` + `exec` 属
  vimrc 式设计；`-u` / `--ext` / `--theme-dir` 无条件加载为明确主动行为，均不单列缺陷。

### S-05（P2 / 低中）

- 现状：`resolve()` 已拒绝空名、绝对路径、盘符、反斜杠、`..`，并有 `is_relative_to(root)`
  二次校验；但未对 `target.resolve()` 做真实路径校验。
- 影响：若 `~/.yate/data` 下存在指向外部的符号链接，`write_text("link/x", ...)` /
  `remove()` 可写到或删除根目录之外。
- 建议：对 `target.resolve()` 再做一次 `is_relative_to(root.resolve())`，或复用
  `yate/services/yxp/install.py:130-142` 的逐段 symlink 检查。

### S-06（P3 / 低）

- 现状：`textual>=8.0`、`pyperclip>=1.8.2`、`lupa>=2.0`、`pyinstaller>=6.0` 无上界；
  除 `tree-sitter>=0.24,<0.26` 外多数 grammar 包无上界；仓库无 lockfile、无 `--require-hashes`。
- 建议：提交 lockfile，CI 接入 `pip-audit` / `osv-scanner`。外部聚合站出现的 lupa 相关
  未核实条目未纳入评级，请以 SCA 实测为准。

### S-07（P3 / 低）

- 现状：tracing 开启时记录完整 `sys.argv` 与 cwd；`--diag` 报告按设计「适合贴到 issue」，
  会带出 `sys.executable`、`sys.prefix`、`~/.yate` 绝对路径与部分终端环境变量。
  脱敏为固定白名单（`_TERMINAL_ENV` 四项 + `WT_SESSION` opaque），机制本身安全。
- 建议：`--diag` 输出对本机路径做脱敏或加提示。

### S-08（P3 / 低）

- 现状：为支持管道走 shell，`translate_cmd` 来自维护者 CLI 参数，非外部不可信输入。
- 建议：仅在文档中标注「该参数等价于命令执行」，无需改代码。

## 三、已确认的正面防护（issue 明确要求避免误判）

- `.yxp` 解包：拒绝反斜杠 / 盘符 / 绝对路径 / `..` / 保留目录、重复与大小写碰撞、
  总载荷 128MB 上限、流式读且不信任 `ZipInfo.file_size`、写盘二次 digest 校验、
  逐段 symlink 检查、失败完整回滚、`os.replace` 原子写记录。仅存 TOCTOU 窗口与
  重复成员名未显式拒绝两个小缺口，不构成绕过。
- LSP / 终端启动均用 argv（`create_subprocess_exec` / `Popen` 向量），无 shell 拼接。
- 无不安全反序列化（`pickle` 仅 smoke harness 的 `dumps` 可序列化性探测）。
- 无硬编码凭据（密钥模式扫描仅命中测试假值）。
- 自动执行防护到位：项目 rc / `./themes` / `./extensions` 三处均有 trust 闸门。

## 四、审计范围与局限（issue 原文）

- 覆盖 `pyproject.toml`、`yate/` 主包重点模块、`tools/` 危险模式扫描。
- 未逐行审计：`pack/` 的 PyInstaller `.spec`、`yate/extensions/*.lua` 业务逻辑、
  `editor_components/filemgr/` 与 hexview 路径处理、`services/workspace.py` 全文、
  `logs.py` 崩溃报告头、`tests/` 与 `tools/` 其余文件。
- 未执行任何代码、pyright / pytest / 架构门禁、依赖 SCA、CVE 库核对、动态 PoC。
- 未发现可直接远程触发的 RCE。

## 五、issue 建议验收标准（原文）

1. S-01：扩展手册明确 Lua 权限定位，`runtime.py` 注释不再暗示「无 Lua 文件 I/O」；
   若走沙箱路线，新增守卫用例断言 `io` / `os` / `package` / `debug` / `python` 全局不可用。
2. S-02：无 `checksum` 的 `.yxp` 在默认参数下被拒绝，新增回归用例覆盖「允许」开关。
3. S-05：`api.data` 对符号链接路径的写入 / 删除被拒绝，新增用例覆盖。
4. 全量门禁照常通过：`pyright yate/ tests/ tools/ pack/`、`pytest tests/ -q -n auto`、
   `pytest tests/test_architecture.py -q`。
