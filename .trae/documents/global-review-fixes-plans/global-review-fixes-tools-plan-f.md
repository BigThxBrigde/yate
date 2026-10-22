# plan-f：`tools/` 工具链修复

- 波次：wave-4（依赖前三波验收通过）
- 覆盖：W-14 / W-15 / W-16 / W-17 / W-18 / S-15 / S-16
- 独占文件清单：
  - `tools/pack/wiki.py`
  - `tools/lint_lua.py`
  - `tools/yxp/cli.py`
  - `tools/smoke_test/report.py`
  - `tools/smoke_test/scenarios/regression.py`
  - `tools/release/cli.py`
  - `tools/changelog/translations.py`
  - `tools/changelog/cli.py`
  - `tests/test_pack_wiki.py`
  - `tests/test_lua_lint.py`
  - `tests/test_tools_yxp.py`
  - `tests/test_smoke_tool.py`
  - `tests/test_release_tool.py`
  - `tests/test_changelog_tool.py`
- 只改以上文件，不得动其它任何文件。

## 一、输入事实（已核对源码）

- W-14：[wiki.py](../../tools/pack/wiki.py) 第 1534-1539 行只记录
  `digests[page.zh_target]`；第 1615 行 `recorded = set(manifest)` 只含
  `*.zh.md`；第 1649 行按 zh 键过滤 manifest。
- W-15：[lint_lua.py](../../tools/lint_lua.py) 第 248 行 `read_text` 的通用换行
  把 CRLF 归一为 LF，第 173 行 `"\r" in source` 永不命中 CRLF。
- W-16：[yxp/cli.py](../../tools/yxp/cli.py) 第 261-266 行 `--force` 无条件
  `shutil.rmtree(target)`。
- W-17：[report.py](../../tools/smoke_test/report.py) 第 223 行
  `passed = sum(1 for r in group if r.fail_count == 0)` 未看 `r.error`。
- W-18：[regression.py](../../tools/smoke_test/scenarios/regression.py) 第 24 行
  `_SETTLE_S = 0.3`，第 262/266/279/284/299 行依赖真实睡眠。
- S-15：[release/cli.py](../../tools/release/cli.py) 第 278-284 行快照用
  `read_text`，第 361-368 行回滚用 `write_text`。
- S-16：[translations.py](../../tools/changelog/translations.py) 第 44 行
  `json.loads` 无兜底；[changelog/cli.py](../../tools/changelog/cli.py) 第 147 行
  与第 278 行直接调用。

## 二、分步修改

### 步骤 F1：W-14 孤儿英文页清理

**文件**：`tools/pack/wiki.py`

在 `run()` 第 1615 行前加一个局部推导（不改 manifest schema）：

```python
    recorded = set(manifest) | {
        key[: -len(_ZH_SUFFIX)] + _EN_SUFFIX
        for key in manifest
        if key.endswith(_ZH_SUFFIX)
    }
```

删除原来单独的 `recorded = set(manifest)` 行。manifest 的键仍只写 zh 目标，
`prune_orphan_pages` 的 `recorded` 白名单因此同时包含对应 en 目标。

### 步骤 F2：W-15 CRLF 检测

**文件**：`tools/lint_lua.py`

`check_paths` 第 247-251 行改为：

```python
            try:
                with path.open(encoding="utf-8", newline="") as handle:
                    source = handle.read()
            except OSError as exc:
                issues.append(Issue(path, 1, "read", str(exc)))
                continue
```

### 步骤 F3：W-16 `--force` 只删脚手架

**文件**：`tools/yxp/cli.py`

`create_scaffold` 第 261-266 行改为：

