# dap-support plan-h：yaterc debug_options 配置（W3）

主计划依据：§4.3。

## 目标

yaterc 支持 `debug_options` dict 选项，跨 adapter 通用键白名单校验，
错误进 `config.errors`（`--diag` 可见）。

## 非目标

不做声明式 `debug_adapters`（Phase 2）；不改 `LanguageServerSpec`
（[config.py:77-94](../../yate/config.py#L77-L94)）；不放开 `console` 键
（Phase 3）。

## 独占文件清单（只改这些）

- `yate/config.py` — 新增 `_extract_debug_options`（镜像
  `_extract_language_servers` [config.py:672-701](../../yate/config.py#L672-L701)
  的形状，由 `_extract_options` :668 调用链挂入）；白名单
  `env / stopOnEntry / args`；值必须 dict，否则/未知键按
  `config.errors.append` 收集风格（参照 :684-686）忽略该键；
  **不加入 `_KNOWN_OPTIONS`**（:60-64 只收标量选项，结构化选项走独立
  `_extract_*`）；`YateConfig` 增加 `debug_options: dict[str, object]` 默认空
  （默认值区参照 `terminal_height` :158）；`DapManager.set_debug_options`
  的接线归 plan-j；
- `yate/yaterc.example` — language_servers 段（:112-146）后加
  debug_options 注释段（只列通用键 + console 待 Phase 3 说明）；内置扩展
  清单（:68-79）补 `python_dap` 一行；
- `tests/test_config.py`（修改）— 合法 dict 合并、非 dict 报错、未知键报错
  （风格参照 language_servers 区 :244-488）。

## 实施要点

1. adapter 专有键（justMyCode/subProcess/outputCapture 等）出现在
   debug_options → 记 error 并忽略（保证换 adapter 不盲传未知键）。
2. 错误可见路径：启动消息行 + yaterc 节（[diagnostics.py:277-291](../../yate/diagnostics.py#L277-L291)
   自动带上，无需改 diagnostics——dap 节归 plan-k）。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_diagnostics.py tests/test_cli.py -q
.venv\Scripts\python.exe -m pyright yate/config.py
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- 与既有选项解析顺序冲突：`_extract_options` 单点挂入，负向用例覆盖
  （非 dict/未知键/合法合并三态）。
- 回滚：还原 config.py 单 commit。
