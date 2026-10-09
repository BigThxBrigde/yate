# vim-column-mode 子计划 b：Alt+Shift+方向键 键名/序列管道（wave-1）

> 输入：`overview.md` §四"vsc 键位与键名管道"。依赖：无。下游：plan-d 的
> `<alt-shift-*>` 绑定依赖本计划的序列表与 `parse_key` 支持。

## 一、目标

打通 `Alt+Shift+方向键` 从终端到 keymap 的全链路（当前三处缺口）：

1. `yate/keyproto/legacy.py` 的 `_MOD_ARROWS` 增加 `("alt","shift")` 行 →
   `event_to_raw("alt+shift+up")` 返回 `\x1b[1;4A`（Textual 名 → raw）；
2. `yate/keymaps/base.py` 的 `KEY_ALIASES` 增加 `\x1b[1;4A..D` 条目 →
   `key_name()`/help 反查可用；
3. `parse_key("<alt-shift-up>")` 可解析（当前 shift 分支会产出错误的
   `\x1b\x1b[1;2A`）。

## 二、非目标

- 不加任何绑定（绑定在 plan-d 的 `yate/keymaps/vsc.py`）；
- 不处理 `ctrl+shift+方向`（xterm `\x1b[1;6A/B`，上下两个无消费方，yate 只用
  左右，维持现状）；
- 不改 win32 帧/记录路径（`frames.py:159-181` 与
  `driver_windows.py:66-77` 已能命名 `"alt+shift+up"`，无需改）。

## 三、独占文件清单

- `yate/keyproto/legacy.py`
- `yate/keymaps/base.py`
- `tests/test_key_notation.py`（追加用例）

## 四、具体修改

### 1. `yate/keyproto/legacy.py` — `_MOD_ARROWS`（:38-43）追加一行

```python
    ("alt", "shift"): {"up": "\x1b[1;4A", "down": "\x1b[1;4B", "right": "\x1b[1;4C", "left": "\x1b[1;4D"},
```

键序注意：表键是 `tuple(sorted(mods))`（:61），`("alt","shift")` 已为字母序。
该表同时被 :meth:`modified_key_sequence`（:52-66）共享——集成终端 PTY 写出器
（`yate/editor_term/emulator/keys.py` 引用面）随之获得 alt+shift+arrow 的正确
转发，属顺带收益，在提交信息中注明。

### 2. `yate/keymaps/base.py` — `KEY_ALIASES`（:62-85）追加四条

```python
    "\x1b[1;4A": "alt-shift-up",
    "\x1b[1;4B": "alt-shift-down",
    "\x1b[1;4C": "alt-shift-right",
    "\x1b[1;4D": "alt-shift-left",
```

`_KEY_ALIASES_INV`（:90-92）由推导式自动获得反向表，无需另改。

### 3. `yate/keymaps/base.py` — `parse_key` shift 分支（:111-127）前置组合键检查

在 `if "shift" in modifiers:` 体内、`name == "tab"` 特判之前插入：

```python
        if "alt" in modifiers:
            # alt+shift combos encode as one CSI sequence (modifier param 4),
            # not "ESC + shift-sequence" -- the naive alt-prefix would alias
            # <alt-shift-up> onto a double-ESC'd shift-up.
            combined = _KEY_ALIASES_INV.get(f"alt-shift-{name}")
            if combined is None:
                raise ValueError(f"unsupported alt-shift key: {spec!r}")
            return combined
```

行为变化：`<alt-shift-up>` 等四个 spec 由"抛 ValueError/错误序列"变为正确
raw 序列；`<alt-shift-tab>` 等表外组合显式抛 `ValueError`（与既有
"unsupported shift key" 语义一致）。

## 五、新增测试（tests/test_key_notation.py 追加）

| 用例名 | 前置与操作 | 断言 |
|---|---|---|
| `test_parse_key_alt_shift_arrow_yields_csi_modifier_four` | 对四个 spec 逐一 `parse_key` | `parse_key("<alt-shift-up>") == "\x1b[1;4A"`、`<alt-shift-down> == "\x1b[1;4B"`、`<alt-shift-right> == "\x1b[1;4C"`、`<alt-shift-left> == "\x1b[1;4D"` |
| `test_parse_key_alt_shift_unknown_name_raises` | `parse_key("<alt-shift-tab>")` | `pytest.raises(ValueError, match="unsupported alt-shift")` |
| `test_key_name_alt_shift_arrow_roundtrip` | `key_name("\x1b[1;4A")` 等四条 | 返回 `"<alt-shift-up>"` 等（help 反查可用） |
| `test_event_to_raw_alt_shift_arrow_maps_csi` | 对四个 Textual 名调 `event_to_raw`（`yate.keyproto.legacy`） | `"alt+shift+up" → "\x1b[1;4A"` 等；`event_to_raw("alt+shift+home") is None`（表外不误报） |
| `test_modified_key_sequence_alt_shift_arrow_shared_table` | `modified_key_sequence(frozenset({"alt","shift"}), "up")` | `== "\x1b[1;4A"`（终端面板共享表同步） |

回归（负向防误伤，同文件追加）：

| 用例名 | 断言 |
|---|---|
| `test_parse_key_shift_up_sequence_unchanged` | `parse_key("<shift-up>") == "\x1b[1;2A"`（原路径不动） |
| `test_parse_key_alt_up_sequence_unchanged` | `parse_key("<alt-up>") == "\x1b\x1b[A"`（alt 前缀路径不动） |
| `test_parse_key_ctrl_shift_left_sequence_unchanged` | `parse_key("<ctrl-shift-left>")` 行为与改前一致（该组合无 alias，按原语义抛 ValueError/保持原样——以改前实测为准，用例钉住） |

## 六、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_key_notation.py tests/test_keyproto.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/keyproto/legacy.py yate/keymaps/base.py tests/test_key_notation.py
```

通过判定：退出码 0；既有 key notation / keyproto 用例零回归。

## 七、风险与回滚

- 风险：`parse_key` 是扩展绑定（`add_binding`）与所有 keymap 共用的解析器——
  组合键检查只拦 `alt+shift` 且表外显式抛错，不影响既有 spec；`_MOD_ARROWS`
  新行是纯增量（`modified_key_sequence` 按 mods 元组查表，无碰撞）。
- 老终端若把 `\x1b[1;4A` 解析成别的 key 名，绑定以 raw 序列为准，仍可命中
  （`event_to_raw` 的 C0/表回退保证 name→raw），残余场景列已知限制（overview §七）。
- 回滚：独立 commit（`feat(keyproto): alt+shift+arrow key sequences`），单提交
  revert；与 plan-a 无文件交集，回滚互不影响。
