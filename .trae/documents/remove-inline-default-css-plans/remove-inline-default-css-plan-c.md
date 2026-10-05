# remove-inline-default-css plan-c：资源化守卫测试（wave-2）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> 依赖 plan-a（缓存用例）与 plan-b（AST 扫描要求 `yate/**` 已零内联），
> 故置于 wave-2 串行执行。

## 一、目标

把 issue 的约定固化为防回归守卫：`yate/` 下任何 widget 类的 `DEFAULT_CSS`
只能是 `load_tcss("<name>.tcss")`，内联字符串字面量永久禁入；
同时守住 loader 的缓存与 fail-fast 契约。

## 二、具体修改

扩展 `tests/test_app_css.py`（现有 2 个 app.tcss 用例保留），模块 docstring
更新为"守卫所有 Textual 样式表的资源化装载"，新增 4 个用例：

### 1. `test_widget_default_css_comes_from_load_tcss`

- **验证点**：issue IKJHPH 第 1 点（py 零内联 CSS）。
- **前置**：无需 fixture；AST 解析 `yate/` 下全部 `*.py`
  （实现参照 `tests/test_architecture.py` 的遍历模式）。
- **操作**：遍历每个 `ast.ClassDef` 的 `DEFAULT_CSS` 赋值节点，断言：
  值是 `ast.Call`、被调名为 `load_tcss`、恰一个 `str` 常量实参；
  且该实参指向的 `yate/resources/<arg>` 文件真实存在
  （静态拦截资源名拼错，不必等运行时 fail-fast）。
- **断言失败信息**：带 `文件:行号` 与违规形态。

### 2. `test_bundled_tcss_resources_are_nonempty`

- **验证点**：issue 第 2 点（样式统一在资源目录且真实有效）。
- **操作**：`importlib.resources.files("yate.resources")` glob `*.tcss`，
  逐个 `read_text`，断言非空白且含 `{`（至少一条规则）。
- **边界**：若某 tcss 被清空/删除，本用例先于 UI 冒烟报警。

### 3. `test_load_tcss_returns_cached_string`

- **验证点**：issue 第 3 点（只加载一次、内存消费）——plan-a 的 `lru_cache`。
- **操作/断言**：`a = load_tcss("app.tcss"); b = load_tcss("app.tcss");
  assert a is b`（lru_cache 命中返回同一对象；`str` 不可变，身份断言安全）。

### 4. `test_load_tcss_missing_resource_raises_runtime_error`

- **验证点**：`load_tcss` 的 fail-fast 契约（`yate/paths.py:66-72`）在缓存
  引入后不回退（异常不入 lru_cache，每次缺失都抛）。
- **操作/断言**：`pytest.raises(RuntimeError, match="could not be read")`
  包裹 `load_tcss("no-such-stylesheet.tcss")`。

## 三、负向演练（仓库守卫惯例）

临时把任一组件（如 `yate/editor_view/statusbar.py`）的 `DEFAULT_CSS` 改回
字符串字面量 → 运行用例 1 必须失败（exit 非 0）→ 还原 → 重跑全绿。
演练结果（命令与退出码）回填本文档 §五。

## 四、验收命令（worktree 根执行）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/test_app_css.py tests/test_explorer.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ -q
```

通过判定：pyright 零诊断；三段 pytest 均 exit 0（守卫用例 + 被搬运内容等价性
回归 + 架构守护无意外联动）。

## 五、执行结果回填

（执行后填写：负向演练命令输出摘要、退出码、全量门禁数字。）

## 六、提交

`test(css): guard that widget default css is loaded from bundled tcss`
