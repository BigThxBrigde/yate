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
7. 扩展：`--ext <file>`、`~/.yate/extensions`（`api.app` 可用）
8. `yate --diag` / `--version` / `--changelog zh`

额外回归（本轮改动高风险点）：
- **一次按键只派发一次**（typing / vim 模式切换不要出现"双倍移动"）
- 标签栏点击切换、面包屑宽度截断
- 主题切换后所有覆盖层（help / manual / changelog / palette）配色一致

### F.3.0 已定位的待改点（2026-09-22 预扫描，行号可能漂移）

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
| `yate/docs/extensions.en.md`、`extensions.zh.md` | `api.app` 的类型说明更新为 `ExtensionContext`（原为 `YateApp`）；列出其字段（session / workspace / lsp / keymaps / actions / commands / message / run_shell / open_path / save） |
| `yate/resources/manual.en.md`、`manual.zh.md` | 若提到"应用类 / feature 层"，改为"外壳 `YateApp` + 调度层 `Editor`" |
| `CHANGELOG.md`、`CHANGELOG.zh.md` | 新增条目：架构分层重构（外壳瘦身、`app_features` 移除、新增 `Editor` 调度层与 `EditorSession` 会话层）；用户可见变化：`api.app` 类型变更 |
| `.trae/rules/architecture-boundaries.md` | ✅ 已按新分层重写（L0–L4 定义、R1–R8、自检清单）；`split_app_protocol_plan.md` 引用改指本目录 | 
| `app-layering-refactoring-plans/README.md` | ✅ 已更新为总纲（事实基线 + 分层 + 命名 + 依赖规则 + Plan 索引 + 门禁 + 风险） |
| `app-layering-refactoring-plans/plan_A` – `plan_C` | ✅ 新增落地记录（原索引中仅有"已完成"，无文档） |
| `app-layering-refactoring-plans/plan_D` – `plan_F` | ✅ 迁移至本目录并更新状态与实测结果 |

## F.4 完成检查

- [ ] 四项门禁命令全通过
- [ ] 冒烟清单 1–8 全通过
- [ ] 文档与 CHANGELOG 已更新
- [ ] `git status` 中不再有 `yate/app_features/`
- [ ] `yate/app.py` ≤ 170 行、`yate/editor.py` 保持为唯一的编排大类
