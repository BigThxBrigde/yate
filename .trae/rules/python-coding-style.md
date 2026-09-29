---
alwaysApply: true
scene: python_coding
---

## 适用范围

本规则适用于 yate 项目所有 Python 源码（`yate/`、`tools/`、`tests/`）。项目基于 Python 3.12+，使用 pyright strict 模式进行类型检查，**零诊断是合并的硬门槛**。

风格标准是 **PEP 8 + PEP 20 双轨**：PEP 8 管"长什么样"（版式、命名、导入），PEP 20 *The Zen of Python* 管"怎么想"（pythonic 语义）。两者冲突时以 PEP 20 为准，逐条对照与裁决顺序见 §六。

---

## 一、代码风格（PEP 8）

### 1.1 缩进与空格

- 使用 **4 个空格** 缩进，禁止 Tab
- 行宽上限 **100 字符**（项目实测风格），超长时：
  - 函数签名/调用：将参数分行对齐首参数或 4 空格悬挂
  - 长字符串：使用括号隐式拼接（`()`），禁止 `\` 行续
  - 列表/字典/元组：首元素换行，尾逗号保留
- 运算符两侧加空格（`a + b`、`x in y`、`def f(a, b=1):`）
- 逗号后加空格，逗号前不加（`f(1, 2)`、`[1, 2, 3]`）
- `:` 用于字典/切片时，两侧不加空格（`dict[a:b]`）；用于函数定义时，参数列表中不加（`def f(a: int, b: str) -> None:`）
- 函数调用括号内**紧贴内容**（`f(x)` 而非 `f( x )`）
- 括号、方括号、花括号**紧贴内容**，前后无多余空格
- 文件末尾保留**一个空行**
- 函数/类定义之间空 **2 行**；方法定义之间空 **1 行**
- 逻辑块之间（条件分支、循环体末尾）空 **1 行**

### 1.2 命名

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块 | `snake_case` | `logs.py`、`editor_core/` |
| 包 | `snake_case`（单下划线或无前缀） | `yate.editor_lsp` |
| 函数/方法 | `snake_case` | `install()`、`get_logger()` |
| 类 | `PascalCase` | `YateConfig`、`_SessionFileHandler` |
| 常量 | `UPPER_CASE` | `LOGGER_NAME`、`LEVEL_NAMES` |
| 变量/参数 | `snake_case` | `config`、`path` |
| 私有成员 | 单下划线前缀 `_` | `_logger`、`_extract_options()` |
| 强私有 | 双下划线前缀 `__`（仅限 name mangling 必需场景） | `__dict__`（语言内置） |
| 类型变量 | `CamelCase` | `T = TypeVar("T")`（遗留；3.12 起由 PEP 695 语法隐式声明，见 §3.5） |
| 异常 | `PascalCase` + `Error`/`Exception` 后缀 | `LspConnectionError`（`editor_lsp/client.py:76`） |

### 1.3 导入

- 每个模块头部使用 `from __future__ import annotations`（**强制**，见 §四）
- 导入按以下顺序分组，组间空 1 行：
  1. 标准库
  2. 第三方库
  3. 项目内部（`from yate import ...`）
- 每组内部按字母序排列
- 绝对导入优先（`from yate.logs import tracing`），相对导入仅在子包内部使用
- 禁止 `import *`（通配符导入）
- **不得新增 `TYPE_CHECKING` 导入块**（架构约定，见 `architecture-boundaries.md` R6）：
  类型注解跨模块引用时传**具体对象**（`EditorSession` / `KeymapSet` / 注册表 / widget）或叶子类型；
  不再新建窄 Protocol（R2 / R8，唯一冻结例外是 `editor_view/editor.py::PaneRegistry`）

```python
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import IO

from textual.app import App, ComposeResult

