# Plan F — 门禁与文档

> 状态：⏳ **待执行**（前置 [Plan E](plan_E_tests_tools.md) 仍在进行）· 后置：无
> 门禁：`pyright` 0 诊断 · `pytest` 全绿 · `--diag` / `--version` 正常 · 冒烟清单逐项通过

---

## F.1 门禁命令

```
python -m pyright yate/ tests/ tools/
python -m pytest tests/ -q
python -m yate --diag
python -m yate --version
python -m yate --changelog zh
```

任一失败：先修 `yate/`，再修 `tests/`，最后 `tools/`；修完重跑全部四项。

## F.2 冒烟清单（手工 / `tools/smoke_test`）

1. 启动：空 buffer / `yate <file>` / `yate <dir>`
2. explorer：`a` 新建、`A` 新建目录、`r` 重命名、`d` 删除（tab 清理 + didClose）
3. 终端：`` Ctrl+` `` 开关、shell 退出后按键重启、`:set terminal_height=20`
4. 补全：Ctrl+Space / 输入触发 / Esc 关闭
5. vim：`i` / `Esc` / `:` / `/` / `Ctrl+w`
6. 命令：`:w` `:q` `:set theme=...` `:theme` `:files` `:diagnostics` `:explorer`
7. 扩展：`--ext <file>`、`~/.yate/extensions`（扩展内 `api.app` 现为 `ExtensionContext`，不再是 `YateApp`）
8. `yate --diag` / `--version` / `--changelog zh`

额外回归（本轮改动高风险点）：
- **一次按键只派发一次**（typing / vim 模式切换不要出现"双倍移动"）
- 标签栏点击切换、面包屑宽度截断
- 主题切换后所有覆盖层（help / manual / changelog / palette）配色一致

### F.3.0 已定位的待改点（2026-09-22 预扫描；2026-09-23 复核：4 处行号仍精确命中）

| 位置 | 现状 | 应改为 |
|---|---|---|
| `yate/docs/extensions.en.md:175` | `\| api.app \| ExtensionHost \| the application host protocol (advanced use) \|` | `\| api.app \| ExtensionContext \| the concrete services an extension drives (advanced use) \|` |
| `yate/docs/extensions.zh.md:163` | `\| api.app \| ExtensionHost \| 应用宿主接口（高级用法） \|` | `\| api.app \| ExtensionContext \| 扩展可驱动的具体服务（高级用法） \|` |
| `yate/resources/manual.en.md:1088` | Access 行含 `api.app` | 保留入口名，注明其类型为 `ExtensionContext`（字段同扩展文档） |
| `yate/resources/manual.zh.md:989` | 同上 | 同上 |
| `yate/resources/changelog.*.md` | 历史条目中的 `app_features` / `YateApp`（第 178/180/181/183 行等） | **不改**：历史记录，且架构测试的文本扫描不含 `yate/resources/*.md` |

## F.3 文档同步

> 计划文档现已统一收纳在 `.trae/documents/app-layering-refactoring-plans/`（总纲 `README.md` + `plan_A`…`plan_F`）。

| 文件 | 动作 |
|---|---|
| `yate/docs/extensions.en.md`、`extensions.zh.md` | `api.app` 的类型说明更新为 `ExtensionContext`（现文写的是 **`ExtensionHost`**，代码中不存在该名）；列出其字段（session / workspace / lsp / keymaps / actions / commands / message / run_shell / open_path / save），并把 `api.keymaps` 的 `dict[str, Keymap]` 改为 `KeymapSet` |
| `yate/resources/manual.en.md`、`manual.zh.md` | 若提到"应用类 / feature 层"，改为"外壳 `YateApp` + 调度层 `Editor`" |
| `CHANGELOG.md`、`CHANGELOG.zh.md` | 新增条目：架构分层重构（外壳瘦身、`app_features` 移除、新增 `Editor` 调度层与 `EditorSession` 会话层）；用户可见变化：`api.app` 类型变更 |
| `.trae/rules/architecture-boundaries.md` | ✅ 已按新分层重写（L0–L4 定义、**R1–R11**、自检清单、防回归清单）；R9 的 id 清单已在 2026-09-23 审计中补齐。该文档仍把 `split_app_protocol_plan.md` 列为**前序文档**（不是"引用改指本目录"）；指向本目录的权威引用在文档开头 | 
| `app-layering-refactoring-plans/README.md` | ✅ 已更新为总纲（事实基线 + 分层 + 命名 + 依赖规则 + Plan 索引 + 门禁 + 风险） |
| `app-layering-refactoring-plans/plan_A` – `plan_C` | ✅ 新增落地记录（原索引中仅有"已完成"，无文档） |
| `app-layering-refactoring-plans/plan_D` – `plan_F` | ✅ 迁移至本目录并更新状态与实测结果 |

## F.4 完成检查

- [ ] 四项门禁命令全通过
- [ ] 冒烟清单 1–8 全通过
- [ ] 文档与 CHANGELOG 已更新
- [ ] `git status` 中不再有 `yate/app_features/`
- [ ] `yate/app.py` ≤ 170 行（非空行口径）、`yate/editor.py` 保持为唯一的编排大类

> **前置提醒（2026-09-23 实测）**：`pytest tests/ -q` 目前被 [Plan E](plan_E_tests_tools.md) §E.6 的
> 未迁移用例阻塞（收集阶段中断），F.1 的 pytest 门禁需等 Plan E 完成。行数口径见总纲 §1。

---

## F.5 审计顺手修正（2026-09-23，已完成）

> 来源：子代理对 `.trae/` 文档与本目录计划的交叉审计（总纲 §10）。这些都是与本次重构直接相关、
> 且已失效的引用，随本 Plan 一起收敛。

| 文件 | 修正 |
|---|---|
| `tests/test_architecture.py` 顶部 docstring | 引用的 `.trae/documents/app_layering_plan.md`（不存在）改为 `app-layering-refactoring-plans/README.md` §4；命名守卫不再冒用 R7 编号；`test_collaborators_*` 标注 R4 / R11 |
| `.trae/rules/architecture-boundaries.md` | R9 的 id 清单补齐语义并补容器 id `#body` `#bottom-dock` `#bottom`；`keymaps` 的 L0 / L1 归属消歧 |
| `.trae/rules/python-coding-style.md` | §1.3 / §3.2 的"窄 Protocol（Host/Ops）"改为"具体对象 / 叶子类型"；示例 `from yate import tracing` → `from yate.logs import tracing`；`install()` 示例签名按现状；`yate/crash.py` / `yate/tracing.py` 路径改指 `yate/logs.py` |
| `.trae/skills/textual-pilot-smoke/SKILL.md` | baseline 路径 `tools/smoke_baselines/` → `tools/smoke_test/smoke_baselines/`（并注明 SVG 行需 `--with-svg`）；新增用例的写法改为该文件实际的 pytest 模式 |
| `.trae/documents/split_app_protocol_plan.md` | 顶部状态块补一句"正文 §3.2 的 R1–R6 为**旧编号**，勿与总纲 R1–R11 对照" |
