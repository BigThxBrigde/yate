# 子计划 plan-f：keyproto 层级收敛（A2）

> 所属波次：**wave-2**（与 reexports-plan-b 文件不重叠，可并行；主代理执行）。
> 执行者：**主代理**（改 `yate/keyproto/` 产品源码）。
> 来源：评审 A2。

## 一、输入

- `keyproto/__init__.py:16-17` 声明 "must not import any other yate module except `yate.keymaps.base`"，实际：
  - `keyproto/driver_windows.py:55` `from yate.logs import tracing`（违反声明，但**符合 R12**——运行时日志统一 tracing，改回 stdlib logging 反而制造第二套日志通道）；
  - `keyproto/driver_windows.py:33-36` import textual 私有模块 `textual._xterm_parser`、`textual.drivers._writer_thread`（无稳定承诺，Textual 升级即断）与公共 `constants` / `drivers.win32` / `drivers.windows_driver` / `events.Key` / `message.Message`；
- 决策（主计划 §三 A2）：`yate.logs` 选**豁免注明**路线；textual 私有 API 收敛到薄适配模块 + 集中记录 Textual 最低版本；pin 版本 import 冒烟并入 CI（wave-5 plan-e 的 Windows 腿）。

## 二、独占文件清单

1. `yate/keyproto/__init__.py`（docstring 豁免注明）
2. `yate/keyproto/textual_internals.py`（新增薄适配模块）
3. `yate/keyproto/driver_windows.py`（私有 import 改走适配模块）
4. `tests/test_keyproto.py`（新增 2 个用例）
5. `.trae/rules/architecture-boundaries.md`（keyproto 描述同步，一句）

## 三、具体修改

### 3.1 textual_internals.py（新增）

私有模块（下划线语义由"仅 driver_windows 消费"约定承担；不以 `_` 开头便于 pyright include 覆盖）。内容：
- 模块 docstring：说明本模块是 yate 对 Textual **私有内部 API** 的唯一收口点；列出所依赖的 Textual 最低版本承诺（`textual>=8.0`，pyproject:13）与实测可用版本（8.2.8，依据 architecture-boundaries R12 devtools 桥接实证记录）；升级 Textual 时优先检查本文件。
- 具名 re-export（不做 Any）：
  ```python
  from textual._xterm_parser import XTermParser
  from textual.drivers._writer_thread import WriterThread
  ```
- `__all__ = ["XTermParser", "WriterThread"]`。
- `driver_windows.py:33,35` 两行改为 `from yate.keyproto.textual_internals import WriterThread, XTermParser`；其余 textual 公共 import（`constants` / `win32` / `windows_driver` / `Key` / `Message`）不动（公共 API，无稳定承诺问题）。

### 3.2 keyproto/__init__.py docstring

`:16-17` 声明改为三条如实表述：
1. 除 Windows 驱动外，包内模块只依赖 stdlib；
2. `driver_windows.py` 豁免依赖：`yate.logs`（R12 统一 tracing，logger 无副作用）与 `yate.keyproto.textual_internals`（Textual 私有 API 收口点，含最低版本承诺）；
3. 不依赖 `yate.keymaps.base`（原文声明有误——实测包内无该依赖，`SPECIAL_KEYS` 注释属历史描述，如实修正）。

### 3.3 规则同步

`architecture-boundaries.md` §一 L0 清单 keyproto 条目（`:24-27` 附近 2026-09-28 核对注）追加一句："`keyproto/driver_windows.py` 经 `keyproto/textual_internals.py` 收口 Textual 私有 API（A2 定案）；`yate.logs` 为 R12 豁免依赖。"

## 四、新增测试与验证方案

`tests/test_keyproto.py` 新增：

1. `test_textual_internals_is_the_only_private_api_consumer`
   - 前置：无（AST 静态扫描）；
   - act：扫描 `yate/keyproto/*.py` 全部 import；
   - 断言：`textual._xterm_parser` / `textual.drivers._writer_thread`（以及任何 `textual` 下含 `_` 前缀模块）只出现在 `textual_internals.py`——私有 API 收口守卫。
2. `test_driver_windows_import_smoke`（`skipif` 非 win32）
   - 前置：Windows + 已安装 textual；
   - act：`import yate.keyproto.driver_windows`；
   - 断言：导入成功且 `sys.modules` 同时含 `yate.keyproto.textual_internals`——Textual 升级破坏私有 API 时第一时间暴露（CI pin 版本冒烟的本地等价物；wave-5 plan-e 将其纳入 Windows 腿常规步骤）。

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_keyproto.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
```

负向演练：临时在 `driver_windows.py` 回填 `from textual._xterm_parser import XTermParser`，确认用例 1 拦截，再还原。

## 五、风险与回滚

- 风险：适配模块只是搬运 import，运行时行为零变化；Textual 私有 API 断裂风险与本轮前持平（收口后反而更易发现）。
- 回滚：单提交 revert。
