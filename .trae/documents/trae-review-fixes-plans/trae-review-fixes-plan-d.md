# plan-d（W-D）：services / syntax / extensions — 10 条

- 波次：W-D（依赖 W-A；与 W-B / W-C 并行）
- 独占文件（**只改这些**）：`yate/services/fonts.py`、`yate/services/yxp.py`、`yate/services/shell.py`、
  `yate/logs.py`、`yate/editor_syntax/engine.py`、`yate/editor_syntax/regex_backend.py`、
  `yate/editor_syntax/langdefs.py`、`yate/services/extensions/bridges.py`、
  `yate/services/extensions/loader.py`、`yate/services/extensions/api.py`、
  `yate/extensions/example_ext.py.example`；
  测试：`tests/test_fonts.py`、`tests/test_yxp.py`、`tests/test_tools_yxp.py`、`tests/test_shell.py`、
  `tests/test_tracing.py`、`tests/test_syntax_engine.py`、`tests/test_extension_api.py`、
  `tests/test_extension_bridges.py`、`tests/test_extension_examples.py`、`tests/test_extensions.py`
- 输入：评审记录 §五 M-7/M-8、§六 m-3/m-4/m-6/m-8/m-14/m-15/m-17/m-18
- 边界约束：`services/extensions/` 内部可改，但**门面 `__init__.py` 的 14 个公共名冻结**
  （R14 守卫 `test_extension_facade_exports_the_frozen_plugin_names` 必须绿）。

## 1. M-7（MAJOR）`yate/services/fonts.py:387-388` 非 dict `profiles`

**修法**：

```python
    profiles_raw = data.setdefault("profiles", {})
    if not isinstance(profiles_raw, dict):
        return False, "unsupported settings.json: profiles is not an object"
    profiles = cast(dict[str, Any], profiles_raw)
    defaults_raw = profiles.setdefault("defaults", {})
    if not isinstance(defaults_raw, dict):
        return False, "unsupported settings.json: profiles.defaults is not an object"
    defaults = cast(dict[str, Any], defaults_raw)
```

**回归测试**（`tests/test_fonts.py`）：
`test_legacy_profiles_list_is_reported_not_raised`（写 `{"profiles": [{"name": "x"}]}` → 返回 `(False, msg)`，不抛）。

## 2. M-8（MAJOR）`yate/services/yxp.py:304-314,416-432` 无成员大小上限

**修法**（新增模块常量 + 有界读取助手）：

```python
#: Hard caps for one .yxp payload (extensions are small scripts).
MAX_MEMBER_BYTES: Final[int] = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES: Final[int] = 128 * 1024 * 1024
```

- `_read_member(zf, rel) -> bytes`：用 `zf.open(rel)` 分块读，累计超过 `MAX_MEMBER_BYTES` 即抛
  `YxpError(f"{source}: member {rel!r} exceeds the size cap")`（不信任 `ZipInfo.file_size`，
  防压缩包谎报）；
- `_verify_digests` 与 `_member_bytes` 统一走该助手；
- `read_package` 校验 payload：`sum(zi.file_size for zi in zf.infolist() if zi.filename in payload)`
  超 `MAX_PAYLOAD_BYTES` 直接拒绝（快速失败，省去解压）。

**回归测试**（`tests/test_yxp.py`）：
- `test_oversized_member_is_rejected_before_extraction`（构造单成员 > cap 的 zip，断言 `YxpError` 且无文件落盘）
- `test_declared_small_but_actually_large_member_is_rejected`（`ZipInfo.file_size` 被篡改为小值，
  流式读取时按实际字节拒绝）

## 3. m-3（MINOR）`yate/extensions/example_ext.py.example:76,89` 漏 `mark_content_changed`

**修法**：两处在 `buf.lines[row] = ...` 之后补 `buf.mark_content_changed()`。
**回归测试**（`tests/test_extension_examples.py`）：`test_upper_command_marks_the_buffer_changed`
（调用 `:upper` 后 `buffer.content_version` 递增、`document.modified` 为真）。

## 4. m-4（MINOR）`yate/editor_syntax/engine.py:83` `# type: ignore`

**修法**：`return cast(SyntaxBackend, ts_backend)`，补 `from typing import cast`（与 `Protocol` 同组），
删掉 ignore 注释；保留原有解释性注释。

## 5. m-6（MINOR）`yate/editor_syntax/regex_backend.py:384-388` 引号内 `#` 被当注释

**修法**：新增 `_comment_start(line: str, marker: str) -> int`：逐字符扫描，维护单/双引号状态
（含 `\` 转义），只在引号外命中 `marker` 时返回下标；`_tokenize_config_line` 改用它。

**回归测试**（`tests/test_syntax_engine.py`）：
`test_config_hash_inside_a_string_is_not_a_comment`（`key = "a#b" # real` → `"a#b"` 仍是 string，
`# real` 是 comment）。

