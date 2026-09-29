# yate Code Review — Windows Terminal 键位失效（IKH1RA）— 2026-09-26

## Windows Terminal 键位失效（IKH1RA）— 2026-09-26

- [x] **WT 下 `ctrl+p` / `ctrl+1` / `ctrl+/` 失效，`ctrl+q` / `ctrl+w` 正常**
  （[Gitee IKH1RA](https://gitee.com/jermaine/yate/issues/IKH1RA)，分支 `issues/keybinding-fix-wt`）
  **根因（实测，Textual 8.2.8）：** ① `ctrl+/`：legacy 终端发 C0 字节 `\x1f`，Textual 将其命名为
  `ctrl+underscore`，而 `event_to_raw` 只登记 `ctrl+/` → 键被静默丢弃；② `ctrl+1`：conhost 不给
  Ctrl+数字编 C0 码，Textual win32 驱动（`drivers/win32.py`）只读 `uChar` 不读 `dwControlKeyState`，
  修饰键丢失，WT 又不支持 kitty CSI-u → 物理不可达；③ `ctrl+p`：提交 issue 时点（09-19）keymap
  分发前无 event.key 分支，vsc 有 `\x10` raw 绑定、vim 无绑定且吞键 → 仅 vsc 可用。
  **处置：** `ctrl+p` 随 `9fa5ac8` 分层重构修复（`Editor.handle_key` 全局分支，vim/vsc 双键位生效）；
  `ctrl+/` 由 `keys.py` `_CTRL_PUNCT` 补 `underscore` 条目 + `base.py` `KEY_ALIASES` 补显示别名修复
  （全平台，顺带消除 help 面板乱码）；`ctrl+1` 文档化为 kitty/CSI-u-only（双语 manual + README，
  替代路径 `Alt+Shift+P`），彻底根治需方案 B 自建输入通道（`win_keybinding_plan.md`，另行排期）。
  **证据：** 定向 255 / 全量 1228 passed，pyright 0 诊断；commit `b03e40f` `ff3cfc0` `678c02c`
  `f26e65d`；计划与执行记录见 [keybinding-fix-wt](../documents/keybinding-fix-wt/README.md)。
  **真机复测与 Phase A（2026-09-26，`YATE_TRACE=1` 取证）：** 首轮复测 vim 下仅 ctrl+q 通 →
  探针实证当前代码 pilot 层全通（此前疑为旧代码误测）→ trace 裁决出**真正的根因**：WT win32
  驱动把 ctrl+标点命名为长名（`ctrl+right_square_bracket` / `ctrl+circumflex_accent` /
  `ctrl+underscore`）而 `event_to_raw` 表不认识 → 丢键；但 `event.character` 仍携带正确 C0 字节。
  修复 = PA2b 通用兜底（表未命中且 character<0x20 → 直接采用，`1db6175`）+ PA1 入口日志 +
  PA3 vim 守卫（反向演练有效）。复测 trace：四键全通、零 unmapped。**剩余：ctrl+1 物理层丢失**
  （trace 无事件行），Phase B（win32-input-mode 驱动 chord）是唯一解，待启动。