from yate.logs import tracing
```

### 1.4 语句与表达式

- 单行 `if`/`for`/`while` 仅限 `pass` 或简单赋值，其余必须分行块
- `if`/`elif`/`else`、`try`/`except`/`else`/`finally`、`with` 之间不加空行
- 布尔判断使用 `if x is not None:` 而非 `if x != None:`；`if x:` / `if not x:` 用于真值测试
- 列表推导式、生成器表达式长度超 80 字符时分行
- 字符串格式化优先使用 f-string（`f"path: {path}"`），其次 `str.format()`，禁止 `%` 格式化（唯一例外：日志用惰性 `%` 占位符，见 §4.6 —— practicality beats purity）

---

## 二、Docstring 规范（PEP 257）

### 2.1 基本规则

- 所有**公共**模块、类、函数、方法必须有 docstring
- 私有函数（`_prefix`）在逻辑复杂时也应加 docstring
- 使用 `"""` 三引号（双引号字符串字面量），首行紧接 `"""` 后
- 单行 docstring：闭合 `"""` 与开头同行
- 多行 docstring：第一行摘要 + 空行 + 详细描述，闭合 `"""` 独占一行

### 2.2 模块 Docstring

- 模块顶部（`from __future__` 之前）放置模块级 docstring
- 第一行简述模块职责
- 后续段落描述关键行为、约束、边界条件
- 可以包含 Usage 示例（使用 `::` 引导 reST 代码块）

```python
"""Unified logging for yate: crash reports and runtime tracing.

:data:`tracing` is opt-in -- a normal session writes nothing and pays
nothing ...

Usage in a module::

    from yate.logs import tracing
    log = tracing.get_logger(__name__)
"""

from __future__ import annotations
```

### 2.3 函数/方法 Docstring

使用**散文式** docstring，第一行摘要（动词开头）+ 空行 + 详细行为描述，结合 **Sphinx 交叉引用**（`:class:`、`:mod:`、`:func:`、`:data:`、`:meth:`、`` `identifier` `` 行内代码），与项目现有代码风格一致。

参数、返回值、异常的描述融入正文，不使用 `:param:` / `:return:` / `Args:` / `Returns:` 等结构化区块标记。

```python
def install(
    yate_trace: bool | None = None,
    yate_trace_level: str | None = None,
) -> bool:
    """(Re)configure tracing and return whether it is on.

    *yate_trace* / *yate_trace_level* are the yaterc fallbacks (``None`` =
    not set; the ``YATE_TRACE*`` env vars always win).  A second call keeps
    the file opened by the first and only adjusts the level, so the two
    startup passes never produce two files or two headers.

    See :meth:`uninstall` and :mod:`yate.cli` for the two call sites.
    """
```

**禁止** 无内容空 docstring（`"""."""`）。至少写一行有意义的摘要。

### 2.4 类 Docstring

- 第一行简述类的职责
- 描述关键属性、不变量、使用约束
- 如有构造参数复杂，可在 docstring 中说明

```python
class ActionRegistry:
    """Maps action names to zero-argument-in-spirit context callables.

    Actions are decoupled from keys: keymaps bind keys to action names,
    and extensions register new ones via :meth:`register`.
    """
```

### 2.5 模块级常量文档

使用 `#:` 注释为模块级常量/类型声明添加说明（与项目风格一致）：

```python
#: Root logger name; every yate logger is ``yate`` or a child of it.
LOGGER_NAME = "yate"

#: Accepted level names -- :mod:`logging`'s built-ins, in increasing order.
LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
```

### 2.6 行内注释

- 行内注释以 `# `（`#` + 空格）开头，放在代码右侧 2 空格以外
- 避免多余注释（代码自解释时不加注释）
- 复杂逻辑、临时 workaround、已知限制必须加注释说明

```python
config.errors.append(
    f"tab_width must be an integer between 1 and 16, got {tab_width!r}"
)

# bool is a subclass of int -- reject it explicitly for this option.
if isinstance(tab_width, int) and not isinstance(tab_width, bool):
```

---

## 三、类型注解（PEP 484 + PEP 526）

### 3.1 强制类型注解

- **所有** 公共函数/方法必须有完整签名注解（参数 + 返回值）
- **所有** 模块级变量和类属性必须有类型注解（PEP 526 变量注解）
- 类型注解是 pyright strict 模式的硬要求，**零诊断是合并门槛**

### 3.2 类型风格

项目观察到的实际风格（**以现有代码为准**）：

- **优先使用 Python 3.9+ 原生小写泛型**：`list[str]`、`dict[str, str]`、`tuple[str, ...]`、`set[int]`。`Dict`/`List`/`Tuple`/`Set`（typing 模块大写版本）视为遗留，新代码不使用
- **可空标注使用 `X | None`（PEP 604）**，不再使用 `Optional[X]`（3.12 基线下的首选写法；
  2026-09-28 核对：升级计划 SP3 的存量迁移**已完成**，全仓（`yate/` + `tests/` + `tools/`）
  `Optional[` 与 `Union[` 均为 **0 处**，新代码不得再引入）
- **联合类型使用 `X | Y`**，不再使用 `Union[X, Y]`（含运行时类型别名，如 `Node = Leaf | Split`；
  3.12 运行时下 `|` 与 `Union[...]` 等价）
