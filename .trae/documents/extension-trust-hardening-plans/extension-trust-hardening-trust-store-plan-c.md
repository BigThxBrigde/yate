# 子计划 c — S-04 trust store 读侧加固与显式告警（wave-1）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-04。
> 只改 2 个文件。内容指纹 / Windows ACL / 二次确认 UI 按主计划 §二 F 登记另案，
> 本子计划不得实现。

## 一、目标与非目标

- 目标：消除 `chmod` 失败被 `contextlib.suppress(OSError)` 静默吞掉；读侧拒绝
  符号链接形式的 trust store；模块 docstring 如实说明「永久路径授权」模型。
- 非目标：不改 `~/.yate/trusted_workspaces` 一行一路径格式（向后兼容）、不改
  `is_trusted()` 的 resolved 精确匹配语义、不动 `yaterc.py` /
  `theme/files.py` / `loader.py` 三处门控调用点、不新增命令 / UI。

## 二、独占文件清单

1. `yate/services/trust.py`
2. `tests/test_trust.py`

## 三、具体改动

### 3.1 `yate/services/trust.py:1-20, 22-36, 46-66, 69-119`

- 删除 `import contextlib`（改后不再使用）。
- 新增模块级常量（带 `#:` 说明）：
  ```python
  #: Whether POSIX permission bits are meaningful here; tests override this
  #: seam so the warning path is exercised on Windows too.
  _POSIX: bool = os.name == "posix"
  ```
- 新增私有函数：
  ```python
  def _chmod_quietly(target: Path, mode: int) -> None:
      """Best-effort owner-only permissions; a failure must be visible."""
      try:
          os.chmod(target, mode)
      except OSError as exc:
          log.warning(
              "could not set owner-only permissions on %s: %s", target, exc
          )
  ```
- `trust_workspace()` 的 `:104-112` 改为：`store.parent.mkdir(...)` 保持；
  `if _POSIX: _chmod_quietly(store.parent, 0o700)`；写文件；
  `if _POSIX: _chmod_quietly(store, 0o600)`。原有注释保留并补一句说明失败会
  告警而不是静默。
- `load_trusted_workspaces()` 在读文件之前加读侧守卫：
  ```python
      if store.is_symlink():
          log.warning("refusing to read symlinked trust store %s", store)
          return set()
  ```
  仅拒绝 store **文件本身**为符号链接；父目录为链接（用户家目录常见布局）不受影响。
- 模块 docstring 补三段事实：① trust 是按 resolved 绝对路径的**永久授权**，
  不绑定目录内容，替换受信任目录里的代码后仍会自动执行，撤销需手工从
  store 删除该行；② POSIX 上目录 / 文件权限为 best-effort，失败显式告警，
  Windows 不使用 ACL（另案）；③ store 自身为符号链接时读侧返回空集。
- 全部注释 / docstring 英文 ASCII；日志保留惰性 `%` 格式。

### 3.2 `tests/test_trust.py`

先读 `:1-106` 现有形态；新增 `import logging`（如未导入）与
`from yate.services import trust`（用于 monkeypatch 模块级常量）。

- 新增 `test_chmod_failures_are_reported_and_trust_is_still_recorded(
  tmp_path, monkeypatch, caplog)`：
  - arrange：`monkeypatch.setattr(trust, "_POSIX", True)`；
    `monkeypatch.setattr(trust.os, "chmod", _raise)`（`_raise` 抛 `OSError("denied")`）；
    `monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)`；
    store = `tmp_path / "nested" / ".yate" / "trusted_workspaces"`，root 先 mkdir。
  - act：`with caplog.at_level(logging.WARNING, logger="yate"):`
    `assert trust.trust_workspace(root, store) is True`。
  - assert：store 含一行 resolved root；`is_trusted(root, store)` 为 True；
    `caplog.text` 中 `"could not set owner-only permissions"` 出现 **2 次**
    （父目录 + store 文件各一次）。本用例跨平台可跑（不依赖真实 POSIX 位）。
- 新增 `test_chmod_succeeds_silently(tmp_path, monkeypatch, caplog)`：
  `_POSIX=True` 且 `os.chmod` 为记录替身（不抛错）→ 调用两次、无 warning。
- 新增 `test_symlinked_trust_store_is_refused(tmp_path, monkeypatch, caplog)`：
  - arrange：`real = tmp_path / "trusted_workspaces"`，写入一个已 resolve 的
    root 路径；`link = tmp_path / "linked_store"`，`link.symlink_to(real)`，
    `except (OSError, NotImplementedError): pytest.skip(...)`；
  - act / assert：`trust.load_trusted_workspaces(link) == set()`、
    `trust.is_trusted(root, link) is False`、`caplog.text` 含
    `"refusing to read symlinked trust store"`；真实 store 直接读仍返回该 root。
- 既有 7 个用例全部不动（含 `:41 test_trust_refuses_a_symlinked_root` 与
  `:92 test_trust_workspace_creates_owner_only_directory`，后者仅 POSIX 生效）。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/services/trust.py tests/test_trust.py
.venv\Scripts\python.exe -m pytest tests/test_trust.py tests/test_extensions.py tests/test_theme_trust.py tests/test_config.py tests/test_extension_flows.py -q
.venv\Scripts\python.exe -m pytest tests/test_trust.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

通过判定：三条退出码全 0；新增 3 例通过（符号链接不支持时 skip 并在报告列明）；
三处门控调用点相关既有测试无回归。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| monkeypatch 全局 `os.chmod` 影响同进程其它测试 | 用 `monkeypatch`（自动还原），替身只抛 / 只记录 | `git checkout -- yate/services/trust.py tests/test_trust.py` |
| `_POSIX` 常量被视为新抽象 | 它只是既有 `os.name == "posix"` 分支的可测缝，不改变生产判定 | 还原为直接 `os.name` 判断（但测试需改） |
| 读侧拒绝符号链接 store 破坏用户手工软链 | 文档（plan_g）明示；仅拒 store 文件本身 | 同上 |

## 六、报告格式

改动清单、实跑命令与退出码、skip / caplog 断言结果、未解决项与原因。
