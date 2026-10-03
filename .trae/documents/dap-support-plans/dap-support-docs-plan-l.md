# dap-support plan-l：双语文档 / 手册调试章 / README / API 清单（W6）

主计划依据：§9 文档与资源表。

## 目标

用户可发现：双语 dap 指南、手册调试章、README 特性/结构树、
example_ext.py.example API 面清单。

## 非目标

不改代码与测试；不改 F5→F7 既有条目（plan-b 已完成，本计划只在键位表
补调试键行）；不做 yaterc.example（plan-h 已完成）。

## 独占文件清单（只改这些）

- `yate/docs/dap.en.md` + `yate/docs/dap.zh.md`（**新增，双语成对硬约束**，
  同步同时落地）— 内容按主计划 §9 表：架构一图、debugpy 安装、键位表
  （F5/F6/F9/F10/F11/F12/Shift+F5/Shift+F11 + `:debug` 系列）、断点/求值/
  面板用法、`YATE_PYTHON_DAP`/`YATE_JS_DAP`/`debug_options`、
  internalConsole/startDebugging 限制、**带修饰 F 键终端兼容说明**（含
  Shift+F5 原始序列）、"扩展接入其他 adapter"教程（JS 范例完整走查 +
  gdb/dlv/lldb-dap 差异点表 §4.5）；风格与 [lsp.en.md](../../yate/docs/lsp.en.md)/
  [lsp.zh.md](../../yate/docs/lsp.zh.md) 对齐（文件头互链）；
- `yate/resources/manual.en.md` / `manual.zh.md` — 新增"调试"章（置于集成
  终端章之后）：快速开始（t.py 走查）、命令/键位表、JS 范例改名即装、
  限制；**不改** plan-b 已迁移的 F7 条目；
- `README.md` — 特性区（:28-47）加 debugging（DAP：内置 debugpy + JS 扩展
  示例）行；键位表（:92-98 区）补调试键行；结构树（:215-252）补
  editor_dap/debug_panel/dap_sync；
- `README.zh.md` — 对应（特性 :25-73、键位表 :117-123 区、结构树 :230-267）；
- `yate/extensions/example_ext.py.example` — API 面清单（:21-36）加
  `api.dap.register_debugger` 注释态小例（指向 JS 范例）。

## 实施要点

1. 路径引用遵守 doc-conventions §五（相对路径、无本机真实路径）；
   文件名 ASCII 连字符分词。
2. 双语内容一一对应，英文为准成稿后翻译；术语统一（debug adapter /
   breakpoint / step over 等，参照 lsp 文档既有译法）。
3. `--setup-defaults` 后改名激活的说明与 plan-g 的示例头注释保持一致。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_user_setup.py tests/test_pack_wiki.py tests/test_release_tool.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
# 人工核对：双语文件成对存在、文档内链接可达（相对路径）
```

## 风险与回滚

- 文档与实现漂移：验收前对照主计划 §5.5 键位表与 §7 错误文案逐条核对；
- 回滚：纯文档 commit，可独立 revert。
