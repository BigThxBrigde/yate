# SP5 — 服务与日志健壮性（S5 + S11 + S33 + S34 + S36 + S39 决策门）

> 来源：[P1 批次二（S5）](../P1_suggestions_plan.md)、[批次五（S11）](../P1_suggestions_plan.md)、
> [批次六（S33/S34/S36/S39）](../P1_suggestions_plan.md)。统一门禁见 [README §五](README.md)。

## 条目

| 条目 | 证据锚点 | 内容 | 规模 |
|---|---|---|---|
| S5 | [logs.py:278-280](../../../../yate/logs.py) | `_original_excepthook` 在 import 期捕获，uninstall 会覆盖他人后装的 hook | S |
| S36 | [logs.py:396-401、:522-523](../../../../yate/logs.py) | 崩溃报告 / trace 文件名秒级碰撞（`"w"` 模式互毁） | S |
| S11 | [workspace.py:244-272](../../../../yate/services/workspace.py) | `walk_files` 递归深度无上限（`limit` 只限文件数）；`visible_tree` 递归且无 symlink 环防护 | M |
| S33 | [extensions.py:389-423](../../../../yate/services/extensions.py) | 失败扩展模块残留 `sys.modules` | S |
| S34 | [extensions.py:290-301](../../../../yate/services/extensions.py) | `bind_key` 的 keymap 名拼错静默无绑定 | S |
| S39 | [trust.py](../../../../yate/services/trust.py) | symlink 重定向即可改变信任对象 | L（**先定方案**） |

## 独占文件清单（只许改这些）

- `yate/logs.py`
- `yate/services/workspace.py`
- `yate/services/extensions.py`
- `yate/services/trust.py`
- `tests/test_crash.py`、`tests/test_tracing.py`、`tests/test_workspace_filter.py`、
  `tests/test_extensions.py`、`tests/test_trust.py`（新增用例）

## 实施步骤

1. **第 0 步 复核**：六条锚点逐一确认（重点 S11：`limit` 参数现状、`visible_tree`
   是否仍无 symlink 防护；S39：store 匹配逻辑现状）。
2. **S5**：`sys.excepthook` 捕获延迟到 `install()` 首次调用；`uninstall()` 恢复到
   install 时刻的值；构造函数不再触碰 `sys.excepthook`。
   验收：安装前伪造自定义 hook → install → uninstall → 还原为伪造 hook。
3. **S36**：`build_err_path` 与 trace 文件名追加 pid（`crash-YYYYMMDD-HHMMSS-<pid>.err`）
   或改微秒精度（二选一，报告注明）。
   验收：monkeypatch 时钟固定同一时刻，两次调用路径不同。
4. **S11**：`walk_files` 与 `visible_tree` 改显式栈迭代；**逐层排序行为必须与现有
   测试基线一致**（目录优先、`name.lower()`）；`visible_tree` 补与 `walk_files` 相同的
   symlink 环防护。验收：现有 `test_workspace_filter` 顺序断言全绿；新增 1500 层深链
   目录不炸、指向祖先的 symlink 不栈溢出。
5. **S33**：`exec_module` 异常分支先 `sys.modules.pop(module_name, None)` 再记录错误。
   验收：import 即抛错的扩展 → 模块名不在 `sys.modules`。
6. **S34**：未命中 keymap 名时 `log.warning`（或 `api.message` 提示），列出可用名。
   验收：以不存在的 keymap 名调用 → 出现警告且不抛异常。
7. **S39 决策门（波次三启动前由主代理裁决）**：
   - 彻底修复需改存储策略（落盘真实路径 / inode 校验 / `:trust` 拒绝写入 symlink 路径），
     改动面大且**需同步调整**现有归一化行为守卫
     `test_startup_treats_a_literal_symlink_entry_as_its_resolved_root`；
   - **默认本轮只做最小加固**：`:trust` 写入前 resolve 并拒绝 symlink 条目；
   - 无论选哪档，先在报告中写明方案再动手。
8. **子代理门禁**：
   ```Shell
   .venv\Scripts\python.exe -m pyright yate/logs.py yate/services tests/test_crash.py tests/test_tracing.py tests/test_workspace_filter.py tests/test_extensions.py tests/test_trust.py
   .venv\Scripts\python.exe -m pytest tests/test_crash.py tests/test_tracing.py tests/test_workspace_filter.py tests/test_extensions.py tests/test_trust.py -q
   ```

## 注意

- S11 改迭代是本子计划唯一动排序语义风险点：先跑 `test_workspace_filter.py` 固化基线，
  再动手。
- logs.py 同文件两处（S5/S36）先做 S5 后做 S36，避免 uninstall 语义与命名改动交叉。
