# plan_d — 扩展系统机件拆包子包（Gitee IKK4K6 note_51571449）

## 目标与决策

note_51571449 两点：①扩展系统实现代码都在 services 模块，是否单独成包；②若拆，更新文档/架构文档/架构边界规则。

**决策：拆**，形态为 `yate/services/extensions/` 子包（不是顶层包）：

- 保持 L3 层归类与 R1-R5 依赖方向不变（顶层包会打乱 L0-L4 语义）。
- 门面导入路径 `yate.services.extensions` 不变（现有 `extensions.py` 的 13 个公共名再导出原样迁入包 `__init__`），外部零破坏。
- 内部模块私有化：外部（editor/flows/tests 除外）只允许进门面，新增架构规则 **R14** 并入架构测试守卫。
- `yate/services/lua/`（扩展运行时）随迁为 `yate/services/extensions/lua/`。
- `yate/services/events.py`（通用事件枢纽，editor 直接使用）与 `yate/services/user_setup.py`（用户目录装配）**不迁**——非扩展系统私有。

## 专属文件清单

移动（git mv 保留历史）：

- `yate/services/extension_api.py` → `yate/services/extensions/api.py`
- `yate/services/extension_bridges.py` → `yate/services/extensions/bridges.py`
- `yate/services/extension_loader.py` → `yate/services/extensions/loader.py`
- `yate/services/extensions.py` → `yate/services/extensions/__init__.py`（内容即门面再导出，docstring 保留"内部模块非公共 API"并指向新路径）
- `yate/services/lua/` → `yate/services/extensions/lua/`

修改（按 grep 实际命中为准，先枚举再改）：

- 全仓 `from yate.services.extension_api|extension_bridges|extension_loader import` 与 `from yate.services.lua` 的导入点：editor.py、yate/flows/extension_flows.py、yate/editor_view/statusbar.py（如有）、tests/**（枚举后逐一改路径，语义零改动）
- 相对导入：api/bridges/loader/lua 内部互相 import 的绝对路径改为新路径（包内允许 `from yate.services.extensions import ...` 门面级或显式子模块路径，遵循仓库绝对 import 惯例）
- `.trae/rules/architecture-boundaries.md`：新增 **R14**（格式对齐既有 R1-R13 条目）：扩展系统机件仅居于 `yate/services/extensions/`；外部代码只可 `from yate.services.extensions import <公共名>`（13 名白名单），直引 `api/bridges/loader/lua` 子模块视为违规；R4 的 services 禁拉 editor_view 约束对包内所有模块继续生效
- 架构测试（tests/ 下现有架构守卫文件，grep `R4|R11|architecture` 定位）：新增 R14 用例（外部直引子模块即红；门面 13 名可导入）
- `yate/docs/extensions.en.md` / `.zh.md`：正文提及的模块路径（如 `yate/services/extension_api.py`、`yate/services/extension_bridges.py`、`yate/services/lua`）替换为新路径；en/zh 同步
- 其它文档提及处：grep `services/extension_` 于 `yate/docs/**`、`README*`、`.trae/rules/**`，逐一更新

禁止触碰：`yate/services/events.py`、`yate/services/user_setup.py`、`yate/extensions/`（示例与 `_yate.lua`，路径不变）、CHANGELOG（由主控再生成）。

## 验收命令

```
python -m pyright
python -m pytest tests -q            # 含新 R14 架构用例，全绿
python -m tools.smoke_test compare   # 0 漂移（纯移动，无行为变更）
```

python 统一用仓库内 worktree 沙箱的 `.venv\Scripts\python.exe`，在该任务 worktree 目录内执行。

## 提交

单提交：`refactor(extensions): move extension machinery into a services subpackage`，正文一句：yate.services.{extension_api,extension_bridges,extension_loader,lua} collapse into yate/services/extensions/ behind the unchanged facade; new architecture rule R14 makes the facade the only import surface (gitee IKK4K6 note_51571449)。

## 回滚

纯移动 + 导入路径更新，`git revert` 单提交即可还原；无行为、无数据迁移。

## 执行记录与评审回填（2026-10-13）

| 提交 | 内容 |
| --- | --- |
| `2931a9b` | 拆包主体：7 处 git mv（相似度 57%-100%）+ 16 文件导入更新 + R14 规则与双用例 + 双语手册/规则文档路径同步 |
| `4aedb60` | 架构 wiki（`.trae/wikis/yate-architecture.md`）同步子包形态与 R14、events.py:34 docstring 存量路径、changelog 再生成 |
| `ed16f4e` | pr-review 修复：门面 layout map 补全十桥清单（原"four bridges"为搬迁前存量过时文本） |

### 门禁实测（2931a9b 树）

- `python -m pyright`：0 errors（2 warnings 为 pyperclip 存量）
- `python -m pytest tests -q`：2322 collected 全绿（架构 31 passed，含 2 条新 R14 用例：`test_extension_machinery_hides_behind_facade` / `test_extension_facade_exports_the_frozen_thirteen_names`）
- `python -m tools.smoke_test compare`：112/112 scenarios、1352/1352 checks、exit 0（纯移动零行为变更的实证）
- 执行者负向演练：清空白名单扫描全 yate/** 恰好命中 `editor_view/statusbar.py` 一处存量直引（`UiExtensionBridge` 类型注解，13 名门面不含该名），登记 `EXTENSION_SUBMODULE_FROZEN` 后零违规

### 评审记录（pr-review 框架，review 模式，round 1）

| 级别 | 位置 | 发现 | 处置 |
| --- | --- | --- | --- |
| MINOR | `services/extensions/__init__.py` layout map | "the four api.* bridges" 为搬迁前存量过时表述（现十桥），随迁移逐字带入 | **已修** `ed16f4e` |
| INFO | R14 `EXTENSION_SUBMODULE_FROZEN` | statusbar 直引 bridges 系门面 13 名不含 `UiExtensionBridge` 所致，仿 R11 白名单机制冻结并写入规则正文 | 合理设计，登记 |
| INFO | architecture-boundaries.md §六 | 执行者校正用例计数 28→29（补登漏记的 `test_no_relative_imports`）并注明事实 | 合理，登记 |

**结论：APPROVE**（AI pre-review；合并决策归人工）。纯移动实证：smoke 0 漂移 + 门面 13 名冻结测试 + R14 直引拦截；无新 sink、无热点改动、架构边界收紧（外部只能进门面成为机器可查规则）。

### 偏离登记（执行者已披露）

1. R14 引入存量直引冻结白名单（statusbar 的 `UiExtensionBridge` 类型注解）——"13 名逐字不变"硬约束的连带。
2. §六 计数校正（28→29→31 含 2 条新增）。
3. 范围外未动：`.trae/wikis/`、`.trae/documents/**`、`.trae/reviews/**` 旧路径提及——其中 wiki 已由主控在 `4aedb60` 补齐，其余为历史任务文档，保持原样。
