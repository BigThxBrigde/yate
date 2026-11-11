# yate 宏（录制与回放）

[English](macros.en.md) · **中文**

yate 支持把一段原始按键序列录进寄存器、稍后回放——经典的「把这套复杂编辑
在另外九行上重做一遍」工作流。两种内置键位（vim 与无模式 vsc）共用同一个
`<f6>` 前缀与同一组 `:macro-*` 命令；回放与手动输入走同一条派发路径，
录了什么就重放什么。

---

## 1. `<f6>` 前缀

| 按键 | 效果 |
| --- | --- |
| `<f6>` `r` `{a-z0-9}` | 开始录制，状态栏显示 `rec @<寄存器>` |
| `<f6>`（录制中） | 停止录制并保存序列 |
| `<f6>` `p` `{a-z0-9}` | 回放寄存器 |
| `<f6>` `@` | 回放最近一次播放或录制的寄存器 |

说明：

* 录制中的每次按键都会被执行*并*记录（vim 语义，含未映射键与组合键）；
* 寄存器为单字符（`a-z0-9`），仅当前会话有效、不会持久化；重复录制同名
  寄存器会覆盖旧内容；
* vim 键位照常支持数字 count 前缀：`3` `<f6>` `p` `a` 回放三次。无模式
  键位没有数字前缀状态，回放一次——需要次数请用 `:macro-play a 3`；
* 回放进行中的嵌套回放会被拒绝并提示，自引用寄存器不会无限递归。

---

## 2. 命令行等价入口

```
:macro-record [a-z0-9]    " 空参数停止正在进行的录制
:macro-play {a-z0-9} [count]
:macro-repeat [count]     " 回放最近一次播放/录制的寄存器
```

非法寄存器名或次数会在消息行报错；没有可重复的宏时 `:macro-repeat`
会明确提示而不是静默失败。

---

## 3. 实现要点（站外备注）

* 录制内容是**原始按键序列**（键位表派发所用的同一字符串），不是编辑器
  动作——回放经编辑器的 raw 按键派发入口，组合键、count 与未映射键的
  语义与手动输入完全一致。
* 宏状态（寄存器、进行中的录制、回放防护旗标、最近寄存器、前缀等待态）
  全部挂在会话上：状态栏与 which-key 面板读到的是与派发层相同的真值。
* `MACRO_PREFIX_KEY` 是单一共享 L0 常量，两套键位各自导入；守卫测试锁定
  常量引用（任一绑定表硬编码 `"<f6>"` 字面量都会被拦截）与两表同名动作。
* 前缀 chord 等待期间，which-key 面板显示 `r` 录制 / `p` 回放 /
  `@` 重复的提示行。

---

## 4. English

yate records a sequence of raw keystrokes into a register and replays it
later. Both built-in keymaps share one `<f6>` prefix and the same
`:macro-*` commands; replay goes through the same dispatch path as manual
typing, so what was recorded is what gets replayed.

| Keys | Effect |
| --- | --- |
| `<f6>` `r` `{a-z0-9}` | start recording; the status bar shows `rec @<register>` |
| `<f6>` (while recording) | stop and store the sequence |
| `<f6>` `p` `{a-z0-9}` | replay the register |
| `<f6>` `@` | replay the register played or recorded last |

Registers are session-scoped and overwritten on re-record; a count prefix
replays N times in the vim keymap (`:macro-play a 3` in the modeless one);
nested replays are rejected with a notice. Command-line equivalents:
`:macro-record [a-z0-9]`, `:macro-play {a-z0-9} [count]`,
`:macro-repeat [count]`.
