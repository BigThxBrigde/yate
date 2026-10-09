# 波次 f：manager → parsing；yaterc → yaterc_options（issue IKK5F7）

## 目标 1：`editor_lsp/manager.py`（833）→ `parsing.py`

- 新增 `yate/editor_lsp/parsing.py`（~230 行）——"线格式 → 缓冲坐标"纯函数：
  - `_to_utf16`、`_from_utf16`（55–76）；
  - `_unwrap_completion`、`_range_from`、`_range_to_buffer_cols`、
    `_parse_completion_item`（530–647，staticmethod → 模块函数，签名不变）；
  - `_parse_diagnostics`（679–743）。
  imports：`Document` + `.client`（Completion/Diagnostic/DiagnosticSeverity）；
  client 不 import parsing，无环；editor_lsp 仍不 import 上层。
- `manager.py`（~630 行）：保留全部状态编排（注册/客户端/生命周期/防抖/
  停机——`register_server`/`ensure_client`/四钩子/`shutdown_all` 共享
  `_configs`/`_clients`/`_starting`/`_open`/`_change_timers`/`_bg_tasks`
  六容器，是 A11 豁免的合理成分）；`request_completion` 保留在 manager，
  解析调用改 `parsing.*`；manager 保留 `from .parsing import _to_utf16,
  _from_utf16` 转发 import（`test_lsp.py:646` 两处引用零改动）。
- 包根 `__init__.py` 不动（parsing 不进 re-export，§三.5 守卫不触发）。
- 注意：`tests/test_lsp.py:771` monkeypatch
  `yate.editor_lsp.manager.CHANGE_DEBOUNCE_S`——常量留在 manager，无需改。

## 目标 2：`yaterc.py`（803）→ `yaterc_options.py`

- 新增 `yate/yaterc_options.py`（~630 行）：迁出 L193–803 全部
  `_extract_*` / `_parse_*` / `_require_*`（路径串提取、extensions、
  disabled_extensions、theme_dirs、journey 分数、screen_saver、file_preview、
  `_extract_options` 主表、language_servers、`_parse_language_server`、
  两个通用校验器）。只依赖 stdlib + `yate.config`（不需要 `yate.logs`，
  该区间无 log 调用）。
- `yaterc.py`（~200 行）：保留 docstring（精简为加载器职责）、
  `RC_FILENAME`（74）、`log`（76）、`user_config_path`（79）、
  `find_project_config`（84）、`default_rc_paths`（100）、两个 PEP 695
  回调**类型别名** `ThemeRegistrar` / `ThemeDirLoader`（119–124，N30 注入
  回调的词汇表，非类）、**`load_config`（127，公开 API 原位——
  `yate/cli.py:299` 与 `tests/test_cli.py:203/248/440` 的
  `patch("yate.yaterc.load_config")` 零改动）**；其对
  `_extract_*` 的调用改为经 `yaterc_options` 导入
  （已核实 193–803 区间无 `log.*` 调用，`yaterc_options.py` 不需要
  `yate.logs`）。
- import 方向：`yaterc.py → yaterc_options.py → (yate.config, stdlib)`，单向。
- 架构守卫：`tests/test_architecture.py` 的 `UI_FREE_FILES` 元组追加
  `"yaterc_options.py"`（保持 UI-free：不 import editor_view/textual.app）。

## 规则侧同步

- 行数守卫豁免集合（`tests/test_architecture.py`）移除 `yaterc.py` 与
  `editor_lsp/manager.py`；
- `.trae/rules/architecture-boundaries.md` §三.7 豁免名单同步移除
  `manager.py`、`yaterc.py` 条目；
- 同规则文档 §六「R4」条目文本：守卫面 `UI_FREE_FILES` 补提
  `yaterc_options.py`（与测试侧追加保持一致）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_lsp/ yate/
.venv\Scripts\python.exe -m pytest tests/test_lsp.py tests/test_config.py tests/test_cli.py tests/test_diagnostics.py tests/test_app_lsp.py tests/test_architecture.py -q
```

## 预估

`parsing.py` ~230；`manager.py` ~630；`yaterc_options.py` ~630；
`yaterc.py` ~200。

## 全量门禁（f 波完成 = 全部波次完成）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
```
