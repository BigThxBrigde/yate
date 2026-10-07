# 子计划 plan-e：re-export 成文例外与 editor_lsp 定向收敛（A1）

> 所属波次：**wave-2**（与 keyproto-plan-b 文件不重叠，可并行；两者均主代理执行）。
> 执行者：**主代理**（改 `yate/` 产品源码）。
> 来源：评审 A1；选型论证主计划 §四.1（采用路线 (b')，否决全面禁止）。

## 一、输入

- 五个 L0 叶包 `__init__.py` re-export（`editor_core/__init__.py:12-27`、`editor_lsp/__init__.py:18-36`、`editor_syntax/__init__.py:25-49`、`editor_term/__init__.py:9-21`、`keymaps/__init__.py:11-29`）与规则 §三.5 "不 re-export" 两套做法并存；
- 唯一实质惰性违规：`import yate.editor_lsp` 连带加载 818 行 `manager.py`；
- 消费方实测（`from yate.editor_lsp import LspManager` 等，需改为子模块路径的 8 处）：
  `yate/services/extensions.py:41`、`yate/lsp_sync.py:21`、`yate/editor_view/statusbar.py:20`、`yate/editor_view/editor.py:22`、`yate/editor.py:35`、`yate/document_flows.py:28`、`yate/completion.py:21`、`tests/test_lsp.py:21`；
- 插件 API 契约：`yate/docs/extensions.en.md:307` / `extensions.zh.md:281` 明文示例 `from yate.editor_syntax import LangSpec`——re-export 是文档承诺的公共 API 面。

## 二、独占文件清单

1. `yate/editor_lsp/__init__.py`（移除 `LspManager` re-export，保留 client 轻量符号，docstring 注明例外）
2. `yate/editor_core/__init__.py`、`yate/editor_syntax/__init__.py`、`yate/editor_term/__init__.py`、`yate/keymaps/__init__.py`（仅 docstring 各加一行例外注明，re-export 不动）
3. 消费方 7 处改子模块 import：`yate/services/extensions.py:41`、`yate/lsp_sync.py:21`、`yate/editor_view/statusbar.py:20`、`yate/editor_view/editor.py:22`、`yate/editor.py:35`、`yate/document_flows.py:28`、`yate/completion.py:21`（改为 `from yate.editor_lsp.manager import LspManager`）
4. `tests/test_lsp.py:21`（同上）
5. `tests/test_architecture.py`（新增守卫用例，见 §四）
6. `.trae/rules/architecture-boundaries.md` §三.5（三层表述修订）

## 三、具体修改

### 3.1 editor_lsp/__init__.py

- 删除 `from yate.editor_lsp.manager import LspManager` 与 `__all__` 中的 `"LspManager"`；
- docstring 追加例外注明段："The package root re-exports the lightweight client data types
  (public API shared with extensions); the heavyweight `LspManager` deliberately lives
  only in `yate.editor_lsp.manager` so importing the package root stays cheap. This is
  the documented exception to the lazy-`__init__` rule (architecture-boundaries §三.5)."

### 3.2 其余四包 docstring

各加一行（措辞按包语境调整）："The re-exports below are the documented public API
exception (architecture-boundaries §三.5): pure-leaf packages may re-export their
public surface; UI/service packages may not."

### 3.3 规则 §三.5 修订

原文："包 `__init__.py` 保持惰性：不 re-export 子模块符号，避免 `import yate.X` 连带加载整层。"
改为三层表述：
1. 包 `__init__.py` 默认惰性：不 re-export 子模块符号，避免 `import yate.X` 连带加载整层；
2. UI / 服务包（`editor_view` / `services`）禁止 re-export（现状惯例成文化，`editor_view/__init__.py:23-26`、`services/__init__.py:3-7` 为范本）；
3. 纯 L0 叶包（`editor_core` / `editor_syntax` / `editor_term` / `keymaps`）允许**有限** re-export 作为插件公共 API 面，且**重量级实现模块**（如 `editor_lsp.manager`）不得进包根——例外须在各包 `__init__.py` docstring 注明（2026-10 评审 A1 定案，路线 b'）。

同步登记 R2 无关、R 条款不变；`python-coding-style.md` 无需联动。

## 四、新增测试与验证方案

`tests/test_architecture.py` 新增守卫用例：

1. `test_editor_lsp_package_root_is_light`
   - 前置：无（AST 静态扫描，风格与既有 `test_no_type_checking` 一致）；
   - act：AST 解析 `yate/editor_lsp/__init__.py` 的 import 语句；
   - 断言：不存在 `from yate.editor_lsp.manager import ...`（或 `import yate.editor_lsp.manager`）——证明包根不再连带加载 818 行实现模块；守卫 R 无关项：§三.5 第 3 层"重量级模块不进包根"。
2. `test_leaf_package_reexports_carry_exception_note`
   - 前置：无；
   - act：读五个包 `__init__.py` 文本；
   - 断言：含 re-export 的包 docstring 均含 "§三.5" 或 "architecture-boundaries" 例外注明——防止未来新增 re-export 包不带例外说明（规则与实现不再次分叉）。

验证命令（退出码 0）：

```powershell
.venv\Scripts\python.exe -c "import yate.editor_lsp, sys; assert 'yate.editor_lsp.manager' not in sys.modules; print('lazy ok')"
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_lsp.py tests/test_extensions.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
```

负向演练：临时在 `editor_lsp/__init__.py` 回填 manager 导入，确认两条新用例 + import 探针失败，再还原。

## 五、风险与回滚

- 风险：插件/用户代码若直接 `from yate.editor_lsp import LspManager` 会 break——插件面向的注册通道是 `api.lsp`（`LspExtensionBridge`），`LspManager` 属宿主内部类型，破坏面可忽略；CHANGELOG 增加一条 developer-facing 变更记录（wave-6 汇总）。
- 回滚：单提交 revert（含规则文本），无数据迁移。
