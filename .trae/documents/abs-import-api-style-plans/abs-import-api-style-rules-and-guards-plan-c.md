# plan-c：规则落盘 + 架构守卫 + 议题 2/3 审查记录（wave-2）

> 隶属 [主计划](../abs-import-api-style-plan.md)。**串行依赖**：wave-1（plan-a ∥ plan-b）全部验收通过后才执行——新增守卫覆盖 `yate/` + `tests/` + `tools/` 全域，提前加入会中途红。
> 独占文件域：`../rules/python-coding-style.md`、`tests/test_architecture.py`（与 wave-1 零重叠）。

## 一、输入

- wave-1 完成态：`yate/` 与 `tools/` 相对导入已归零（各自验收命令退出码 0）。
- 主计划 §二 议题 2 / 议题 3 的证据与裁定；§三.2 例外甄别。

## 二、改动 1：python-coding-style.md §1.3 重写（议题 1 落盘）

文件：[../../rules/python-coding-style.md](../../rules/python-coding-style.md)

**改写位置**：§1.3 第 5 条（现第 55 行）「绝对导入优先（`from yate.logs import tracing`），相对导入仅在子包内部使用」→ 替换为：

```markdown
- **包内一律使用绝对导入**（issue IKKS4C）：同一包内的模块互引也写全限定路径
  （`from yate.editor_view.icons import CHECK`，而非 `from .icons import CHECK`）；
  `from .X` / `from ..X` 形态禁止出现在 `yate/`、`tools/`、`tests/` 任何位置。
  例外登记：无。
```

并紧跟正反例代码块：

```python
# 好：包内互引同样写全限定绝对路径
from yate.editor_view import theme
from yate.editor_view.icons import CHECK

# 坏：相对导入（同包内也不允许）
from . import theme
from .icons import CHECK
from .._util import repo_root
```

同步把 §五 快速检查清单增补一项：`- [ ] 无相对导入（from . / from ..），包内一律绝对导入`。

## 三、改动 2：python-coding-style.md §1.2 增补（议题 2 + 议题 3 #2 落盘）

### 3a. 修正包名行（现第 37 行）

现文本「包 | `snake_case`（单下划线或无前缀） | `yate.editor_lsp`」表述含混（"单下划线或无前缀"不知所指），改为：

```markdown
| 包 | `snake_case`，单词用下划线分隔、不用 CamelCase | `yate.editor_lsp`、`yate.editor_view` |
```

### 3b. 新增「开放 API 命名」条款（§1.2 末尾追加）

```markdown
**开放 API 命名（issue IKKS4C）**：开放 API 的公共成员禁止下划线前缀，私有实现
必须带下划线。开放 API 指以下三个面的交集：
1. 纯 L0 叶包 `__init__.py` 的有限 re-export（`__all__` 声明，见
   architecture-boundaries.md §三.5）；
2. `yate/services/extensions.py` 的 `ExtensionAPI` / `ExtensionContext` 及其
   bridge 类的公共成员；
3. 插件手册 `yate/docs/extensions.en.md` / `extensions.zh.md` 引用的成员名。

登记例外（内部私有，不属开放 API，保留下划线）：
`_TsPoint` / `_TsNode`（`editor_syntax/ts_backend/backend.py`，R2 冻结白名单
私有结构化类型）、`_from_utf16` / `_to_utf16`（`editor_lsp/parsing.py` 包内
解析辅助）、`_shared`（`editor_sprites/chars/` 包内私有数据模块）、
`_WelcomeRow`（`editor_view/welcome.py`，L2 组件内部）。
```

### 3c. 议题 3 其余修正

§1.3 无其他文本问题；议题 3 表 #4（extensions.py 导入排序）已由 plan-a 完成；#5-#8 观察项不动（主计划 §二 表格为审查记录，随本计划一并归档）。

## 四、改动 3：test_architecture.py 新增守卫（防回归）

文件：[tests/test_architecture.py](../../../tests/test_architecture.py)

### 4a. 模块 docstring 增补 bullet（插到 R12 bullet 之后）

```python
* **Absolute imports** (issue IKKS4C): packages import absolutely -- no
  ``from .X`` / ``from ..X`` anywhere in ``yate/`` / ``tools/`` / ``tests/``
  (python-coding-style 1.3); intra-package references spell the full path.
```

### 4b. 新增用例（追加在 `test_no_type_checking` 之后）

```python
def test_no_relative_imports() -> None:
    """Packages import absolutely: ``from .X`` / ``from ..X`` is banned
    everywhere (issue IKKS4C, python-coding-style 1.3) -- intra-package
    references spell the full path, so import intent is greppable and the
    rule text cannot drift from the code."""
    offenders: list[tuple[str, int]] = []
    for path in _python_files():
        tree = _parsed_tree(path)
        rel = path.relative_to(PROJECT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                offenders.append((rel, node.lineno))
    assert not offenders, offenders
```

**用例三要素**：

- **前置条件**：wave-1 已把 `yate/`（72 处）与 `tools/`（94 处）相对导入清零；`tests/` 现状 0 处（主计划 §二）。`_python_files()`（`tests/test_architecture.py:239-247`）覆盖三目录并排除守卫文件自身；`_parsed_tree`（:651-658）按 (path, mtime) 缓存 AST。
- **操作**：AST 遍历每个 `ast.ImportFrom` 节点，`node.level > 0` 即相对导入（`from .` 与 `from ..` 都被拦截；`import .x` 不是合法语法无需处理）。
- **断言**：`offenders == []`，失败信息含文件相对路径 + 行号。
- **负向验证（一次性演练，参照 IKJB0Q 模式）**：在任一文件（如 `yate/paths.py`）临时加入 `from . import os` → 运行用例确认红 → 还原 → 确认绿。演练后不留任何痕迹。

### 4c. 计数说明

用例落位后架构测试为 **29 个**；架构规则文档 §六 的用例对照表（[../../rules/architecture-boundaries.md](../../rules/architecture-boundaries.md)）下次触碰该文件时再同步补行（本计划不改架构规则文本，避免无关 diff——登记为待办而非静默遗漏）。

## 五、议题 2 审查结论（零整改，记录归档）

三源交叉核对（主计划 §二 议题 2）结论：现有开放 API **无**带下划线的公共成员，无「无下划线但实为内部」的误暴露；5 个下划线成员甄别为内部私有并登记于 §三.3b 的例外清单。**不改任何代码、不改双语手册**——手册 `api.*` 面与代码一致（双语同步约束因此不触发）。

## 六、输出与验收命令（worktree 根执行）

```powershell
# 1. 类型门禁零诊断
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/

# 2. 架构守护全绿（含新用例，共 29 个）
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q

# 3. 负向演练（手工，演练后还原）：见 §四.4b，预期加一行相对导入后用例红、还原后绿

# 4. 全量回归
.venv\Scripts\python.exe -m pytest tests/ -q
```

通过标准：pyright 零诊断；`test_no_relative_imports` 通过且负向演练拦截有效；既有 28 守卫零回归。

## 七、风险与回滚

- 风险：守卫范围含 `tests/`——pytest 插件或 conftest 未来若需相对导入（无已知场景，`tests/` 非 `__init__.py` 包）会被拦；届时须先改规则文本再调守卫（两处同步，主计划 §六 #3）。
- 规则文本改动为纯文档 + 测试，遵循 doc-conventions（相对路径引用）；架构规则 §六 对照表补行登记为待办（§四.4c）。
- 回滚：本计划单独 commit；`git revert` 即同时还原规则文本与守卫用例（同 commit 保证两处不漂移）。