- 方法返回自身实例类型时用 `typing.Self`（3.11+），替代字符串前向引用或自建 TypeVar
- 使用 `cast()` 进行显式类型窄化（`cast(Sequence[Any], raw)`）
- 类型注解仅用的导入使用叶子类型，或把类型下移到叶子模块（禁止 `TYPE_CHECKING`；不新建窄 Protocol，见 §4.3 与 `architecture-boundaries.md` R2 / R8）
- 前向引用（引用尚未定义的类）使用字符串字面量：`"YateConfig" | None`
- `from __future__ import annotations` 使所有注解延迟求值，**每个模块必须包含**

### 3.3 `Any` 的使用

- 禁止滥用 `Any`。仅在以下场景使用：
  - 外部库返回值无 stub（可注释说明原因）
  - 动态分发无法静态确定类型
  - 用户输入的原始值（待后续校验窄化）
- `Any` 注释必须附带简短理由（行内 `# noqa: Any - <reason>`）

### 3.4 TypedDict / NamedTuple

- 结构化配置数据优先使用 `@dataclass`（项目现有风格）
- 需要 JSON 序列化的异构映射使用 `TypedDict`
- 不可变、固定字段使用 `NamedTuple` 或 `dataclass(frozen=True)`

### 3.5 泛型（PEP 695，3.12 首选）

新增泛型类/函数一律用 PEP 695 语法，类型别名用 `type` 语句；类型变量由语法隐式声明，
不再手写 `TypeVar` / `Generic`：

```python
# 泛型类：T 的作用域与约束由语法直接表达
class Registry[T]:
    ...

# 带约束/上界的写法
class Cache[K: str, V: object]:
    ...

# 泛型函数
def find_leaf[T](root: Node[T], path: str) -> T | None: ...

# 类型别名（3.12 的 type 语句，惰性求值，替代 TypeAlias）
type Node = Leaf | Split
```

存量代码无 `TypeVar` / `Generic` / `TypeAlias` 实体用法（见升级计划 F4），
如遇遗留写法仅限兼容场景保留，新代码不得再写。

---

## 四、项目特定硬规则

### 4.1 `from __future__ import annotations`（强制）

**每个 `.py` 模块的第一行可执行语句**（docstring 之后）必须是：

```python
from __future__ import annotations
```

理由：
- 让所有类型注解延迟求值，消除前向引用的字符串字面量需求
- 统一 pyright 对注解的处理方式
- 避免运行时类型注解求值导致的循环导入

### 4.2 pyright strict 模式（强制）

- `pyproject.toml` 中 `typeCheckingMode = "strict"`
- 提交前运行 `pyright`，**零诊断才能合并**
- 禁止用 `# type: ignore` / `# pyright: ignore` 静默诊断（极特殊场景需代码评审批准，并附带注释说明理由）

### 4.3 禁止 `TYPE_CHECKING`（架构约定）

**不得新增** `if TYPE_CHECKING:` 导入块。类型注解需要跨模块引用时，按
`architecture-boundaries.md` 的依赖方向处理：传**具体对象**（`EditorSession`、`KeymapSet`、
注册表、widget），或把类型下移到叶子模块；不靠窄 Protocol + 延迟导入兜底。

**现状：全仓库 0 处**（`yate/interfaces.py` 已删除，`tests/test_editor_core.py` 的遗留已随
分层重构清除；架构守护测试 `tests/test_architecture.py` 会拦截回归）。

### 4.4 `cast()` 优先于 `# type: ignore`

当 pyright 无法正确推断类型时（如从 `Any` 值窄化），使用 `cast()` 而非静默忽略：

```python
# 好：显式窄化
entries = list(cast(Sequence[Any], raw))

# 坏：静默忽略
entries = list(raw)  # type: ignore[arg-type]
```

### 4.5 异常处理

- 禁止裸 `except:`（无类型）。必须指定具体异常类型
- 捕获 `Exception` 时必须附带 `noqa: BLE001` 注释（说明为何需要捕获所有异常）
- `except` 块内至少记录日志或向用户反馈；禁止静默吞异常
- 使用 `sys.excepthook` 注册全局异常处理器（见 `yate/logs.py` 的 `crash` 服务）

### 4.6 日志记录

- 使用 `logging` 模块（见 `yate/logs.py` 的 `tracing` 服务），禁止 `print()` 用于调试
- 模块内创建 logger：`log = tracing.get_logger(__name__)`
- 日志消息使用 `%` 格式化占位符（惰性求值）：`log.debug("value: %s", value)`
- **禁止** f-string 直接拼入日志参数：`log.debug(f"value: {value}")` — 在 DEBUG 级别关闭时仍会求值