```python
    if target.exists():
        if not force:
            raise yxp.YxpError(
                f"{target} already exists (use --force to replace)"
            )
        if not target.is_dir():
            raise yxp.YxpError(
                f"refusing to remove {target}: not a directory"
            )
        try:
            metadata = read_source_metadata(target)
        except yxp.YxpError as exc:
            raise yxp.YxpError(
                f"refusing to remove {target}: not an extension scaffold "
                f"({exc})"
            ) from exc
        if metadata.get("name") != name:
            raise yxp.YxpError(
                f"refusing to remove {target}: scaffold metadata names "
                f"{metadata.get('name')!r}, not {name!r}"
            )
        shutil.rmtree(target)
```

同步更新 docstring：“With *force* an existing **scaffold** directory of the same
name is removed”已属准确描述，可保留。

### 步骤 F4：W-17 崩溃场景不计通过

**文件**：`tools/smoke_test/report.py`

第 223 行改为：

```python
        passed = sum(
            1 for r in group if r.fail_count == 0 and r.error is None
        )
```

### 步骤 F5：W-18 去掉固定睡眠

**文件**：`tools/smoke_test/scenarios/regression.py`

1. 删除 `_SETTLE_S` 常量与文件头对应注释，改为一句：
   “Background work is awaited through ``wait_until``; no wall-clock sleep is
   used as a synchronization primitive.”
2. `_regress_completion_popup_keys`（第 251-311 行）中：
   - 第 262 行 `await pilot.pause(_SETTLE_S)` 删除；
   - 第 266 行 `await pilot.pause(_SETTLE_S)` 删除；
   - 第 279 行删除，改为在 `type_text(pilot, "n")` 后用
     `await wait_until(pilot, lambda: popup.prefix == "prin")`（已有第 282 行）；
   - 第 284 行删除；
   - 第 299 行删除。
   - 在 `await type_text(pilot, "pri")`（第 261 行）后加
     `await wait_until(pilot, lambda: popup.is_open)`，确保自动防抖查询已落地；
     第 295 行第二次 `type_text(pilot, "pri")` 后同样加该等待。
3. 其余使用处（第 262/266/279/284/299 行）保持按键—等待—断言顺序，不新增
   真实睡眠。

### 步骤 F6：S-15 字节级快照与回滚

**文件**：`tools/release/cli.py`

```python
def _snapshot_texts(repo: Path, files: Sequence[str]) -> dict[str, bytes | None]:
    snapshots: dict[str, bytes | None] = {}
    for rel in files:
        path = repo / rel
        snapshots[rel] = path.read_bytes() if path.exists() else None
    return snapshots
```

`_abort_with_rollback` 的 `snapshots` 参数类型改为 `dict[str, bytes | None]`，
回滚写回改为 `path.write_bytes(data)`（变量名由 `text` 改 `data`）。

### 步骤 F7：S-16 覆盖文件 JSON 语法错误

**文件**：`tools/changelog/translations.py`

新增异常：

```python
class OverrideFileError(Exception):
    """The hand-maintained override file could not be parsed."""
```

`load_overrides` 的 `loaded: object = json.loads(text)` 改为：

```python
    try:
        loaded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OverrideFileError(f"{path}: invalid JSON ({exc})") from exc
```

**文件**：`tools/changelog/cli.py`

两处调用（第 147 行、第 278 行）包起来：

```python
    try:
        overrides = translations.load_overrides(overrides_path)
    except translations.OverrideFileError as exc:
        print(f"error: {exc}")
        return 1
```

## 三、新增/修改测试

### `tests/test_pack_wiki.py`

1. 扩展既有 `test_prune_removes_only_pages_recorded_in_the_manifest`：
   第二次 `run()` 后追加
   `assert not (target / "orphan.en.md").exists()`。
2. `test_prune_keeps_a_user_written_english_page`
   - 准备：手写 `target / "manual-note.en.md"`（不在 manifest）。
   - 操作：`wiki.run(target, None, repo_root=repo)`
   - 断言：该文件仍存在。

### `tests/test_lua_lint.py`

