# 子计划 b — S-05 `api.data` 符号链接写穿（wave-1）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-05。
> 只改「独占文件清单」列出的 3 个文件。

## 一、目标与非目标

- 目标：`yate/services/data_store.py` 在词法校验之外增加**真实路径**校验：
  任何经符号链接逃出 `~/.yate/data` 的名称，在 `read` / `write` / `remove` /
  `list` 路径上一律被拒绝；`write_text` / `remove` 在操作前二次复核，闭合
  `resolve()` 与真正写盘之间的窗口。
- 非目标：不改 `DataExtensionBridge` 的「失败返回 None/False/[]」契约、不改
  `api.data` 公共成员名、不改 Lua `yate.data` 面、不引入文件锁。

## 二、独占文件清单

1. `yate/services/data_store.py`
2. `tests/test_data_store.py`
3. `tests/test_extension_bridges.py`

## 三、具体改动（定位到文件:行号 / 签名）

### 3.1 `yate/services/data_store.py:46-73, 93-133`

- 新增模块私有函数：
  ```python
  def _assert_inside_data_root(target: Path, relative: str) -> None:
      """Reject *target* when its real path escapes the resolved data root."""
      real_root = data_root().resolve()
      if not target.resolve().is_relative_to(real_root):
          raise ValueError(
              f"data name resolves outside {real_root}: {relative!r}"
          )
  ```
  （`Path.resolve()` 在 3.12 默认 `strict=False`，父级符号链接会被展开；
  `real_root` 与 `target` 同口径，HOME 本身是符号链接的合法环境仍放行。）
- `resolve()` 在现有 `if not target.is_relative_to(root)` 之后追加
  `_assert_inside_data_root(target, relative)`；更新 docstring：说明第二道
  词法校验之外还有真实路径校验，符号链接（含中间目录）会被拒绝。
- `write_text()` 在 `path.parent.mkdir(parents=True, exist_ok=True)` 之后、
  `tempfile.mkstemp(...)` 之前再次调用
  `_assert_inside_data_root(path, relative)`（闭合 mkdir 后的窗口）。
- `remove()` 在 `path.unlink()` 之前再次调用同样校验。
- `read_text()` / `names()` 不新增调用：`resolve()` 已覆盖；保留其既有
  `ValueError` 向上传播语义（bridge 捕获后返回 `None` / `[]`）。
- 模块 docstring 第 3-7 行补一句：真实路径校验同样属于本 L0 模块的单源规则。
- 全部注释 / docstring 英文 ASCII；不改日志惰性 `%` 格式。

### 3.2 `tests/test_data_store.py`

先读现有 `:1-136`，复用 `isolated_home` autouse 夹具与「symlink 不可用则
`pytest.skip`」先例（`tests/test_yxp.py:429-554`）。新增共享夹具或辅助函数：
```python
def _link_to_external(root: Path, outside: Path) -> Path: ...
```
创建 `data_store.data_root()`、外部目录 `tmp_path / "outside"`，在数据根下建
`link -> outside` 符号链接；`except (OSError, NotImplementedError): pytest.skip(...)`。

新增用例（名称即契约）：

- `test_write_rejects_symlinked_parent_outside_data_root`：
  arrange 如上 + `outside / "escape.json"` 不存在；act
  `with pytest.raises(ValueError, match="resolves outside"):`
  `data_store.write_text("link/escape.json", "x")`；assert 外部文件不存在、
  数据根下无临时 `.tmp` 残留。
- `test_remove_rejects_symlinked_parent_outside_data_root`：
  arrange `outside / "victim.json"` 写好内容；act
  `with pytest.raises(ValueError, match="resolves outside"):`
  `data_store.remove("link/victim.json")`；assert victim 仍存在且内容不变。
- `test_read_rejects_symlinked_parent_outside_data_root`：
  `with pytest.raises(ValueError): data_store.read_text("link/victim.json")`。
- `test_names_rejects_symlinked_directory_outside_data_root`：
  `with pytest.raises(ValueError): data_store.names("link")`。
- `test_nested_relative_name_still_writes_under_root`：
  无符号链接的 `games/deep/save.json` 写入 → 读取一致、`resolve()` 仍在根内
  （既有 `test_resolved_paths_stay_below_the_data_root` 是只读锚点，本例补写路径）。

既有 10 个用例（含 `:107 test_rejects_absolute_and_traversal_names`、
`:123`、`:131`）一条不改，作为回归基线。

### 3.3 `tests/test_extension_bridges.py`

- 在既有 `:558 test_data_bridge_roundtrip_under_the_isolated_home(api)` 之后新增
  `test_data_bridge_rejects_symlink_escape(api, tmp_path, caplog)`：
  - arrange：用同一 symlink 辅助模式在 `data_store.data_root()` 下建 `link -> outside`；
  - act / assert：`api.data.write("link/x.json", "{}") is False`、
    `api.data.remove("link/x.json") is False`、`api.data.read("link/x.json") is None`、
    `api.data.list("link") == []`；外部文件未被创建 / 删除；`caplog` 中
    `api.data.write(...)` 告警出现（如需 `yate` logger 传播，monkeypatch
    `logging.getLogger("yate").propagate = True`，见项目记忆）。
  - 与 `tests/test_data_store.py` 的 skip 形态一致（符号链接不可用时 skip）。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/services/data_store.py tests/test_data_store.py tests/test_extension_bridges.py
.venv\Scripts\python.exe -m pytest tests/test_data_store.py tests/test_extension_bridges.py -q
.venv\Scripts\python.exe -m pytest tests/test_data_store.py tests/test_extension_bridges.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

通过判定：三条退出码全 0；新增 6 个用例全通过（符号链接不支持的平台 skip
需在报告中列明）；既有 `test_data_store.py` 10 例全绿。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `Path.resolve()` 对不存在路径在 Windows 引发异常 | 3.12 `strict=False` 为默认；新增用例覆盖不存在目标 | `git checkout -- <3 个独占文件>` |
| 二次复核改变 `write_text` 的 OSError 回退路径 | 复核放在 `mkstemp` 之前，不触碰 `try/finally` | 同上 |
| `api.data` 桥接把 `ValueError` 记成 warning 后吞掉 | 这是既有契约；新增用例同时断言返回值与外部无副作用 | 同上 |

## 六、报告格式

改动清单、实跑命令与退出码、skip 用例清单、未解决项与原因。
