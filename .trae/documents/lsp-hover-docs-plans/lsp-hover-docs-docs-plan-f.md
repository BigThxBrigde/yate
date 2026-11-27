# 计划 f — 双语文档（波次 2，docs）

父计划：[overview.md](overview.md) · 主计划：[../lsp-hover-docs-plan.md](../lsp-hover-docs-plan.md)，决策 D1 / D7

## 输入

- `yate/docs/lsp.en.md:11-23` 与 `yate/docs/lsp.zh.md:10-19`（客户端能力项目符号列表；目前仅有自动补全 + 诊断）。
- `yate/resources/manual.en.md:354-390`（§5.1 vsc）、`:1345-1367`（§16 LSP）、`:1583-1604`（§18 速查表）；§5 的 vim 小节（先读它）。
- `yate/resources/manual.zh.md:322-357`（§5.1 vsc）、`:1202-1219`（§16 LSP）、`:1409-1430`（§18 速查表）；§5 的 vim 小节。
- `FEATURES.md:118-128`、`FEATURES.zh.md:98-104`（§11 LSP 项目符号列表）。
- `doc-conventions.md` §三（`.en.md` / `.zh.md` 成对文件必须一起更新）、§五（仓库内相对路径，不得使用机器本地绝对路径）。

## 已登记的偏离

AC7 点名了 `FEATURES.en.md`；在基线中该文件并不存在。英文特性列表是
`FEATURES.md`。应更新 `FEATURES.md` + `FEATURES.zh.md`，并在最终报告中
注明这一偏离。

## 独占文件

- `yate/docs/lsp.en.md`, `yate/docs/lsp.zh.md`
- `yate/resources/manual.en.md`, `yate/resources/manual.zh.md`
- `FEATURES.md`, `FEATURES.zh.md`
- `tests/test_hover_docs.py`（新建）

不涉及产品代码，不涉及 `.trae/` 文档。

## 具体改动（全部六个文件，事实一致）

两种语言中都要陈述的事实：

1. 一项新能力：**LSP 悬停文档**。快捷键 **`F7`**
   （按键记法中为 `<f7>`）—— **vsc 与 vim 使用同一个键**，没有各 keymap 的
   单独默认值，也没有组合键。它显示光标处符号的 API 文档。
2. 鼠标悬停：启用 `support_mouse` 后，将指针停在符号上会经过短暂防抖后显示同一张卡片；移开指针、移动光标、输入或按 `Esc` 会关闭它。关闭 `support_mouse` 时该路径被禁用。
3. **没有文档 → 绝对不显示任何内容**：没有卡片、没有 "No documentation" 占位符、没有消息栏/状态栏提示、没有闪烁。
   这也覆盖服务器未启动 / 未就绪 / 未为该语言配置服务器，或请求失败/超时的情况。
4. 卡片显示服务器返回的签名和 docstring；它绝不改变焦点、绝不吞掉其他按键，也绝不启动服务器或改变同步行为。
5. 重新绑定：扩展可以使用 `bind_key(..., keymap="both")` 一次改动两个 keymap 的按键；只覆盖其中一个 keymap 是用户的显式选择。

编辑位置：

- `lsp.en.md` / `lsp.zh.md`：在 Autocomplete/Diagnostics 旁添加第三条能力项目符号，并在同步小节下添加一小段说明"悬停是纯请求，不发送 didOpen/didChange"。
- `manual.en.md` / `manual.zh.md`：在**两个** keymap 表格（§5.1 vsc 和 vim 小节）中添加 `| \`F7\` | Show API documentation at
  cursor |`（中文：`| \`F7\` | 显示光标处 API 文档 |`），键位值要完全一致；在 §16 添加一条悬停项目符号；在 §18 四列速查表中添加一行，在**两个**键位列中都写入 `F7`，动作文本相同。
- `FEATURES.md` / `FEATURES.zh.md`：在 §11 添加一条项目符号，提及 `F7`、鼠标悬停以及为空时静默的行为。
- 任何地方都不要把 `Ctrl+K` / `Ctrl+Shift+K` 写成悬停键（D1），不要写机器本地路径，保持现有表格对齐和标题编号。

## 测试（`tests/test_hover_docs.py`）

路径解析：`ROOT = Path(__file__).resolve().parents[1]`；不硬编码 home 目录。以 UTF-8 文本读取每个文件。

| 测试 | 安排 / 执行 | 断言 |
| --- | --- | --- |
| `test_lsp_docs_both_languages_describe_hover_and_f7` | 读取 `lsp.en.md`、`lsp.zh.md` | 每篇都包含 `F7` 以及 `hover`（en）/ `悬停` 或 `hover`（zh） |
| `test_lsp_docs_both_languages_describe_silent_empty_behavior` | 同样的文本 | 英文包含 "no documentation"/"nothing is shown"；中文包含 "无文档"/"不显示" |
| `test_manual_both_languages_put_the_same_key_in_vsc_and_vim_sections` | 截取每本手册的 §5 | `F7` 在每个 §5 片段中至少出现两次，且不存在把 `Ctrl+K` 写作悬停键的行 |
| `test_manual_cheat_sheet_uses_identical_f7_in_both_key_columns` | 读取 §18 片段 | 每种语言的悬停行都包含两次 `F7`（四列表格） |
| `test_manual_lsp_sections_describe_mouse_hover_and_silence` | §16 片段 | 中英文均提及鼠标悬停和空值静默规则 |
| `test_features_both_languages_mention_hover_and_f7` | `FEATURES.md`、`FEATURES.zh.md` | 每篇都包含 `F7` 和 LSP 章节编号 |
| `test_docs_never_present_ctrl_k_as_the_hover_key` | 全部六篇文本 | 没有任何一行出现包含 `Ctrl+K` / `ctrl-k` 的悬停描述语句 |
| `test_docs_contain_no_machine_local_absolute_paths` | 全部六篇文本 | 新增行中没有 `C:\Users\`、`/home/`、`/Users/` 前缀（对整个文件使用正则，与架构守卫的模式一致） |

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hover_docs.py -q -n 1
```

退出码为 0。主代理的波次 2 门禁还会运行完整的 pyright（新增测试文件位于 `tests/`）和架构测试套件（按 `misc-rules.md` §三，纯文档豁免门禁，但该波次同时包含代码）。

## 风险与回滚

- 风险：手册表格对齐 / markdown lint。保持现有列数；不要重排无关行。若 `pymarkdownlnt` 对新增行报错，只修该行并上报。
- 风险：§5 的 vim 小节可能使用与假设不同的标题。读取实际文件，将该行插入真正的 vim 表格；测试对 §5 是通用切片，所以并不硬编码确切标题。
- 回滚：回退此提交；没有代码依赖这些文档，一致性测试也随之移除。
