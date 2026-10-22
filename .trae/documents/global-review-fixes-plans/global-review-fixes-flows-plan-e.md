# plan-e：L3 流程 / L4 外壳 / services 修复

- 波次：wave-3（依赖 wave-1 / wave-2 验收通过）
- 覆盖：W-01 / W-02 / W-03 / S-01 / S-02 / S-03 / S-04 / S-05 / S-06
- 独占文件清单：
  - `yate/yaterc_options.py`
  - `yate/flows/prompt_flows.py`
  - `yate/flows/document_flows.py`
  - `yate/app.py`
  - `yate/editor.py`
  - `yate/config.py`
  - `yate/diagnostics.py`
  - `yate/editor_view/theme.py`
  - `yate/services/data_store.py`
  - `yate/services/user_setup.py`
  - `yate/services/extensions/api.py`
  - `tests/test_yaterc_options.py`
  - `tests/test_app_find.py`
  - `tests/test_app_textual.py`
  - `tests/test_app_explorer.py`
  - `tests/test_data_store.py`
  - `tests/test_user_setup.py`
  - `tests/test_theme_palettes.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-01：[yaterc_options.py](../../yate/yaterc_options.py) 第 596-603 行
  `ft.lstrip(".")` 不去空白。
- W-02：[prompt_flows.py](../../yate/flows/prompt_flows.py) 第 139-150 行
  `n` 分支自增 `_confirm_done`；第 183-190 行用它生成 “replaced N”。
- W-03：[document_flows.py](../../yate/flows/document_flows.py) 第 170-205 行
  未捕获 `session.open` / `open_async` 的 `OSError`。
- S-01：[app.py](../../yate/app.py) 第 104-110 行把 `theme` 原样传给精确匹配的
  `set_theme`；[theme.py](../../yate/editor_view/theme.py) 第 98-110 行不归一化。
- S-02：[config.py](../../yate/config.py) 第 65-66 行与
  [diagnostics.py](../../yate/diagnostics.py) 第 171 行 `Any` 缺 `# noqa` 理由。
- S-03：[editor.py](../../yate/editor.py) 第 727-731 行 ctrl+space 分支位于
  `prompt_bar.active_mode` 早返回之前。
- S-04：[data_store.py](../../yate/services/data_store.py) 第 54-56 行盘符检查
  只覆盖 `C:`（len==2），漏 `C:foo/bar`。
- S-05：[api.py](../../yate/services/extensions/api.py) 第 254-267 行
  `buffer` / `doc` / `workspace` 缺返回注解。
- S-06：[user_setup.py](../../yate/services/user_setup.py) 第 274-275 行
  `any(base.iterdir())` 在 try 之外。

## 二、分步修改

### 步骤 E1：W-01 filetypes 去空白

**文件**：`yate/yaterc_options.py`

第 598 行改为：

```python
    filetypes = [ft.strip().lstrip(".") for ft in filetypes]
```

`_require_str_list` 已拒绝纯空白项，`.strip()` 后为空只可能来自 `"."`/`".."`，
沿用第 599-603 行既有拒绝路径。

### 步骤 E2：W-02 独立“已替换”计数器

**文件**：`yate/flows/prompt_flows.py`

1. `__init__` 第 41 行后加 `self._confirm_replaced: int = 0`。
2. `_do_replace` 第 114 行后加 `self._confirm_replaced = 0`。
3. `y` 分支：

```python
            if self.session.search.replace_current(
                self.session.buffer, self._replacement
            ):
                self._confirm_done += 1
                self._confirm_replaced += 1
```

4. `n` 分支保留 `self._confirm_done += 1`，不再表示已替换。
5. `_finish_or_advance` 的结束语改用 `self._confirm_replaced`。
6. `_end_confirm` 重置 `self._confirm_replaced = 0`。

### 步骤 E3：W-03 打开文档捕获 `OSError`

**文件**：`yate/flows/document_flows.py`

同步路径：

```python
        try:
            doc = self.session.open(path)
        except OSError as exc:
            self._report(f"cannot open {path.name}: {exc}", "warn")
            log.warning("open failed: %s (%s)", path, exc)
            return None
```

异步路径：

```python
        try:
            doc = await self.session.open_async(path)
        except OSError as exc:
            self._report(f"cannot open {path.name}: {exc}", "warn")
            log.warning("open failed (async): %s (%s)", path, exc)
            return None
```

（日志用惰性 `%` 占位符。）

### 步骤 E4：S-01 主题名单点归一化

**文件**：`yate/editor_view/theme.py`

`set_theme` 开头加：

```python
    name = name.strip().lower()
```

docstring 补一句“name is normalized (stripped and lower-cased) before lookup”。

**文件**：`yate/app.py`（可选的一致性收口）

第 105 行改为：

```python
        wanted_theme = (
            theme_name if theme_name is not None else self.config.theme
        ).strip().lower()
```

保留原有 `KeyError` 报告路径。

### 步骤 E5：S-02 `Any` 注解理由

**文件**：`yate/config.py`

```python
    initialization_options: Any = None  # noqa: Any - arbitrary LSP JSON
    settings: Any = None  # noqa: Any - arbitrary LSP JSON
```

**文件**：`yate/diagnostics.py`

```python
def _kv(key: str, value: Any, *, width: int = 18) -> str:  # noqa: Any - probe values span arbitrary types
```

### 步骤 E6：S-03 命令行激活时不吃 ctrl+space

**文件**：`yate/editor.py`

