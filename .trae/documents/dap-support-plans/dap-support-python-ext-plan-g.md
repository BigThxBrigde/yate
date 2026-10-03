# dap-support plan-g：内置 python_dap 扩展与 JS 范例（W3）

主计划依据：§4.2 / §4.4；§8.1 扩展测试。

## 目标

内置 `python_dap.py`（debugpy 五级发现，可禁用）与随包
`example_js_dap.py.example`（js-debug-adapter 完整范例），模板分发零改动生效。

## 非目标

不改 `services/user_setup.py`（通配拷贝
[user_setup.py:104-105](../../yate/services/user_setup.py#L104-L105) 自动覆盖
新 .example）；不接 yaterc（plan-h）。

## 独占文件清单（只改这些）

- `yate/extensions/python_dap.py`（新增）— 镜像
  [python_lsp.py](../../yate/extensions/python_lsp.py)：直接
  `from yate.services.extensions import ExtensionAPI`（:34 先例，**禁止
  TYPE_CHECKING**）、`_venv_langserver` 式相邻 launcher 探测（:37-50 范式）、
  `discover_command()` 五级（env 覆盖/opt-out :64-83 范式 → which → 相邻
  launcher → find_spec("debugpy") → 全空）、`setup(api)` :86-105 范式；
  launch 模板见主计划 §4.2（`justMyCode: False` 写死，不开放 yaterc）；
- `yate/extensions/example_js_dap.py.example`（新增）— 完整内容见主计划
  §4.4 要点；代码纪律：直接 import ExtensionAPI + `from __future__ import
  annotations`，**不得使用 TYPE_CHECKING**（R6；旧版计划示例作废）；
- `tests/test_python_dap_ext.py`（修改）— discover 五级、launch 模板与
  filetypes、disabled_extensions 不加载（手法参照现有 test_python_lsp_ext.py）；
- `tests/test_dap_examples.py`（新增）— .example 静态/加载校验：存在、
  UTF-8、`compile()` 通过；假 ExtensionAPI exec 后断言注册参数（name=node、
  filetypes 含 js、launch 含 type=pwa-node/outputCapture、root_markers 含
  package.json）；`YATE_JS_DAP` 三态；**源码断言：无 TYPE_CHECKING、
  直接 import ExtensionAPI**；
- `tests/test_user_setup.py`（修改）— 资源清单 :24-25 增
  `extensions/example_js_dap.py.example`，确认 `--setup-defaults` 拷贝。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_python_dap_ext.py tests/test_dap_examples.py tests/test_user_setup.py -q
.venv\Scripts\python.exe -m pyright yate/extensions
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- 用户环境未装 debugpy/js-debug：懒失败（注册照常，F5 才报安装提示），
  文档归 plan-l。
- 回滚：删除两个新增文件 + 还原测试。
