# Plan SP1 — config 解耦 + cli 注入 + 测试修补

> 状态：⏳ **待实施** · 前置：[Plan SP0](plan_SP0_baseline.md) ✅ · 后置：[Plan SP2](plan_SP2_guard_docs.md)
> 工作量：M · 步骤：S1.1 → … → S1.9（串行）
> 接口设计与行为契约的唯一来源：[README §3](README.md#3-接口设计方案-a-落地形态)。
> 硬约束：既有错误消息断言逐字不动（行为零漂移）；`tests/test_architecture.py` 属 SP2 域，本 Plan 不动。

---

## 1. 步骤表

| 步 | 动作 | 输入 | 输出 | 验收 |
|---|---|---|---|---|
| S1.1 | config.py 导入组 stdlib 组按字母序加 `from collections.abc import Callable`，模块级加 `type ThemeRegistrar` / `type ThemeDirLoader`（`Any` 附理由注释） | README §3.1 | 两别名落位 | `pyright yate/config.py` → 0 |
| S1.2 | `load_config` 签名加 keyword-only `register_theme` / `load_theme_paths`（`… \| None = None`） | S1.1 | 新签名编译通过 | pyright 单文件 0 |
| S1.3 | 实现改造：① 删 :173-175 惰性 import 注释与语句；② namespace 仅在 `register_theme is not None` 时注入该键（缺省缺名 → NameError，走既有逐文件容错）；③ :204 装载改为回调非 None 才调，**原位不动**（仍在 `_extract_options` 之前）；④ `load_config` docstring 写明 README §3.2 两种模式语义；⑤ 模块 docstring「one injected helper」改为回调注入表述 | S1.2 | config.py 对 `editor_view` 零引用 | `Select-String -Pattern "editor_view" yate\config.py` 零命中；pyright 0 |
| S1.4 | cli.py:264 调用点传 `register_theme=theme_mod.register_theme, load_theme_paths=theme_mod.load_theme_paths`（README §3.3） | S1.3 | 生产路径等价改造 | pyright 0；冒烟主题场景（SP3 复验） |
| S1.5 | 调用点审计：grep 全仓 `load_config\(`，对照 §4 审计表逐点判定「rc 体是否调 `register_theme` / 声明 `theme_dirs`」 | §4 审计表 | 逐点 ✅ / 修补 / N/A 清单（写「执行记录」） | 生产 1 处（cli.py:264）+ 测试 3 文件全部有判定，无未核对项 |
| S1.6 | test_config.py 修补：`_load` 助手（:19-21）增 keyword 透传；主题段（:634-810）按 S1.5 判定传真回调 | S1.5 | 修补 diff | `pytest tests/test_config.py -q` 全绿 |
| S1.7 | test_app_textual.py:1026 / test_diagnostics.py:32/34/256 按 S1.5 判定修补（大概率 N/A：空 rc / 扩展 rc） | S1.5 | 修补 diff 或 N/A 记录 | `pytest tests/test_app_textual.py tests/test_diagnostics.py -q` 全绿 |
| S1.8 | **新增守卫用例 ×2**（名称与断言见 §2，不得遗漏） | README §3.2 契约 | 2 个新用例 | 新用例绿；错误消息逐字断言 |
| S1.9 | SP1 专项门禁：pyright 全仓 + pytest 全量 | S1.6–S1.8 | 数字写「执行记录」 | 0 诊断 + exit 0；既有错误消息断言逐字未动（行为零漂移） |

## 2. 新增测试清单（不可遗漏项）

**新增用例 ×2**（放 tests/test_config.py，命名按 `test_<behavior>_<condition>_<expected>`）：

| 用例 | 场景 | 断言核心 |
|---|---|---|
| `test_load_config_without_theme_hooks_records_register_theme_error` | 两个 rc：rc1 调 `register_theme(...)`、rc2 设 `tab_width = 2`；`cfg.load_config([rc1, rc2])` 不传钩子 | `config.errors` 恰含一条 `register_theme` 的 NameError 记录；`config.tab_width == 2`（后续 rc 未中止）；`config.theme` 保持默认 `mocha` |
| `test_load_config_without_theme_hooks_keeps_theme_dirs_unloaded` | rc 声明 `theme_dirs` 指向含合法主题 `*.py` 的目录；不传钩子 | `config.theme_dirs` 照常提取非空；`theme.THEMES` 无新主题（未装载）；`config.errors` 无主题装载错误 |

## 3. 产物提交（与 SP2 分笔）

- 本 Plan 完成后**先不提交**，与 SP2 的守卫/文档分两笔（见 [Plan SP3](plan_SP3_gate_commit.md) S3.3）：
  本 Plan 产物独立成笔 `refactor(config): decouple yaterc loader from editor_view.theme`
  （config.py + cli.py + tests 修补与新增用例）。

## 4. 存量调用点审计修补表（S1.5 逐点判定）

| 位置 | 判定要点 | 预期处理 |
|---|---|---|
| tests/test_config.py `_load`（:19-21） | 助手签名 | 增 keyword 透传（`register_theme` / `load_theme_paths` 可选参数） |
| tests/test_config.py :634-810 主题段 | rc 体调 `register_theme`（:641、:801）或声明 `theme_dirs`（:664/:684/:697/:710/:718/:728/:735/:746 等） | 断言依赖注册/装载结果的用例传真回调（测试模块已有 `from yate.editor_view import theme as themes`）；仅断言 `config.theme_dirs` 提取结果的用例可不传（提取不依赖钩子） |
| tests/test_cli.py :254-312 | 是否经真实 cli 启动路径触达 `load_config` | 涉主题注册/装载的传回调或 monkeypatch；不触达记 N/A |
| tests/test_app_textual.py :1026 | rc 体内容 | 涉主题则补回调，否则 N/A |
| tests/test_diagnostics.py :32/:34/:256 | rc 体内容 | 大概率 N/A（空 rc / 扩展 rc），复核确认 |

---

## 执行记录（回填区，执行时填写）

- S1.1–S1.4：（日期、逐步验收结果、实际改动行号 vs 计划锚点偏移）
- S1.5 审计结论：逐点判定表（位置 → ✅ 原样 / 修补 / N/A + 理由）
- S1.6 / S1.7：修补 diff 概要（用例名 → 处理方式）
- S1.8：两个新用例实测输出（pytest 行）
- S1.9 专项门禁：pyright ___ errors；`pytest tests/ -q` → ___ collected / exit ___
- 偏离计划项及理由：
