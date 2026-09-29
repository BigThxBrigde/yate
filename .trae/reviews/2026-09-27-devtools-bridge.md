# yate Code Review — 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27

## 日志/devtools 桥接评审（fix/logging-tracing-wt）— 2026-09-27

> **范围**：分支 `fix/logging-tracing-wt` 相对 master 的 3 个提交（`003263e` 驱动日志改
> tracing + 删 `App` 导入；`a35a133` R12 规则 + TextualHandler 桥 + 2 AST 守卫；
> `036bd2a` 桥改挂 `on_mount`/`on_unmount` 生命周期），2 名独立验证子代理交叉复核，
> 4 项发现全部 2/2 确认。用户裁定后 4 项全修（其中问题 2 按用户指示升级为**真开关
> 闸门**：tracing 禁用时 devtools 一并禁用），分 4 笔提交：`44972c9` `5d3399d`
> `e754b27` `905385f`。**总判定：无致命/严重问题，全部为建议级。**

- [x] **守卫 docstring 挂载点过期（Minor）** —
  [test_architecture.py:395](../../tests/test_architecture.py#L395)
  `test_logging_never_touches_devtools_channel` 仍写 bridge 挂载于 `YateApp.__init__`，
  而 `036bd2a` 已移至 `on_mount`。
  *✅ 已修复（2026-09-27，`44972c9`）——docstring 改为 `on_mount`，与 R12 文档一致。*

- [x] **「tracing 未开启时零输出/桥不参与」声明过强（Major，用户指示升级为真闸门）** —
  [app.py](../../yate/app.py) / [architecture-boundaries.md](../rules/architecture-boundaries.md)
  未配置的 `yate` logger level 为 NOTSET → 有效级别继承 root 的 WARNING，tracing 关闭时
  WARNING+ record 仍会到达 TextualHandler 并（devtools 连接时）转发——原「零成本保证」
  声明与事实矛盾。
  *✅ 已修复（2026-09-27，`5d3399d`）——按用户指示做成**真开关**：挂载的桥改为
  `_TracingGatedTextualHandler`，`emit` 先查 `tracing.is_enabled()`，tracing 禁用即
  devtools 禁用（YATE_TRACE 是 yate 诊断的唯一开关）。闸门放 handler 层而非 logger 层：
  改 logger 级别会破坏 `yate.services.extensions` 子 logger 的测试捕获语义。守卫
  `test_devtools_bridge_forwards_only_while_tracing_enabled` 经真实挂载路径取桥实例，
  双重实证「挂的就是带闸子类 + 双态转发行为」；R12 文档「零成本保证」节改写为「闸门
  语义」。*

- [x] **`on_unmount` 摘除全部 TextualHandler 而非本实例的（Minor）** —
  [app.py on_unmount](../../yate/app.py)
  同进程多 App 实例交替时（先挂未卸→后挂去重未再挂），先卸载者会误摘仍在运行实例的桥。
  *✅ 已修复（2026-09-27，`e754b27`）——桥存 `self._devtools_bridge`，`on_unmount`
  按身份摘除本实例所挂 handler（多实例互不误摘）；`on_mount` 重挂载前防御性摘旧防
  泄漏。R12 文档同步记录身份语义。*

- [x] **桥生命周期守卫的无必要 win32 skip（Minor）** —
  [test_architecture.py](../../tests/test_architecture.py)
  `test_devtools_bridge_follows_app_lifecycle` 带 `sys.platform != "win32"` skip，但
  `run_test` 用平台无关的 HeadlessDriver，不触及 Windows 控制台驱动。
  *✅ 已修复（2026-09-27，`905385f`）——删除 skip（注释说明平台无关性），清理 `sys`
  导入；Linux/macOS 同样可跑。*

### 过程记录（防重蹈）

- **pyright strict 初版抓出 10 诊断**（闸门测试首版）：`pytest` 未在模块顶部导入、
  私有类 `_TracingGatedTextualHandler` 跨模块引用、lambda 参数类型未知——重构为经
  公开挂载路径取真实桥实例 + 顶部导入 + 具名函数，全部消除。
- **验证子代理读主仓路径误报**：一名验证员称 app.py「未见挂载逻辑」——实为读到了
  主仓 `d:\Programming\yate`（无此改动）而非 worktree。交叉复核时须显式钉死
  worktree 绝对路径。
