# Plan A — 主题广播基建：`theme.py` 订阅/派发机制

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 独占文件：`yate/editor_view/theme.py`、`tests/test_theme_subscribe.py`
> 门禁：`pytest tests/test_theme_subscribe.py -q` → **4 passed**；`pyright yate/ tests/ tools/` → 0 诊断

---

## A.1 背景

重构前 `theme.set_theme()` 只改进程级全局 `_active` 后直接返回——**没有任何通知机制**
（总纲 F7）。各组件要么靠 L3 `apply_theme` 被动刷（T2 张力的根源），要么在挂载时读一次
就再也不更新。要让组件自持主题（Plan C），`theme.py` 必须先提供"主题变了"的广播原语。

## A.2 交付物

| 符号 | 形态 | 职责 |
|---|---|---|
| `subscribe(listener) -> Callable[[], None]` | 函数 | 注册监听者并返回**退订函数**；退订幂等（重复移除不抛 `ValueError`），组件 `on_unmount` 无需协调 |
| `_listeners: list[Callable[[], None]]` | 模块级列表 | 订阅者容器（非导出符号） |
| `_notify()` | 函数 | `set_theme` 成功后同步派发：逐个 try/except 隔离，单个订阅者异常记 `log.warning` 不中断广播 |
| `set_theme(name)` | 函数（扩展） | 校验 + 更新 `_active` 后追加 `_notify()` 调用；未知主题先 `raise KeyError`，**不通知** |

设计约束对齐：

- **回调列表而非 EventBus**（规则四"1:N 低频广播 → 回调列表"白名单机制）：同线程同步派发、
  无字符串事件名、无全局总线。
- `log = tracing.get_logger(__name__)`（项目日志规范；`%` 占位惰性格式化）。
- `collections.abc.Callable` 导入（pyright strict 完整注解要求）。

## A.3 设计要点

1. **退订函数由 `subscribe` 返回**，组件持有为 `_theme_unsubscribe` 属性（Plan C 的统一模式），
   避免暴露 `_listeners` 给外部删除遍历。
2. **异常隔离在 `_notify` 内**：一个坏订阅者不得阻塞其余订阅者（vim 的 colorscheme 切换
   永远不该被单个 widget 的 bug 卡死）；异常吞掉但记日志，不静默。
3. **失败不通知**：`set_theme` 对未知主题先抛 `KeyError`，广播只发生在"真的切换了"之后——
   订阅者不需要处理"切换失败"的幻影事件。
4. **广播时机 = 状态更新之后**：订阅者回调里读 `theme.active()` 一定拿到新主题，
   不存在"收到通知但读到旧值"的竞态。

## A.4 验收证据（`tests/test_theme_subscribe.py`，4 用例）

| 用例 | 断言 |
|---|---|
| `test_subscribe_listener_notified_on_set_theme` | 订阅后两次 `set_theme` 各触发一次回调 |
| `test_unsubscribe_stops_notifications_and_is_idempotent` | 退订后不再触发；二次退订是 no-op 非 `ValueError` |
| `test_failing_listener_does_not_block_broadcast` | 订阅者抛 `RuntimeError`，其后的订阅者仍收到回调 |
| `test_failed_set_theme_does_not_notify` | 未知主题抛 `KeyError` 且订阅者零回调 |

实测：`pytest tests/test_theme_subscribe.py -q` → **4 passed**。

## A.5 测试卫生

所有用例 `finally` 中退订 + `set_theme("mocha")` 复位——主题是**进程全局状态**
（textual-pilot-smoke skill 的已知坑），必须防止用例间泄漏。
