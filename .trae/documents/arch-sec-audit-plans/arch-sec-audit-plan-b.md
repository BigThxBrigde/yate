# arch-sec-audit plan-b：扩展信任边界文档（S7）+ 门面 §三.5 异常注记（A1）+ 规则登记

## 输入与依据

- 取证 1（S7/A1）：`yate/services/extensions/__init__.py:1-49` docstring 自述
  "pure re-export facade ... R14"，但缺 `architecture-boundaries.md` §三.5 要求的
  异常声明措辞（§三.5 ②规定 UI/service 包禁止 re-export，唯一例外原文只列了
  `editor_view/theme.py`）。门面本身有守护用例
  `test_extension_facade_exports_the_frozen_plugin_names`（14 名冻结）——是刻意设计，
  需要的是**登记与注记**，不是改代码结构。
- 取证 2（S7）：扩展文档（`yate/docs/extensions.en.md` / `.zh.md`）中
  sandbox/trust 关键词零命中；Lua 运行时（`yate/services/extensions/lua/runtime.py:111-130`）
  为未删减 Lua 5.4（`os`/`io`/`package`/`debug` 可用），`api`/`api.app` 以 lupa 包装对象
  暴露可遍历的 Python 对象图。Python 扩展本就是完整 Python。**实际信任边界是
  "扩展 = 受信任代码"，但文档从未声明**——本轮以文档闭合该缺口（运行时机件加固列非目标，
  见 overview）。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `yate/docs/extensions.en.md`
2. `yate/docs/extensions.zh.md`
3. `yate/services/extensions/__init__.py`（仅 docstring，不改任何代码）
4. `.trae/rules/architecture-boundaries.md`（仅 §三.5 一处句子）

## 具体修改

### 1. `yate/docs/extensions.en.md` / `extensions.zh.md`（双语同步，两文件同时改）

新增小节 "Trust model"（中文 "信任模型"），内容必须与实际行为一致，要点：

- 扩展是**受信任代码**：Python 扩展以完整 Python 运行（可 import 任何库、访问文件系统
  与进程）；Lua 扩展运行在**未裁剪的 Lua 5.4 运行时**（`os`/`io`/`package`/`debug`
  均可用），且 `api` 对象暴露 yate 的 Python API 面。加载扩展 = 把作者当作可信方。
- 工作区 `./extensions` 的自动加载受 workspace trust 门控（`:trust`；详见
  `yate/services/trust.py` 的模块 docstring 语义）：打开陌生仓库不会执行其自带扩展。
- 不受门控的通道（用户刻意动作）：yaterc `extension_paths`、`--ext` / `--ext-dir`、
  用户级 `~/.yate/extensions`。
- 明确一句：当前版本**没有** Lua 沙箱或 API 白名单；不要安装来路不明的扩展。
- 位置：放在文档 "安装/加载" 相关节之后；先通读 en 版结构再落位，zh 版逐段对应翻译。

### 2. `yate/services/extensions/__init__.py`（docstring 末段追加，代码零改动）

在 docstring 末尾（第 48 行 "import only from here." 之后）追加一段：

```text
Package-root re-export exception note (architecture rules section 3.5): UI and
service packages normally must not re-export; this facade is the single
registered exception for service packages -- the plugin import path is
frozen by R14 and guarded by
``test_extension_facade_exports_the_frozen_plugin_names``.
```

### 3. `.trae/rules/architecture-boundaries.md` §三.5 ②

- 在 "**唯一例外**：`editor_view/theme.py` …" 句内追加登记：
  `services/extensions/__init__.py` 门面（R14 冻结 14 名插件导入路径，
  2026-10-29 arch-sec-audit 审计登记，docstring 已自述例外）同为登记例外。
- 保持该文件其余内容与既有编号/措辞不动。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_extension_facade.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "extension and facade" --cov-fail-under=0
```

（测试文件名以 `ls tests/test_extension*` 实际为准；核心是
`test_extension_facade_exports_the_frozen_plugin_names` 与架构 37 用例仍全绿。）

通过判定：exit 0；`__init__.py` 仅 docstring 变化（`git diff --stat` 核对 1 文件 0 代码行变更）；
两个手册文件均新增对应小节（en/zh 同时存在）。

## 风险与回滚

- 纯文档 + docstring 变更（misc-rules §三：含 1 个 .py 文件，不豁免测试，跑上述定向用例）。
- 回滚 = revert 本子计划提交。
