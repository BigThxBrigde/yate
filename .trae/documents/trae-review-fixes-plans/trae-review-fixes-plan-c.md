# plan-c（W-C）：顶层模块 / flows / keymaps — 7 条

- 波次：W-C（依赖 W-A；与 W-B / W-D 并行）
- 独占文件（**只改这些**）：`yate/keymaps/vim.py`、`yate/keymaps/registry.py`、`yate/flows/document_flows.py`、
  `yate/yaterc.py`、`yate/session.py`、`yate/app.py`；
  测试：`tests/test_vim_keymap.py`、`tests/test_keymap_set.py`、`tests/test_session.py`、
  `tests/test_yaterc_options.py`、`tests/test_app_textual.py`
- 输入：评审记录 §四 B-2、§五 M-5/M-6、§六 m-7/m-16/m-21/m-22

## 1. B-2（BLOCKER）`yate/keymaps/vim.py:1241-1248` `{count}G` 越界

**修法**：

```python
if count is not None:
    r = max(0, min(count - 1, len(buf.lines) - 1))
else:
    r = len(buf.lines) - 1
```

（`select` 分支 :1245 与普通分支 :1248 共用钳位后的 `r`。）

**回归测试**（`tests/test_vim_keymap.py`，修复前必须红）：
- `test_gg_with_count_beyond_the_last_line_clamps_to_the_last_line`（3 行文档 `5G` → 光标 `(2, …)`，不抛）
- `test_visual_G_with_count_beyond_the_last_line_clamps`（VISUAL 下 `5G`）
- 既有 `2G` / `3gg` 用例保持绿

## 2. M-5（MAJOR）`yate/flows/document_flows.py:400` `:saveas` 不展开 `~`

**修法**：`path = Path(text)` → `path = self.resolve_input_path(Path(text))`
（同文件 :101-115 已实现 `expanduser` + workspace 根解析，`:e` 走同一入口）。

**回归测试**（`tests/test_app_textual.py` 或该 flow 既有测试文件）：
- `test_saveas_expands_a_home_relative_path`（`tmp_path` 伪装 HOME/`Path.home`，`~` 路径落到家目录）
- `test_saveas_resolves_a_relative_path_against_the_workspace_root`（cwd 与 workspace 根不同，文件落在 workspace 根）
- 既有 `:saveas` 用例若钉了"按 cwd 解析"，按新语义改断言并在偏离段记录

## 3. M-6（MAJOR）`yate/yaterc.py:201-208` 抽取阶段异常未兜底

**修法**：把四处抽取调用包进 try（逐文件段 + 末尾 options 段），异常转 `config.errors`：

```python
        config.sources.append(path)
        try:
            _extract_extensions(namespace, config, path.parent)
            _extract_theme_dirs(namespace, config, path.parent)
            _extract_disabled_extensions(namespace, config)
        except Exception as exc:  # noqa: BLE001 - rc values are user data
            config.errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
    ...
    try:
        _extract_options(namespace, config)
    except Exception as exc:  # noqa: BLE001 - rc values are user data
        config.errors.append(f"{type(exc).__name__}: {exc}")
```

**回归测试**（`tests/test_yaterc_options.py`）：
`test_mixed_key_types_in_screen_saver_are_reported_not_raised`（`screen_saver = {1: True, "x": 1}` →
`load_yaterc` 返回 config、`config.errors` 非空、进程不抛）。

## 4. m-7（MINOR）`yate/keymaps/vim.py:388,674,1093,1348` 裸 `assert`

**修法**：逐处改为显式守卫，保持 `-O` 前后行为一致：
- :388 / :674：`if <条件> is None: return False`（dispatch 未消费语义）；
- :1093：`if self.last_find is None: return`；
- :1348：`if <条件> is None: return`。
不得引入新异常类型，不得改变正常路径。

**回归测试**：`tests/test_vim_keymap.py` 既有用例全绿（无新用例；行为等价，
用 `python -O -m pytest tests/test_vim_keymap.py -q --cov-fail-under=0` 抽查一遍）。

## 5. m-16（MINOR）`yate/session.py:211` 循环内重复 `resolve()`

**修法**：`target = old.resolve()` 提到 `for` 之前，循环里比较 `doc.resolved_path == target`。

**回归测试**：`tests/test_session.py` 既有用例全绿。

## 6. m-21（MINOR）`yate/app.py:175,293` 缺 `@override`

**修法**：给 `watch_theme` 与 `on_key` 补 `@override`（`typing.override` 已在本文件导入或按需补）。
先核对基类确有同名成员（Textual `App.watch_theme` / `App.on_key`），否则不加（预期存在）。

## 7. m-22（MINOR）`yate/keymaps/registry.py:9-11` 空行超量

**修法**：`from __future__ import annotations` 与下一导入组之间删掉一个空行（组间 1 行）。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_vim_keymap.py tests/test_keymap_set.py tests/test_session.py tests/test_yaterc_options.py tests/test_app_textual.py -q --cov-fail-under=0
.\.venv\Scripts\python.exe -O -m pytest tests/test_vim_keymap.py -q --cov-fail-under=0
```

## 风险与回滚

- `m-7` 把 assert 改成"静默 return"可能掩盖真实不变量破坏：守卫分支命中时必须保持与
  `-O` 下原行为一致（原本就是"断言失败 → 抛 AssertionError"，改动后为"直接返回未消费"）。
  若某处断言是**必须成立**的不变量，改用 `raise RuntimeError(...)` 而不是 return，并在偏离段说明。
- `M-5` 改路径语义影响 `:saveas` 相对路径基准，需一次性核对既有用例与手册措辞。
- 回滚：按条 `git revert`。