`nul_keys` 分支改为：

```python
        if event.key in nul_keys and not self.prompt_bar.active_mode:
            if editor_focused or event.key == "ctrl+space":
                self.completion.request(manual=True)
                return True
```

`prompt_bar.active_mode` 时该键继续向下（后续 `if self.prompt_bar.active_mode:
return False` 使其交给 Input）。

### 步骤 E7：S-04 盘符相对路径

**文件**：`yate/services/data_store.py`

```python
    drive_prefix = len(first) >= 2 and first[1] == ":"
```

（`first` 为空时 len 0，安全；`C:foo` 在任何平台都被拒绝。）

### 步骤 E8：S-05 三个属性返回注解

**文件**：`yate/services/extensions/api.py`

新增导入：

```python
from yate.editor_core.buffer import TextBuffer
from yate.editor_core.document import Document
```

（`Workspace` 已导入。）签名改为：

```python
    def buffer(self) -> TextBuffer:
    def doc(self) -> Document:
    def workspace(self) -> Workspace:
```

### 步骤 E9：S-06 空目录探测兜底

**文件**：`yate/services/user_setup.py`

```python
    base_removed = False
    try:
        empty = not any(base.iterdir())
    except OSError as exc:
        # Report instead of escaping from the error-collecting function.
        errors.append(f"{base.name}/: {exc}")
        empty = False
    if empty:
        try:
            base.rmdir()
            ...
```

## 三、新增测试

### `tests/test_yaterc_options.py`

1. `test_extract_language_servers_strips_filetype_whitespace`
   - 输入：`filetypes: [" py ", ".rs "]`
   - 断言：`spec.filetypes == ["py", "rs"]`，无 config.errors。

### `tests/test_app_find.py`

2. `test_f4_confirm_loop_counts_only_actual_replacements`
   - 准备：文本 `"cat cat cat"`。
   - 操作：`_press_f4_replace(pilot, "cat", "dog")` 后依次按 `y`, `n`, `y`。
   - 断言：文本 `"dog cat dog"`；消息含 `"replaced 2 occurrence(s)"`。

### `tests/test_app_textual.py`

3. `test_open_document_reports_oserror_instead_of_crashing`
   - 准备：`monkeypatch.setattr(app.editor.session, "open", _raise_permission)`
     （抛 `PermissionError("denied")`）。
   - 操作：`app.editor.document_flows.open_path(tmp_path / "x.txt")`
   - 断言：不抛异常；消息行含 `"cannot open x.txt"` 与 `"denied"`。
4. `test_open_document_async_reports_oserror`
   - 准备：`monkeypatch.setattr(app.editor.session, "open_async", _raise_permission_async)`
   - 操作：`await app.editor.document_flows.open_path_async(path)`
   - 断言：返回 `False`；消息行含 `"cannot open"`。
5. `test_ctrl_space_with_the_command_prompt_active_does_not_open_completion`
   - 准备：vim 键位，按 `:` 打开命令行并输入 `e`。
   - 操作：`pilot.press("ctrl+space")`。
   - 断言：`app.editor.completion_popup.is_open is False`；
     `app.editor.prompt_bar.active_mode` 仍为 `"command"`。

### `tests/test_theme_palettes.py`

6. `test_set_theme_normalizes_case_and_whitespace`（与 plan-d 第 6 条同名，
   由本计划负责落地；plan-d 不重复添加）。
   - 操作：`theme.set_theme("  MoChA  ")`；`finally` 恢复 `"mocha"`。
   - 断言：`theme.active().name == "mocha"`。

### `tests/test_data_store.py`

7. 在既有参数化 `test_rejects_absolute_and_traversal_names` 的 `name` 列表补
   `"C:foo/bar"` 与 `"d:relative.json"`。

### `tests/test_user_setup.py`

8. `test_cleanup_reports_an_unreadable_base_directory`
   - 准备：`_populate(base)`；`monkeypatch.setattr(Path, "iterdir", _raise_oserror)`
     （抛 `OSError("access denied")`）。
   - 操作：`us.cleanup_defaults(force=True, include_data=True, base_dir=base)`
   - 断言：`report.base_removed is False`；`any("access denied" in e for e in report.errors)`。

### `tests/test_diagnostics.py` / `tests/test_config.py`

9. 无新增用例；`Any` 注解由 pyright strict 与 `# noqa` 文本检查覆盖。

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaterc_options.py tests/test_app_find.py tests/test_app_textual.py tests/test_data_store.py tests/test_user_setup.py tests/test_theme_palettes.py -q
.venv\Scripts\python.exe -m pyright yate/yaterc_options.py yate/flows yate/app.py yate/editor.py yate/config.py yate/diagnostics.py yate/editor_view/theme.py yate/services tests/test_yaterc_options.py tests/test_app_find.py tests/test_app_textual.py tests/test_data_store.py tests/test_user_setup.py tests/test_theme_palettes.py
```

通过判定：两条命令退出码均为 0。

## 五、风险与回滚

- W-02 只改计数口径，不改确认循环的终止条件（`_confirm_done` 仍按 y/n 增长）。
- W-03 的 `OSError` 捕获只包围 `open` 调用；目录探测的既有 `OSError` 语义不变。
- S-01 在 `set_theme` 单点归一化后，`--theme " Mocha "` 与扩展 API 同时受益；
  `KeyError` 消息中的 name 已是归一化名。
- S-03 只拦 ctrl+space，其余全局 chord 原顺序不变。
- 回滚：本子计划单独提交。
