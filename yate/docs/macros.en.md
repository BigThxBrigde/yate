# yate macros

**English** · [中文](macros.zh.md)

yate can record a sequence of raw keystrokes into a register and replay
it later -- the classic "repeat this complicated edit on the other nine
lines" workflow. Both built-in keymaps (vim and the modeless vsc) share
one `<f6>` prefix and the same `:macro-*` commands; the recorded sequence
replays through the same dispatch path as manual typing, so what was
recorded is what gets replayed.

---

## 1. The `<f6>` prefix

| Keys | Effect |
| --- | --- |
| `<f6>` `r` `{a-z0-9}` | start recording into the register; the status bar shows `rec @<register>` |
| `<f6>` (while recording) | stop the recording and store the sequence |
| `<f6>` `p` `{a-z0-9}` | replay the register |
| `<f6>` `@` | replay the register played or recorded last |

Notes:

* While recording, every keystroke is executed *and* recorded, including
  unbound keys and chords -- vim semantics.
* Registers are single characters (`a-z0-9`), session-scoped and never
  persisted; recording the same register again overwrites it.
* In the vim keymap a count prefix works as usual: `3` `<f6>` `p` `a`
  replays three times. The modeless keymap has no numeric prefix state,
  so it replays once -- use `:macro-play a 3` there.
* A replay that is already running rejects nested replays with a notice,
  so a self-referencing register cannot recurse forever.

---

## 2. Command-line equivalents

```
:macro-record [a-z0-9]    " blank argument stops a running recording
:macro-play {a-z0-9} [count]
:macro-repeat [count]     " replay the last played/recorded register
```

Invalid register names or counts surface an error on the message line;
`:macro-repeat` without a previous macro says so instead of failing
silently.

---

## 3. How it works (implementation notes)

* The recorded content is the **raw key sequence** (the same strings the
  keymap tables dispatch on), not editor actions -- replaying goes through
  the editor's raw-key dispatch entry, keeping chord, count and unbound-key
  semantics identical to manual typing.
* Macro state (registers, the in-flight recording, the replay guard, the
  last register and the prefix-await state) lives on the session, so the
  status bar and the which-key panel read the same truth the dispatch
  layer writes.
* `MACRO_PREFIX_KEY` is a single shared L0 constant imported by both
  keymaps; a guard test pins the constant usage (no hard-coded `"<f6>"`
  literal in either binding table) and the identical action name across
  keymaps.
* The which-key panel shows the in-flight await rows (`r` record /
  `p` play / `@` repeat) while the prefix chord is pending.

---

## 4. 中文

yate 支持把一段原始按键序列录进单字符寄存器（`a-z0-9`）并回放。两种内置
键位（vim 与无模式 vsc）共用同一个 `<f6>` 前缀与同一组 `:macro-*` 命令；
回放与手动输入走同一条派发路径，录了什么就重放什么。

| 按键 | 效果 |
| --- | --- |
| `<f6>` `r` `{a-z0-9}` | 开始录制，状态栏显示 `rec @<寄存器>` |
| `<f6>`（录制中） | 停止录制并保存序列 |
| `<f6>` `p` `{a-z0-9}` | 回放寄存器 |
| `<f6>` `@` | 回放最近一次播放或录制的寄存器 |

说明：录制中的每次按键都会被执行并记录（vim 语义，含未映射键）；寄存器
仅当前会话有效、重录覆盖；vim 键位支持数字 count 前缀（`3` `<f6>` `p`
`a` 回放三次），无模式键位回放一次、需要次数用 `:macro-play a 3`；回放
进行中的嵌套回放会被拒绝并提示，自引用寄存器不会无限递归。

命令行等价入口：`:macro-record [a-z0-9]`（空参数停止录制）、
`:macro-play {a-z0-9} [count]`、`:macro-repeat [count]`；非法寄存器名或
次数会在消息行报错。
