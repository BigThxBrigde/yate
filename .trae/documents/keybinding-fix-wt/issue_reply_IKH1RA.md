# Issue IKH1RA 回复草稿（人工粘贴用，不自动发布）

> 原文：https://gitee.com/jermaine/yate/issues/IKH1RA
> 「部分KeyBinding在Windows Terminal下失效：`ctrl+p`, `ctrl+1`, `ctrl+/` 等，但 `ctrl+q`, `ctrl+w` 可正常工作」

---

感谢反馈，问题已定位并修复（分支 `issues/keybinding-fix-wt`）。三个键实际是两类原因：

**1. `ctrl+/` —— 命名漂移（已修复，全平台）**

传统终端把 `ctrl+/` 编码为 C0 字节 `\x1f`，Textual 收到后把它命名为 `ctrl+underscore`
而不是 `ctrl+/`，而 yate 的 `event_to_raw` 映射表只登记了后者，导致按键被静默丢弃。
已补上映射（`editor_view/keys.py`），同时在别名表（`keymaps/base.py`）补了显示条目，
顺带修好了帮助面板（F1）里该键显示为乱码的问题。修复后 `ctrl+/` 在所有终端均可切换键位。

**2. `ctrl+p` —— 分发层级问题（已随分层重构修复）**

提交 issue 时按键先走 keymap 的 raw 分发：vsc 键位有 `ctrl+p` 绑定所以可用，vim 键位
没有绑定且未识别键被吞掉，所以失效。分层重构后 `ctrl+p` 提升为全局分发分支（先于
keymap），vim/vsc 两种键位下均生效。

**3. `ctrl+1` —— 终端限制（文档化，根治另行排期）**

conhost 不会给 `Ctrl`+数字 编码 C0 字节（数字键在 Ctrl 下没有历史编码），Textual 的
Windows 驱动又只读取字符、不读键盘状态位，修饰键信息在到达应用前就丢了；Windows
Terminal 目前也不支持 kitty 键盘协议（CSI-u）。所以 `ctrl+1` 在 WT/conhost 下物理不可达，
只有 kitty / WezTerm 等 CSI-u 终端能用。手册与 README 已标注兼容性及替代路径
（`Alt+Shift+P` 命令面板 / `:` 命令行）。彻底解决需要自建 Windows 输入通道读取
`dwControlKeyState`（win32-input-mode），已有重构计划，另行排期。

`ctrl+q` / `ctrl+w` 一直正常，因为它们有标准的 C0 编码（`\x11` / `\x17`），不在上述两类问题内。

验证：定向 255 项 / 全量 1228 项测试通过，pyright strict 零诊断；真机矩阵见计划文档
`.trae/documents/keybinding-fix-wt/`。