### 4.7 测试规范

- 测试框架：`pytest`
- 测试文件命名：`test_<module_name>.py`，放 `tests/` 目录
- 测试函数命名：`def test_<behavior>_<condition>_<expected>():`
- 测试使用 fixtures 共享 setup/teardown，避免重复代码
- 断言使用 `pytest.raises()` / `pytest.warns()` 验证异常路径
- 运行前确保 `pytest tests/ -q` 全部通过

---

## 五、快速检查清单

提交前确认：

- [ ] `from __future__ import annotations` 在 docstring 之后、其他导入之前
- [ ] pyright strict 零诊断
- [ ] 所有公共函数/类有 docstring
- [ ] 类型注解完整（参数 + 返回值 + 变量注解）
- [ ] 可空/联合标注用 `X | None` / `X | Y`（不写 `Optional[X]` / `Union[X, Y]`）；覆写基类方法加 `@override`
- [ ] 4 空格缩进，行宽 ≤ 100
- [ ] 无 `import *`
- [ ] 无裸 `except:`
- [ ] `Any` 使用有理由注释
- [ ] 嵌套 ≤ 3 层，卫语句早返回（Flat is better than nested）
- [ ] pythonic 写法按 §6.2 首选：真值测试 / 推导式 / 解包 / `enumerate` / `with`；但可读性优先，不做技巧堆砌
- [ ] 无静默吞异常：每个 `except` 块记日志或向用户反馈（PEP 20: errors should never pass silently）
- [ ] `pytest tests/` 全部通过

---

## 六、PEP 20：The Zen of Python（与 PEP 8 的结合）

PEP 8 管"长什么样"，PEP 20 管"怎么想"。PEP 8 官方开篇即引用
*"A Foolish Consistency is the Hobgoblin of Little Minds"*——风格规则是 PEP 20 的
下游手段而非目的：当字面遵守 PEP 8 反而伤害可读性时，以 PEP 20 为准。
Zen 全文速查：`python -m this`。模式速查另可参照《Pythonic：Python 语言习惯和哲学的代码风格》
（<https://jishuzhan.net/article/1945060183000002562>）。

### 6.1 Zen 原则 → 本仓库落地规则对照

| Zen 原则 | 本仓库的落地 |
|---|---|
| Beautiful is better than ugly / Readability counts | §一 版式与命名；宁可多写三行，不写难读的一行 |
| Explicit is better than implicit | 跨层传具体对象、不造窄协议（`architecture-boundaries.md` R8）；可空显式写 `X | None`（§3.2）；不写隐式魔法 |
| Simple is better than complex | 能用函数实现的就不造类（`architecture-boundaries.md` §三.6）；不为假设性需求加抽象 |
| Complex is better than complicated | 复杂度无法回避时，用显式结构（dataclass / 明确分支）表达，不堆砌嵌套技巧 |
| Flat is better than nested | 卫语句早返回，嵌套 ≤ 3 层（见 §6.2） |
| Sparse is better than dense | §1.1 空行与分组；一行只做一件事 |
| Special cases aren't special enough to break the rules | 禁止 `# type: ignore` 豁免诊断（§4.2）；架构测试不得用豁免注释绕过 |
| Although practicality beats purity | 行宽 100 而非 79（§1.1）；日志用惰性 `%` 占位符而非 f-string（§4.6）；存量遗留写法仅限兼容场景保留（§3.5） |
| Errors should never pass silently / Unless explicitly silenced | §4.5：禁止裸 `except:`；每个 `except` 块必须记日志或反馈——"silenced" 只指显式捕获并记录 |
| In the face of ambiguity, refuse the temptation to guess | 类型注解完整 + pyright strict 零诊断（§三.1 / §4.2）；边界输入显式校验，不做隐式猜测转换 |
| There should be one-- and preferably only one --obvious way to do it | 全仓统一一种写法：`X | None` 而非 `Optional[X]`（§3.2）、PEP 695 泛型而非 TypeVar（§3.5）、f-string 而非 `%` / `.format()`（§1.4） |
| Now is better than never / Although never is often better than *right* now | 小步及时合入；但半成品不入库——pyright / pytest 全绿才是合并门槛（§4.2 / §4.7），无实测依据的预优化不做 |
| If the implementation is hard to explain, it's a bad idea | §二：难以解释的实现先重构再注释；docstring 解释不了的设计就是坏设计 |
| Namespaces are one honking great idea | 包 `__init__.py` 保持惰性、不 re-export 子模块符号（`architecture-boundaries.md` §三.5）；不建中央接口文件 |

