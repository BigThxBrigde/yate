# dap-support plan-a：键位层支持带修饰 F 键（W1）

主计划依据：§5.0 事实 2 与决策 2；§1 键位层行。

## 目标

`<shift-f5>` / `<ctrl-shift-f5>` 等"带修饰 F 键"在键名解析、原始字节、
Textual 事件名三个方向全通；帮助覆盖层可逆显示。本期只绑定
Shift+F5 / Shift+F11（绑定本身归 plan-j），其余参数序列一次性支持。

## 非目标

不绑定任何调试动作（plan-j）；不改 vsc.py/vim.py（plan-b/j）；不处理
F1-F4/F8 既有绑定。

## 独占文件清单（只改这些）

- `yate/keymaps/base.py` — `SPECIAL_KEYS` :29-59（f1-f12 :47-58，补 `~` 族
  基准码表 F5=15/F6=17/F7=18/F8=19/F9=20/F10=21/F11=23/F12=24）、
  `parse_key` :88-126（shift 分支 :104-106 只大写单字符；新增 F 键修饰分支，
  键名风格与 `test_modified_arrows`（tests/test_app_textual.py:97）一致）、
  `key_name` :128-158 与 `KEY_ALIASES` :62-85（逆映射，帮助层显示）；
- `yate/keyproto/legacy.py` — `textual_key_to_raw` :87-124：识别 Textual 的
  `shift+f5` / `ctrl+shift+f5` 等事件名（mods 匹配风格同 `_MOD_ARROWS`
  :38-43 / `_MOD_SPECIAL` :45-49），带修饰 F 键发 `\x1b[<code>;<param>~`
  （param=2(shift)/3(alt)/5(ctrl)/6(ctrl+shift)）；当前返回 None（:124）；
- `tests/test_keyproto.py`、`tests/test_key_notation.py` — 双向用例。

## 实施要点

1. xterm 序列冻结基准（写入测试常量）：Shift+F5 = `\x1b[15;2~`、
   Shift+F11 = `\x1b[23;2~`、Ctrl+Shift+F5 = `\x1b[15;6~`。
2. 裸 F5 序列 `\x1b[15~` 行为不变（防回归用例）。
3. 禁止新增 `Any` / `TYPE_CHECKING`；pyright strict 零诊断。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py tests/test_key_notation.py tests/test_app_textual.py -q
.venv\Scripts\python.exe -m pyright yate/keymaps yate/keyproto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

## 风险与回滚

- 个别终端/多路复用器不上报修饰序列：本计划只保证编码/解码一致，兼容提示
  归文档（plan-l）；全部调试动作有 `:命令` 兜底。
- 回滚：单 commit revert 即可，无外部状态。