## 6. m-8（MINOR）`yate/services/extensions/bridges.py:159-170` 语言注册不可回滚

**修法**（补齐 A13 的 undo 面）：
1. `langdefs.py` 新增 `drop_language(*keys: str) -> None`（仅删注册表条目，内置表用 `_BUILTIN_KEYS`
   快照保护，删内置键即 `ValueError`——与 `unregister_character` 同款语义）；
2. `engine.py` 新增 `unprefer_regex(*filetypes: str) -> None`（`_REGEX_PINNED.discard`）；
3. `HighlightExtensionBridge` 构造改为 `__init__(self, record_undo: RollbackHook)`，
   `register` 记录 undo：恢复先前 spec（有则 `register_language(prev, *keys)`，无则 `drop_language(*keys)`）
   - `unprefer_regex(*keys)`；
4. `api.py:128` 构造处传 `self._record_undo`；
5. `SpriteExtensionBridge.register` 与 `LspExtensionBridge.register_server` 用现有
   `unregister_character` / `LspManager.unregister_server`（不存在则在 manager 内补最小实现）
   记录 undo；`SyntaxExtensionBridge.register_tree_sitter` 若无反注册 API，按"最小可用"补
   `ts_backend.drop_grammar(name)` 并在 docstring 说明。

**回归测试**（`tests/test_extension_bridges.py` / `tests/test_extension_api.py`）：
- `test_failed_setup_rolls_back_a_registered_language`（扩展 `setup` 内 `register` 后 `raise` →
  `available_filetypes()` 不含该键，内置高亮未被覆盖）
- `test_failed_setup_rolls_back_a_registered_sprite`（同上模式的 sprite）
- 门面冻结用例（`tests/test_architecture.py` 36 passed）保持绿

## 7. m-14（MINOR）`yate/services/yxp.py:476-491` 备份失败仍删除

**修法**：读取失败时 `continue`（跳过该文件的删除），不再"记录失败仍 unlink"：

```python
            try:
                previous[rel] = target.read_bytes()
            except OSError:
                log.warning("could not read stale file %s; keeping it", target)
                continue
```

**回归测试**（`tests/test_yxp.py`）：`test_stale_file_whose_backup_fails_is_kept`（`monkeypatch`
让 `read_bytes` 抛 `OSError` → 文件仍在、`removed` 不含该文件）。

## 8. m-15（MINOR）`yate/logs.py:347-361` 头部写失败泄漏句柄

**修法**：`handle: IO[str] | None = None` 提到 `try` 之前；`except (OSError, ValueError)` 分支里
`if handle is not None: handle.close()`（再 `faulthandler.enable(file=sys.stderr)` 兜底）。

**回归测试**（`tests/test_tracing.py`）：`test_header_failure_closes_the_handle`（`monkeypatch`
让 `_write_header` 抛 `OSError`，断言传入的 handle 已 `closed`）。

## 9. m-17（MINOR，性能）`yate/services/extensions/loader.py:104-109` 去重 O(n²)

**前置测量**（`overview.md` §四）：50 个已加载项下 `load_file` 去重循环计时；< 30% 降幅则登记不修。

**修法**：`LoadedExtension` dataclass 增加 `resolved: Path` 字段（加载时填一次）；
`sources` 段改为集合查询（`self._resolved: set[Path]`，加载时 add），去重循环删除。

**回归测试**（`tests/test_extensions.py`）：`test_same_script_loaded_through_two_sources_is_loaded_once`
（既有语义）+ `test_duplicate_detection_does_not_resolve_repeatedly`（计数 `Path.resolve`）。

## 10. m-18（MINOR）`yate/services/shell.py:51-57` 静默吞异常

**修法**：`except OSError:` 的 `pass` 改为
`log.warning("could not kill the timed-out shell (pid %d)", proc.pid, exc_info=True)`。

**回归测试**（`tests/test_shell.py`）：`test_kill_failure_is_logged`（`monkeypatch` 让 `kill` 抛
`OSError`，`caplog` 断言一条 WARNING）。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.\.venv\Scripts\python.exe -m pytest tests/test_fonts.py tests/test_yxp.py tests/test_tools_yxp.py tests/test_shell.py tests/test_tracing.py tests/test_syntax_engine.py tests/test_extension_api.py tests/test_extension_bridges.py tests/test_extension_examples.py tests/test_extensions.py tests/test_architecture.py -q --cov-fail-under=0
```

## 风险与回滚

- m-8 触碰扩展注册面：必须保证 `services/extensions/__init__.py` 的 14 个公共名与签名不变，
  失败回滚用例必须演示"setup 抛错后注册表复原"。
- M-8 的大小上限若与真实打包产物冲突（`--install-extension` 装自建大包），先查 `tests/`
  夹具与 `docs` 的示例包体量，必要时把上限写入 `yate/docs/extensions.*.md`。
- 回滚：按条 `git revert`；m-8 的回滚需连同 `api.py` 构造签名一起回。