（未列出的 Zen 条目为元幽默或语境性表述，不映射工程规则。）

### 6.2 pythonic 写法对照（首选 vs 避免）

**卫语句早返回（Flat is better than nested）**

```python
# 首选：卫语句先排除边界，主干不缩进
def find_leaf(root: Node | None, path: str) -> Leaf | None:
    if root is None or not path:
        return None
    ...

# 避免：主干整体嵌套在 if 里，两层缩进才到正题
def find_leaf(root: Node | None, path: str) -> Leaf | None:
    if root is not None:
        if path:
            ...
```

**真值测试（Readability counts）**

```python
if not items: ...          # 首选：空容器与 None 的"没有"语义统一时
if obj is None: ...        # 首选：None 判断必须用 is
if len(items) == 0: ...    # 避免
if obj == None: ...        # 禁止
```

**链式比较（Readability counts）**

```python
if 0 < x < 10: ...          # 首选：链式比较，语义与数学一致，中间项只求值一次
if x > 0 and x < 10: ...    # 避免
```

**推导式与生成器（One obvious way）**

```python
# 首选：映射 + 过滤一步到位
names = [p.name for p in plugins if p.enabled]

# 避免：手动 append 循环
names = []
for p in plugins:
    if p.enabled:
        names.append(p.name)
```

超过 80 字符（§1.4）或需要嵌套两层 for/if 时改回普通循环——可读性优先于"用了推导式"。

**enumerate / zip 替代下标循环**

```python
for i, item in enumerate(items, start=1): ...   # 首选
for x, y in zip(xs, ys): ...                     # 首选：并行遍历
for i in range(len(items)): ...                  # 避免
```

**解包与交换（Explicit）**

```python
first, second = pair                 # 结构化解包
first, *rest = items                 # 头尾分离
a, b = b, a                          # 交换
name, ext = filename.rsplit(".", 1)  # 比下标 [0] / [1] 更显式
```

**默认参数与可变默认值（Explicit）**

```python
def greet(name: str = "stranger") -> None: ...   # 首选：默认参数简化调用签名

# 禁止：可变默认参数——默认值只在定义时求值一次，跨调用共享同一个对象
def add(item: str, items: list[str] = []) -> None: ...

# 首选：None 哨兵 + 函数体内新建（生产环境标准做法）
def add(item: str, items: list[str] | None = None) -> None:
    target = [] if items is None else items
    ...
```

**容器成员与元组匹配**

```python
if ch in "aeiou": ...                              # 首选：成员测试
if target in items: ...                            # 首选：替代手工 found 标志循环
if name.startswith(("test_", "spec_")): ...        # 首选：startswith / endswith 接受元组
isinstance(x, (int, float))                        # isinstance 同样接受元组
if ch == "a" or ch == "e" or ch == "i": ...        # 避免
if name.startswith("test_") or name.startswith("spec_"): ...  # 避免
```

手工 found 标志循环（遍历 + `break` + 事后 `if found:`）一律用 `in` 成员测试替代。

**EAFP：只在密集路径用（Errors should never pass silently 的正面用法）**

```python
# 密集循环内"先查后取"（LBYL 两次查表）→ 首选 EAFP
try:
    value = mapping[key]
except KeyError:
    value = default

# 一次性的简单场景，条件表达式更直白，不必强行 try
value = mapping[key] if key in mapping else default
```

规则：`try` 只包会抛的那一行；`except` 捕获具体异常；不为"省一次判断"写 EAFP，
更不允许 EAFP 成为静默吞异常的借口（§4.5）。

**上下文管理器（Simple is better than complex）**

```python
with path.open(encoding="utf-8") as f: ...   # 首选
f = path.open(encoding="utf-8")              # 避免：手动 try/finally close
```

**纠偏：pythonic ≠ 技巧堆砌**

以上对照是"首选"，不是"必须"。一行塞三个推导式、lambda 链、炫技切片都违反
Beautiful is better than ugly。判断标准：换一个人第一次读，能否在一遍内看懂。

### 6.3 规则冲突时的裁决顺序

1. **正确 > 清晰 > 简短 > 快**：先保证行为正确，再保证读得懂；性能优化必须以
   profiler 实测为前提，不做预优化。
2. **可读性 > 风格一致性**：PEP 8 自身的例外条款——不要为了一致而一致
   （A Foolish Consistency is the Hobgoblin of Little Minds）。
3. **显式 > 隐式**：两种写法都合规时，选更显式的那个。