3. `test_crlf_file_is_reported`
   - 准备：`path.write_bytes(b"local x = 1\r\n")`
   - 操作：`lint_lua.check_paths([path], set(), lambda source, name: None)`
   - 断言：规则集合包含 `"crlf"`。

### `tests/test_tools_yxp.py`

4. 修改既有 `test_create_force_replaces_existing_dir`：
   - 先 `main(["--create", "my_ext", "--dir", tmp])` 生成脚手架；
   - 再 `main(["--create", "my_ext", "--dir", tmp, "--force"])`；
   - 断言退出码 0 且 `manifest` 存在。
5. `test_create_force_refuses_a_non_scaffold_directory`
   - 准备：`(tmp / "my_ext").mkdir()` 并写 `precious.txt`。
   - 操作：`main(["--create", "my_ext", "--dir", tmp, "--force"])`
   - 断言：退出码 1；`precious.txt` 仍存在。
6. `test_create_force_refuses_a_scaffold_with_a_different_name`
   - 先生成 `other`，把目录改名为 `my_ext`；再 `--create my_ext --force`。
   - 断言：退出码 1，目录保留。

### `tests/test_smoke_tool.py`

7. `test_group_table_counts_an_errored_scenario_as_not_passed`
   - 准备：`ScenarioResult("boom", tags=("edit",), error="TimeoutError: x")`
   - 操作：`reporter.results([errored])`
   - 断言：输出含 `"0/1 scenarios"`，不含 `"1/1 scenarios"`。

### `tests/test_release_tool.py`

8. `test_snapshot_texts_preserves_bytes`
   - 准备：`path.write_bytes(b"a\r\nb\n")`
   - 断言：`cli._snapshot_texts(tmp_path, ["f"]) == {"f": b"a\r\nb\n"}`。

### `tests/test_changelog_tool.py`

9. `test_load_overrides_reports_invalid_json`
   - 准备：`path.write_text("{broken", encoding="utf-8")`
   - 断言：`pytest.raises(translations.OverrideFileError, match="invalid JSON")`。
10. `test_generate_returns_one_for_an_invalid_override_file`
    - 使用 `cli_repo` / `stub_gitdata` fixture，overrides 文件写入非法 JSON。
    - 断言：`cli.generate(cli_repo, overrides_path=bad_path) == 1`；
      `capsys` 的 out 含 `"error:"`。

### 冒烟（W-18 验证）

```powershell
.venv\Scripts\python.exe -m tools.smoke_test run --scenario regress_completion_popup_keys --jobs 1
```

## 四、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pack_wiki.py tests/test_lua_lint.py tests/test_tools_yxp.py tests/test_smoke_tool.py tests/test_release_tool.py tests/test_changelog_tool.py -q
.venv\Scripts\python.exe -m pyright tools/pack/wiki.py tools/lint_lua.py tools/yxp/cli.py tools/smoke_test/report.py tools/smoke_test/scenarios/regression.py tools/release/cli.py tools/changelog tests/test_pack_wiki.py tests/test_lua_lint.py tests/test_tools_yxp.py tests/test_smoke_tool.py tests/test_release_tool.py tests/test_changelog_tool.py
.venv\Scripts\python.exe -m tools.smoke_test run --scenario regress_completion_popup_keys --jobs 1
```

通过判定：三条命令退出码均为 0。

## 五、风险与回滚

- W-14 的 en 名推导依赖 `*.zh.md` 后缀约定；`Home*` / `_Sidebar*` 仍由
  `protected` 集合拦截。
- W-16 的行为收紧会让“裸目录 + --force”从成功变失败，属计划内的安全修复；
  既有测试同步改写。
- W-18 将固定睡眠替换为状态等待，若场景本身依赖防抖延迟，会出现超时而非
  flake；超时即说明需要改断言，不得退回睡眠。
- S-15 快照类型变化只影响 release 回滚路径，release 测试覆盖新建文件与既有
  文件两种回滚。
- 回滚：本子计划单独提交。
