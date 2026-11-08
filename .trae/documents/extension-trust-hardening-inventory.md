以下为只读调研结果。路径均相对 worktree 根 `the worktree root`；只列事实，未修改任何文件。另有 issue 素材文件 `.trae/documents/extension-trust-hardening-issue.md:1-27`（`:20-27` 为 S-01…S-08 摘要表），仅作来源关联。

---

## S-01 Lua 运行时与 Lua 装载路径

**源码事实 / 签名 / 常量**

- `yate/services/extensions/lua/runtime.py:1-29` 模块注释：`:3-9` "single place in yate that touches the `lupa` package"、动态 `importlib.import_module`；`:11-24` "Shape of the bridge"（`:14-19` `create_runtime` 每扩展一个 runtime、`api` 全局、`assert(load(source, chunkname))`、`package.preload["yate"]`）；`:26-28` `api` 参数刻意标注 `object`（"opaque handoff"）。
- 常量：`runtime.py:40 _LIBRARY_MODULE: str = "yate"`；`:45 _MODULE_CHUNK_PREFIX: str = "lib."`；`:49 _MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")`；`:53 _CHUNK_SOURCE_GLOBAL: str = "_YATE_CHUNK_SOURCE"`；`:58 _LIBRARY_CHUNK_NAME: str = "=yate.api"`；`:59 _EXTENSION_CHUNK_NAME: str = "=extension"`。`:42-44`、`:55-57` 注释说明 chunkname 被插入 Lua 字符串字面量、必须 quote-free。
- `_compile_chunk(runtime: Any, source: str, chunkname: str) -> Any`：`runtime.py:62-79`；拼接点 `:77` ``runtime.eval(f'assert(load({_CHUNK_SOURCE_GLOBAL}, "{chunkname}"))')``；`:79` 清除全局。
- `create_runtime(api: object, library_source: str, modules: Mapping[str, str] | None = None) -> Any`：`runtime.py:82-130`；`:111` `importlib.import_module("lupa")`、`:112` `lupa.lua54.LuaRuntime(unpack_returned_tuples=True)`、`:114` `globals_["api"] = api`、`:120-122` 编译库并 `require("yate")`、`:125-129` 共享模块循环（`:126 _MODULE_NAME_RE.match(name)`、`raise ValueError`；`:128 chunkname = f"={_MODULE_CHUNK_PREFIX}{name}"`；`:129 preload_table[name] = _compile_chunk(...)`）、`:102-103` 注释"no `package.path` entry and no Lua-side file I/O"、`:105-109` 固定 Lua 5.4 的 GC 说明。
- `run_extension(runtime: Any, source: str) -> Callable[[object], None] | None`：`runtime.py:133-183`；`:158` 清空 setup/teardown、`:159` `_compile_chunk(runtime, source, _EXTENSION_CHUNK_NAME)`。
- Lua 装载路径 `yate/services/extensions/loader.py:23-29` 导入（`:23-27` `is_lua_available` / `lua_api_library_source` / `lua_module_sources`、`:28` `create_runtime, run_extension`、`:29` `is_trusted`）；`:79-100 load_directory`、`:96` `glob("*.py")` + `glob("*.lua")`；`:102-174 load_file`、`:123-124` `.lua` 分支；`_load_lua(self, path: Path, resolved: Path) -> LoadedExtension` `:176-206`（`:183 is_lua_available()`、`:190 start_scope()`、`:191-193 create_runtime(self.api, lua_api_library_source(), lua_module_sources())`、`:194-196 run_extension(runtime, path.read_text(encoding="utf-8"))`、`:197-203` rollback/end_scope）；`load_startup_extensions(loader, config, *, ext_dirs=(), ext_files=()) -> list[str]` `:228-316`。

**现有测试文件与用例名**

- `tests/test_lua_engine.py:366 test_create_runtime_rejects_unsafe_module_names(name)`、`:352 test_lib_dir_is_not_discovered_as_an_extension()`；同文件其余 `:68-337` 为 Lua 库/game_engine 用例。
- `tests/test_lua_extensions.py:243 test_lua_extension_chunk_error_rolls_back_registrations`、`:289 test_load_directory_loads_mixed_py_and_lua`、`:305 test_load_directory_exclude_applies_to_lua_stem`、`:318 test_bundled_lua_library_compiles_into_runtime`、`:334 test_explicit_setup_hook_called_after_chunk`、`:455 test_lua_module_table_setup_and_teardown_full_cycle`、`:474 test_lua_module_table_without_setup_is_a_loud_error`、`:489 test_lua_module_table_setup_failure_rolls_back`、`:551 test_lua_package_import_paths`、`:588 test_lua_availability_probe_swallows_probe_errors`、`:621 test_lua_extension_without_lupa_records_install_hint`、`:641 test_bundled_lua_library_resources_ship_bundled`。
- `tests/test_extension_bridges.py:577 test_runtime_preloads_shared_lua_modules()`、`:558 test_data_bridge_roundtrip_under_the_isolated_home(api)`；`tests/lua_game_harness.py`（含相关符号的测试辅助）。
- `tests/test_lua_defs.py`、`tests/test_lua_lint.py`、`tests/test_lua_layout.py` 存在（文件名层）。

**文档 / 手册（中英）**

- `yate/docs/extensions.en.md:134-157` "### Trust model"：`:136-137` "Extensions are **trusted code**"、`:139-141` Python 完整权限、`:142-145` "**untrimmed Lua 5.4 runtime**"（`os`/`io`/`package`/`debug` 可用，`api.app` 经 lupa 包装可遍历）、`:146-147` "current version ships **no Lua sandbox and no API whitelist**"、`:149-157` 门控来源。
- `yate/docs/extensions.zh.md:120-137` 对应：`:120-121` "扩展是**受信任代码**"、`:125-127` "**未裁剪的 Lua 5.4 运行时**"、`:128-129` "当前版本**没有** Lua 沙箱，也没有 API 白名单"、`:131-137` 门控来源。
- 章节位置：`yate/docs/extensions.en.md:78-97` "### Workspace trust (:trust)"、`:897` "## 6. Lua extensions"、`:911` "### Shape of a Lua extension"、`:944` 共享 Lua 模块（zh 对应 `yate/docs/extensions.zh.md:70-86`、`:820`、`:834`、`:944`）；`yate/docs/extensions.en.md:785`、`:815` Lua lint 章节（zh `:718`、`:749`）。
- `yate/resources/manual.en.md:1250`（`api.shell(cmd)`）、`:1273`、`:1305-1311` Lua 支持段落（"same loader pipeline"、`require("yate")`、`_yate.lua`、`lua.example`，无沙箱措辞）、`:79-80`、`:872-877`、`:1018-1025`；`yate/resources/manual.zh.md:1126`、`:1147`、`:1173-1177`、`:77-78`、`:801-805`、`:930-936`。事实：两份 manual 中 `sandbox`/`沙箱`/`权限`/`白名单` 字面无命中。

---

## S-02 `.yxp` 校验、安装入口、CLI 与门面

**源码事实 / 签名 / 常量**

- `yate/services/yxp/manifest.py:1-28` 模块注释（`:3-13` zip + `manifest` + 可选 `checksum`，`:9-13` "without it the payload installs unverified"）；`:20-24` "Neither a symlinked member target nor ... is ever written through or deleted through"。
- 常量：`manifest.py:49 MANIFEST_NAME="manifest"`、`:51 CHECKSUM_NAME="checksum"`、`:55 RECORDS_DIRNAME="_manifests"`、`:57 RECORD_SUFFIX=".json"`、`:60 NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")`、`:62 _DIGEST_RE`、`:66 _DRIVE_RE`、`:69 MAX_MEMBER_BYTES=32*1024*1024`、`:70 MAX_PAYLOAD_BYTES=128*1024*1024`、`:73 _READ_CHUNK`。
- 类型：`:76 class YxpError(Exception)`、`:89 YxpManifest`、`:100 YxpPackage`（`:106 checksums: dict[str,str] | None`）、`:110 InstallReport`、`:121 UninstallReport`、`:130 InstalledPackage`、`:80 default_extensions_dir() -> Path`。
- `read_package(package_path: Path) -> YxpPackage` `manifest.py:145-200`；缺失分支 `:186-193`：`checksums: dict[str,str] | None = None`，仅 `if CHECKSUM_NAME in file_names` 时 `_parse_checksums(...)` + `_verify_digests(...)`；`:164-168` 允许"at most one" checksum 成员；`:158-163` manifest 必须恰好一个。
- 其余：`_load_json_member` `:203-215`、`_check_member_name` `:218-232`、`_manifest_str` `:235-246`、`_parse_manifest` `:249-289`、`_check_file_list` `:292-306`、`_parse_checksums` `:309-334`、`_read_member` `:337-363`、`_verify_digests` `:366-376`。
- `install_package(package_path: Path, base_dir: Path | None = None) -> InstallReport` `yate/services/yxp/install.py:53-127`；`:73-76` 经 facade 晚期绑定 `read_package`/`default_extensions_dir`；缺失 checksum 分支 `:77-82` `log.warning("installing extension package %s without a checksum member: contents cannot be verified")`；`:85-89` records 目录 symlink 拒绝；`:95-105` 未拥有文件碰撞；`:106-116` 抽取 + 回滚。
- 同文件：`_resolves_through_symlink` `:130-142`、`_extract_payload` `:145-185`、`_member_bytes` `:188-204`（写时复验）、`_rollback_files` `:207-233`、`_restore_stale_files` `:236-255`、`_remove_stale_files` `:258-297`、`_write_record` `:303-332`、`uninstall_package(name: str, base_dir: Path | None = None) -> UninstallReport` `:338-390`。
- 门面 `yate/services/yxp/__init__.py:1-33`（`:9-17` "Package-root re-export exception note"，点名 `yate/commands.py`、`yate/cli.py`、`tools/yxp/cli.py`；`:19-32` 冻结的 logger 名 `"yate.services.yxp"` 与补丁缝）；导入 `:44-74`；`__all__` `:76-103`（含 `_read_member`、`_restore_stale_files`、`_rollback_files`、`_write_record`、`os`）。
- `yate/cli.py:139` `pkg_group = parser.add_mutually_exclusive_group()`；`:140-148 --install-extension`（`dest="install_extensions"`, `action="append"`, `metavar="FILE"`）、`:149-157 --uninstall-extension`、` :158-162 --list-extensions`；`_manage_extensions(args: argparse.Namespace) -> int` `:299-322`（`:305 from yate.services import yxp`、`:310 yxp.format_install_report(yxp.install_package(Path(package_path)))`、`:316 yxp.format_uninstall_report(yxp.uninstall_package(name))`、`:321 yxp.format_package_list(yxp.list_packages())`）；`main(argv: Sequence[str] | None = None) -> int` `:325`；分发条件 `:386-388`；help 文本 `:64-65`。
- 编辑器内命令链：`yate/commands.py:568-608`：`_install_extension` `:570-580`（`:576 yxp.install_package(Path(args))`）、`_uninstall_extension` `:582-592`（`:588 yxp.uninstall_package(args)`）、`_list_extensions` `:594-601`、注册 `:603-608`。

**现有测试文件与用例名**

- `tests/test_yxp.py`（37.21 KB）：`:40 test_read_package_happy_path`、`:51 test_read_package_without_checksum_member`、`:56 ...missing_manifest`、`:65 ...duplicate_manifest`、`:76 ...duplicate_checksum`、`:86 ...bad_manifest_json`、`:102 ...manifest_not_object`、`:109 ...invalid_name`、`:119 ...version_defaults`、`:128 ...files_must_be_string_list`、`:138 ...files_mismatch_both_ways`、`:151 ...rejects_unsafe_names`、`:161 ...rejects_case_colliding_names`、`:181 ...checksum_keys_mismatch`、`:191 ...checksum_bad_digest_format`、`:199 ...tampered_payload`、`:212 ...not_a_zip`、`:219 ...unreadable_file`；`:227 test_install_extracts_payload_and_writes_record`、`:243 ...creates_nested_dirs`、`:251 test_install_without_checksum_installs_unverified`、`:257 ...refuses_unowned_collision`、`:267 ...refuses_tampered_package_without_side_effects`、`:284 ...upgrade_overwrites_and_removes_stale`、`:297 ...failure_rolls_back_partial_extraction`、`:334 test_failed_record_write_restores_previous_installation`、`:356 ...on_fresh_install_leaves_no_files`、`:399 ...leaves_no_temporary_record_files`、`:407 ...failed_record_replace_keeps_old_record_and_drops_temp`、`:429/:449/:466/:491/:515/:535/:554` symlink 系列、`:582 test_install_without_checksum_logs_warning`、`:601 test_install_with_checksum_no_warning`、`:684 test_rollback_skips_symlinked_member`、`:710 test_restore_stale_files_skips_symlinked_member`、`:739/:750/:756/:761/:772` uninstall 系列。
- `tests/test_yxp_subpackage.py:62 test_yxp_subpackage_no_relative_imports`、`:74 ...all_files_under_threshold`、`:81 test_yxp_facade_preserves_import_path`、`:94 ...facade_direct_import`、`:103 ...facade_all_names_resolve`、`:113 ...submodule_loggers_use_frozen_name`、`:124 ...subpackage_ascii_comments`。
- `tests/test_tools_yxp.py:28-368`（`:260 test_pack_writes_manifest_checksum_and_payload`、`:339 test_verify_accepts_valid_package`、`:349 test_verify_rejects_bad_package`、`:368 test_example_directory_packs_and_installs` 等 29 个）。
- `tests/test_cli.py:81 test_extension_dests_default_to_empty_lists`、`:151 test_extension_package_flags_parse`、`:164 test_extension_package_flags_are_mutually_exclusive`、`:171 test_main_installs_and_lists_extension_packages`、`:185 test_main_uninstall_extension_package`、`:197 test_main_install_extension_failure_exit_code`、`:648 test_cli_uninstall_reports_yxp_error_and_fails`。

**文档 / 手册（中英）**

- `yate/docs/extensions.en.md:1096-1169` "## 7. Extension packages (`.yxp`)"：`:1099-1110` 格式、`:1112-1114` CLI、`:1122-1124` ex 命令、`:1140-1147` `tools/yxp`、`:1169` `--verify`；`yate/docs/extensions.zh.md:999-1066` "## 7. 扩展包（`.yxp`）"：`:1001-1013`、`:1014-1016`、`:1023-1025`、`:1040-1047`、`:1066`。
- `yate/resources/manual.en.md:1014` "### 10.4 Extension paths (extensions)"；`yate/resources/manual.zh.md:926` "### 10.4 扩展路径（extensions）"。事实：两份 manual 中未出现 `.yxp` / `--install-extension` 字面（相关章节位于 docs 指南）。

---

## S-03 `shell=True` 与扩展 shell 暴露、`:!` 调用链

**源码事实 / 签名 / 通知面**

- `yate/services/shell.py:19-30 ShellResult`（字段 `command/returncode/output/cwd`、`:27-30 ok` 属性）；`:33-59 _kill_tree(proc: subprocess.Popen[str]) -> None`；`run_shell(command: str, cwd: Path | None = None, timeout: float = 60.0) -> ShellResult` `:62-117`；`:74-84 subprocess.Popen(command, shell=True, cwd=..., stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace", start_new_session=...)`；`:86` OSError 降级 `ShellResult(command, 1, ...)`；`:110-112` 超时返回码 124；`:120-122 shell_name() -> str`（`"cmd.exe"` / `"/bin/sh"`）。日志点 `:15 log`、`:57-58`、`:107-109`。
- `yate/services/extensions/api.py:49 from yate.services.shell import ShellResult`；`:147-148 ExtensionContext.run_shell: Callable[[str, bool], ShellResult | None]`；`:302-305 @property app -> ExtensionContext`；`shell(self, command: str) -> ShellResult | None` `:620-622`（`return self._ctx.run_shell(command, False)`）；相邻服务 `:616-630`。
- `yate/flows/shell_flows.py:22` 导入；`:29 class ShellFlows`；`run(self, command: str, show_output: bool = True) -> ShellResult | None` `:56-70`（`:67 run_shell(command, cwd=cwd)`）；`run_later(self, command: str) -> None` `:72-87`（`:84-87 _spawn(partial(self.run_async, command), group="shell", exclusive=False, exit_on_error=False)`）；`open_prompt(self) -> None` `:89-93`（`prompt.activate("shell", ..., on_submit=self.run_later)`）；`run_async(self, command: str, show_output: bool = True) -> ShellResult | None` `:95-107`（`:103 _message(f"running: {command}", "info")`、`:104 asyncio.to_thread(run_shell, command, cwd=cwd)`）；`_cwd() -> Path` `:109-116`；`_show_result` `:118-124`（覆盖层标题 `$ command`）。
- `:!` 分发：`yate/editor.py:737-744 run_command`（`:742 if text.startswith("!"):`、`:743 self.shell.run_later(text[1:])`）；`yate/actions.py:224 reg("shell_prompt", lambda ctx: editor.shell.open_prompt(), "Run shell command")`；`yate/keymaps/vsc.py:89,96`、`yate/keymaps/vim.py:211,220` 的 `:!` 描述；`yate/editor_components/statusbar.py:151` 提示图标；`yate/diagnostics.py:220 _kv(":! default", shell_name())`。

**现有测试文件与用例名**

- `tests/test_shell.py:44 test_run_shell_captures_stdout_and_success`、`:54 ...appends_stderr_on_its_own_line`、`:61 ...reports_a_non_zero_exit_code`、`:68 ...times_out_with_a_message`、`:76 ...timeout_returns_without_waiting_for_the_grandchild`、`:120 test_kill_tree_asks_taskkill_to_terminate_the_whole_tree`、`:143 ...bounds_the_drain_when_the_tree_survives_the_kill`、`:193 ...defaults_to_the_process_cwd`、`:198 test_shell_result_ok_tracks_the_return_code`、`:204 test_shell_name_matches_the_platform`、`:212-323` 配置 shell / 平台默认 / kill 失败共 20 个用例。
- `tests/test_shell_flows.py:103 test_run_gates_output_overlay_on_show_output_and_mounted`、`:128 test_run_later_rejects_empty_command`、`:140 test_run_async_rejects_empty_command`、`:151/:176` 字体安装用例；`tests/test_shells.py` 存在。
- 事实：`tests/test_extension_api.py` 中 `^def test_.*(shell|data)` 无命中（该 API 的 shell/data 无同名直接单元用例，data 侧由 `tests/test_extension_bridges.py:558` 覆盖）。

**文档 / 手册（中英）**

- `yate/resources/manual.en.md:816` 命令表 `:!cmd`、`:1233-1251` "## 14. Shell Integration"（`:1235-1236` 入口 `:!cmd`/F2、`:1237-1239` cwd、`:1240-1241` `cmd.exe` / `/bin/sh` "equivalent to `subprocess.run(shell=True)`"、`:1242-1245` 非阻塞、`:1248` 60 秒/124、`:1250` `api.shell(cmd)`）、`:1273` Services 表、`:285`、`:582`、`:1604`。
- `yate/resources/manual.zh.md:750`、`:1112-1126` "## 14. Shell 集成"（`:1114-1115` 入口、`:1118-1119` `shell=True`、`:1124` 超时、`:1126` `api.shell(命令)`）、`:1147`、`:261`、`:544`、`:1438`。
- 权限措辞：`yate/docs/extensions.en.md:134-147`、`:149-157`；`yate/docs/extensions.zh.md:120-137`。

---

## S-04 trust 全文与调用点

**`yate/services/trust.py` 全文（120 行）**

- `:1-20` 模块注释：`:3-10` 目标（"Opening a repository must never execute the repository's own code"）、`:7-8` 文件格式 `~/.yate/trusted_workspaces`，"one resolved absolute path per line, `#` comments allowed"、`:12-15` rc 声明路径 / `--ext` / `--ext-dir` / `~/.yate/extensions` 不受门控、`:17-19` 写侧拒绝 symlink 根。
- `:28-32` 导入与 `log = tracing.get_logger(__name__)`；`:36 TRUST_FILE: Path = yate_home() / "trusted_workspaces"`（"Read at call time, so tests can point it at a temporary file"）。
- `_has_symlink_component(path: Path) -> bool` `:39-43`（`probe.is_symlink() or any(parent.is_symlink() ...)`）。
- `load_trusted_workspaces(path: Path | None = None) -> set[Path]` `:46-66`：`:53` store 选择、`:58 read_text(encoding="utf-8", errors="replace")`（`:55-57` 注释：损坏字节不阻断启动）、`:59-60 except OSError: return set()`、`:62-65` strip / 跳过空行与 `#` / `Path(entry).resolve()`。
- `trust_workspace(root: Path, path: Path | None = None) -> bool` `:69-113`：`:88-94` symlink 根拒绝（S39）+ `log.warning`、`:95-97` 已信任则直接 True、`:98-107` `store.parent.mkdir(parents=True, mode=0o700, exist_ok=True)` 与 `if os.name == "posix": os.chmod(store.parent, 0o700)`（`contextlib.suppress(OSError)`）、`:108-109` `store.open("a", encoding="utf-8")` 追加 `f"{resolved}\n"`、`:110-112` `if os.name == "posix": os.chmod(store, 0o600)`、`:113 return True`。`:102-103` 注释说明 Windows 上 chmod 为 no-op。
- `is_trusted(root: Path, path: Path | None = None) -> bool` `:116-119`（`root.resolve() in load_trusted_workspaces(store)`）。

**调用点**

- `yate/yaterc.py:69 from yate.services.trust import is_trusted`；`:120-137`（`:122-127` 注释"project-level yaterc is code the project author wrote"、`:128 if is_trusted(project.parent):`、`:131-136` `log.debug` + `notes.append("yaterc: skipped untrusted ... (run :trust there to load it)")`）。
- `yate/editor_components/theme/files.py:24` 导入；`:62-69` 文档串；`:70-82`（`:71 cwd = Path.cwd().resolve()`、`:74 if is_trusted(cwd):`、`:77-80 errors.append("themes: skipped untrusted ...")`）。
- `yate/services/extensions/loader.py:29` 导入；`:292-311`（`:296 cwd = Path.cwd().resolve()`、`:304 if is_trusted(cwd):`、`:307-310` `messages.append(f"extensions: skipped untrusted {cwd_extensions} (run :trust to load them)")`）。
- `:trust` 命令链：`yate/commands.py:381-382 def _trust(args: str)` → `editor.extension_flows.trust_cwd_extensions()`、`:406-407 reg("trust", _trust, ...)`；`yate/flows/extension_flows.py:27` 导入 `trust_workspace`、`:67-102 trust_cwd_extensions(self) -> None`（`:78 cwd = Path.cwd()`、`:79 trust_workspace(cwd)`、`:83-88` "refused to trust ... it contains a symlink component" 消息、`:89-102` 立即 `load_directory` 并汇报）。

**现有测试文件与用例名**

- `tests/test_trust.py:18 test_missing_store_yields_no_trusted_workspaces`、`:23 test_trust_workspace_roundtrip`、`:34 ...is_idempotent`、`:41 test_trust_refuses_a_symlinked_root`、`:65 test_comments_and_blank_lines_are_skipped`、`:75 test_load_tolerates_invalid_utf8_bytes`、`:93 test_trust_workspace_creates_owner_only_directory`。
- `tests/test_theme_trust.py:49,66,80,92,106`（`test_workspace_themes_skipped_when_untrusted` / `...loaded_when_trusted` / `test_home_themes_always_loaded_without_trust` / `test_no_themes_directory_appends_no_note` / `test_default_theme_dirs_feed_load_theme_paths`）。
- `tests/test_extension_flows.py:27-34` symlink 探针替身 `_symlinked` / `_link_free`、`:81 test_trust_cwd_refuses_symlinked_cwd`、`:98 ...reports_missing_extensions_dir`、`:114 ...reports_each_failed_extension`。
- `tests/test_extensions.py:83 test_startup_skips_untrusted_cwd_extensions`、`:97 test_startup_loads_cwd_extensions_in_trusted_workspace`、`:130/:154/:172` symlink 解析三例（夹具 `:113-127 _symlinked_workspace`）。
- `tests/test_config.py:608 test_default_rc_paths_skips_untrusted_project_rc`、`:627 test_default_rc_paths_trusts_the_rc_owner_not_the_working_dir`；`tests/test_workspace_filter.py` 含 symlink 字面。

**文档 / 手册（中英）**

- `yate/docs/extensions.en.md:78-97` "### Workspace trust (:trust)"（`:82-84` 跳过消息、`:88-91` `:trust`、`:92-95` symlink 拒绝、`:96-97` 存储格式）、`:149-157` 门控；`yate/docs/extensions.zh.md:70-86`、`:131-137`。
- `yate/docs/themes.en.md:82-83,156-157,308-317` "## 7. Workspace themes and trust"；`yate/docs/themes.zh.md:77-78,142-143,288-296` "## 7. 工作区主题与信任"。
- `yate/resources/manual.en.md:986-987`（"trusted workspaces only -- run `:trust` and restart; see section 7 of the themes"）、`:993`；`yate/resources/manual.zh.md:900-901`、`:906`。

---

## S-05 `data_store` 全文与 `api.data`

**`yate/services/data_store.py` 全文（146 行）**

- `:1-12` 模块注释（`:3-7` `api.data` / `DataExtensionBridge` / games JSON、`:9-11` logs 与 crash 文件不走此模块）；`:24 log`；`:27 DATA_DIRNAME: str = "data"`。
- `data_root() -> Path` `:30-32`；`_has_drive_prefix(first: str) -> bool` `:35-43`。
- `resolve(relative: str) -> Path` `:46-73`：`:59-60` 空串、`:61-62` 反斜杠、`:63-66` `candidate.is_absolute() or candidate.drive or _has_drive_prefix(first)`、`:67-68 ".." in candidate.parts`、`:69-72 root = data_root(); target = root / candidate; if not target.is_relative_to(root): raise ValueError(...)`。
- `read_text(relative: str) -> str | None` `:76-90`（`:86-87 FileNotFoundError → None`、`:88-90 (OSError, UnicodeDecodeError) → log.warning + None`）。
- `write_text(relative: str, text: str) -> None` `:93-120`（`:106 path.parent.mkdir(parents=True, exist_ok=True)`、`:107-109 tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`、`:112-113` 写、`:115 temp.replace(path)`、`:116-118` OSError 回退 `path.write_text(...)`、`:119-120 temp.unlink(missing_ok=True)`）。
- `remove(relative: str) -> bool` `:123-133`；`names(relative_dir: str) -> list[str]` `:136-145`（`:140 sorted(... if entry.is_file())`、`:141-145` 缺失/非目录/OSError 处理）。实际公开名为 `resolve` / `write_text` / `remove` / `read_text` / `names`。

**api.data 暴露方式**

- `yate/services/extensions/api.py:33-47` 导入（`:38 DataExtensionBridge`）；`:193 self._data = DataExtensionBridge()`；`@property def data(self) -> DataExtensionBridge` `:377-380`（docstring "Read/write small documents under `~/.yate/data` (`api.data`）"）。
- `yate/services/extensions/bridges.py:461-502 class DataExtensionBridge`：`read` `:473-479` → `data_store.read_text(name)`、`write` `:481-487` → `write_text`、`remove` `:490-496` → `remove`、`list` `:498-502` → `names`；均 `try/except (ValueError, OSError[, TypeError])` 后告警。
- Lua 侧对应 `yate/extensions/_yate.lua` 的 `yate.data.read/write`（文档 `yate/docs/extensions.zh.md:788`、en `:864` 附近）。

**现有测试文件与用例名（含 symlink 夹具先例）**

- `tests/test_data_store.py:1-136` 全 10 个用例：`:22 test_has_drive_prefix_is_platform_independent`、`:35 test_read_missing_file_returns_none`、`:40 test_write_then_read_roundtrip_creates_parents`、`:49 test_write_is_atomic_and_leaves_no_temp_file`、`:59 test_write_falls_back_to_a_direct_write_when_rename_fails`、`:76 test_remove_reports_whether_the_file_existed`、`:84 test_names_lists_files_sorted_and_tolerates_missing_dir`、`:107 test_rejects_absolute_and_traversal_names`（`:93-105` 参数化名单含 `/etc/passwd`、`../escape.json`、`C:\Windows\evil.json`、`C:foo/bar` 等）、`:123 test_resolved_paths_stay_below_the_data_root`、`:131 test_data_root_points_at_the_yate_data_directory`；`:3-5` 注释指明 `tests/conftest.py` 的 autouse `isolated_home` 夹具。
- `tests/test_extension_bridges.py:558 test_data_bridge_roundtrip_under_the_isolated_home(api)`。
- symlink 夹具/先例：`tests/test_extensions.py:113-127 _symlinked_workspace(tmp_path)`（`link.symlink_to(real, target_is_directory=True)` + `pytest.skip("symlinks are not supported on this platform")`）；`tests/test_yxp.py:429-554`（`os.symlink(...)` + `pytest.skip("symlink creation unavailable")`，如 `:438-441`、`:455-458`、`:479-482`、`:502-505`）；`tests/test_extension_flows.py:27-34`（monkeypatch `_has_symlink_component` 的 `_symlinked` / `_link_free` 替身）；`tests/test_trust.py:41`；`tests/test_workspace_filter.py`。

---

## S-06 依赖、dev 组、CI、lockfile / SCA

- `pyproject.toml:1-3 [build-system] requires = ["hatchling"]`；`:12-15 dependencies = ["textual>=8.0", "pyperclip>=1.8.2"]`（仅有下界）；`:17-18 [project.scripts] yate = "yate.cli:main"`；`:20 [project.optional-dependencies]`。
- dev 组 `pyproject.toml:24-63`（`:21-23` 注释说明含 ts 组）：`pyright>=1.1.400`、`pytest>=8.0`、`pytest-cov>=5.0`、`pytest-xdist>=3.6`、`tree-sitter>=0.24,<0.26` 及 `:33-56` 各 grammar、`lupa>=2.0`、`pymarkdownlnt>=0.9.41,<1.0`、`fonttools>=4.53`、`brotli>=1.0`。其余 extras：`:64-68 lua = ["lupa>=2.0"]`、`:69-103 ts`（`:73-77` `<0.26` 上界原因注释）、`:104-110 build = ["pyinstaller>=6.0","pillow>=10.0"]`。
- 门禁配置：`:115-127 [tool.pyright]`（`strict`、`pythonVersion="3.12"`、`include`）；`:129-142 [tool.pytest.ini_options]`（`testpaths=["tests"]`、`addopts="-q"`、`:140-142` 本地复现命令注释）；`:144-151 [tool.coverage.run]`；`:153-166 [tool.coverage.report] fail_under = 75`（`:160-166` 单一真值来源说明）；`:173-187 hatch version / wheel / sdist。
- CI 文件与依赖步骤：
  - `.github/workflows/test.yml:1-15` 头注释（`:9-12` 本地复现 `pip install -e ".[dev]"`、`pytest`、coverage；`:14-15` 与 `.workflow/test.yml` 相互独立）、`:38-39 permissions: contents: read`、`:57-62 actions/checkout@v4 fetch-depth: 0`、`:64-69 setup-python@v5` + `cache: pip` + `cache-dependency-path: pyproject.toml`、`:71-72 Upgrade pip`、`:74-80 Pin canonical remote`、`:82-87 Changelog gate: python -m tools.changelog check`、`:89-90 Install package and dependencies: python -m pip install -e ".[dev]"`、`:92-115 pytest --cov=yate --cov-branch --cov-report=term-missing -n auto`；smoke job `:122-178`（`:147-148` 同一安装命令、`:166-168` `python -m tools.smoke_test run ...`、`:170-178` upload-artifact）；lint job `:183-215`（`:199-200` 安装、`:201-204` `pyright --version`、`:205-215 pyright --pythonplatform Windows`）。
  - `.workflow/test.yml:1-31` 头注释（`:19-22` 本地复现、`:24-31` 门禁分工与 `--require-zh` 说明）、`:48-72` 单 stage：`:63 python --version`、`:63 python -m pip install --upgrade pip`、`:65 python -m tools.changelog check`、`:67 pip install -e ".[dev]"`、`:72 TERM=xterm-256color python -m pytest tests --cov=yate --cov-branch --cov-report=term-missing -n auto`。
- lockfile / SCA 事实：全仓 `*.lock` 0 个、`requirements*.txt` 0 个；`*lock*` 唯一命中 `tools/smoke_test/smoke_baselines/move_line_block.json`。仓库 `*.yml` 仅 `.github/workflows/test.yml` 与 `.workflow/test.yml`（无 dependabot 配置）。`.github` 内 `audit|security|scan|lock|codeql|dependabot|pip-audit|safety|osv|trivy` 仅命中 `.github/workflows/test.yml:98` 注释里的 "wall-clock" 与 `.github/sync-to-gitee.sh:23` 的 "safety net" 注释；无 SCA / 依赖审计步骤。
- 相关测试：`tests/test_dependency_groups.py`、`tests/test_gate_config.py`、`tests/test_diagnostics.py:352,368,395,440,468,474`（packages 段用例）、`tests/test_changelog_tool.py`。

---

## S-07 diagnostics 全文、argv 记录点、`--diag`

**`yate/diagnostics.py` 全文（466 行）**

- `:1-11` 模块注释（"All values are read from existing modules' real interfaces"、best-effort `<probe failed: ...>`、终端才着色）。
- `_TERMINAL_ENV: tuple[str, ...]` `:32-37` = `("TERM", "COLORTERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION")`；`_OPAQUE_TERMINAL_ENV` `:38` = `("WT_SESSION",)`。`:46-52` ANSI 常量；`:57-66` `_KV_LINE_RE` / `_LABEL_LINE_RE` / `_SKIPPED_EXTRAS = frozenset({"dev","build"})` / `_SECTION_TITLE_RE`；`:71 type SectionFn`。
- `format_report(editor: Editor, *, color: bool = False) -> str` `:76-117`（`:83-96` 12 个 section 顺序：system/terminal/shell/paths/yaterc/config/themes/syntax/extensions/lsp/fonts/packages；`:105-112` 每节 best-effort；`:114-117` 拼接与着色）。
- `print_report(editor: Editor) -> None` `:120-125`（`:122 sys.stdout.isatty()`、`:125 print(format_report(...))`）；`_enable_windows_ansi` `:128-145`；`_colorize_line` `:148-166`；`_kv(key, value, *, width=18) -> str` `:171-175`。
- 路径 / 环境输出点：`_section_system` `:180-189`（`:183 platform.platform()`、`:186 sys.executable`、`:187 sys.prefix`）；`_section_terminal` `:194-208`（`:202-204` 逐个 `_TERMINAL_ENV` 原值、`:205-207` opaque 仅 `<set>/<unset>`）；`_section_shell` `:213-221`（`:219 " ".join(integrated)`、`:220 _kv(":! default", shell_name())`）；`_section_paths` `:226-252`（`:242 package_root()`、`:243 bundled_extensions_dir()`、`:244 user dir (~/.yate)`、`:245 crash data dir`、`:247-251` 最多 5 个 crash 文件名）；`_section_yaterc` `:257-282`（`:261 user_config_path()`、`:263 find_project_config()`、`:271-279` `config.sources` / `config.errors`）；`_section_config` `:287-301`（`:299 extension_paths`、`:300 theme_dirs`）；`_section_extensions` `:344-383`（`:357-368` 候选目录与 `ext-file` 路径、`:375-383` `record.path` / `record.error`）；`_section_lsp` `:388-411`（`:404 command`、`:405 args`、`:410 env keys` 只列键名）；`_section_packages` `:430-457`；`_package_version` `:460-465`。
- argv 记录点：`yate/cli.py:466 log.info("startup: argv=%r cwd=%s", sys.argv, Path.cwd())`；`:460-465 tracing.configure(yate_trace=..., yate_trace_level=...)`；`:467-468` 紧随的 `log.info("rc files: %s", ...)`。`yate/diagnostics.py` 全文无 `sys.argv` 输出。
- `--diag` 分支：`yate/cli.py:203-208` 参数定义、`:63` help、`:487-509`（`:491 if args.diag:`、`:494 app = YateApp(...)`、`:506-507 load_extensions() / register_configured_servers()`、`:508 diagnostics.print_report(app.editor)`、`:509 return 0`）。

**现有测试文件与用例名**

- `tests/test_diagnostics.py:47 test_report_contains_all_twelve_sections`、`:53 test_report_has_header_and_divider`、`:62 test_yaterc_option_appears_in_config_section`、`:70 test_kv_separator_is_colon_everywhere`、`:88 test_broken_extension_shows_error_reason`、`:101 test_lsp_env_keys_are_shown_but_values_are_masked`、`:121 test_failing_section_does_not_abort_report`、`:140 test_plain_report_has_no_ansi_escapes`、`:145 test_colored_report_keeps_text_and_masks_secrets`、`:163 test_print_report_writes_plain_text_to_stdout`、`:182 test_print_report_colors_on_a_terminal`、`:194 test_colored_report_styles_the_error_lines`、`:210 test_empty_section_body_renders_none`、`:219 test_recent_crash_reports_are_listed`、`:234 test_yaterc_load_errors_are_listed`、`:245 test_missing_extension_file_is_flagged`、`:254 test_rc_and_ext_dir_candidates_are_listed`、`:273/:282/:290/:298` 占位/语法段、`:311/:352/:368/:395/:440/:468/:474` packages 段、`:523/:552` LSP diagnostics 降级用例。
- `tests/test_cli.py:135 test_diag_flag_is_store_true`、`:355 test_diag_prints_report_without_running_tui`、`:376 test_diag_with_none_yaterc_reports_no_rc_loaded`。

**文档 / 手册（中英）**

- `yate/resources/manual.en.md:90` 选项表 `--diag`、`:108` 示例 `yate --diag`、`:1109` "Find the resources directory in the paths section of `yate --diag`"；`yate/resources/manual.zh.md:88`、`:106`、`:1008`。
- `yate/cli.py:61-65` 内建 help 文本含 `--diag` / `--install-extension`。

---

## S-08 wiki translate-cmd 参数来源与 `shell=True`

**源码事实 / 签名 / 参数链**

- `tools/pack/wiki/translate.py:1-20` 模块注释（`:3-4` "subprocess plumbing around `--translate-cmd`"、`:11-19` 所有经晚期绑定 facade 的名字）；`:63-85 __all__`；`:88 TRANSLATE_TIMEOUT_S: Final[float] = 900.0`；`:97-99 _INTERRUPT_EXIT_CODES`；`:103 _PREVIEW_TRANSLATE_HOOK`；`:117 _emit_mode`；`:119 _COLLECTED_FAILURES`；`:155 _stage_local`；`:159 _STOP_POLL_S`；`:208 _TERMINATE_WAIT_S`。
- `_run_translate(text: str, translate_cmd: str) -> tuple[str | None, str | None]` `:234-330`；`shell=True` 位于 `:253`（`:251-260 _wiki_facade.subprocess.Popen(translate_cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace")`）；`:261-266` 无法启动 shell 的 `WIKI_TRANSLATE_FAILED`、`:292-295` 超时 `TimeoutExpired(cmd=translate_cmd)`、`:322-329` rc/stdout 判定。
- `translate_via_cmd(text: str, translate_cmd: str) -> str | None` `:333-354`；文档串 `:340-342` "*translate_cmd* is executed through the shell ... must therefore come from a trusted source (the local CLI invocation / yaterc), never from untrusted input"；`:351` 调 `_wiki_facade._run_translate`。
- 其余：`_translation_state(*, has_en, recorded, digest, translate_cmd: str | None, translate_all) -> _PageState` `:380-403`；`needs_translation(page, target, manifest, translate_all) -> bool` `:406-450`；`_run_batch(plans, translate_cmd: str, stop, index, board) -> list[_PageOutcome]` `:453-517`（`:502-504` 调 `translate_via_cmd`）；`_translate_pending(plans, translate_cmd: str, *, target, jobs, console, lint_pool) -> _TranslationReport` `:520-690`（`:619 pool.submit(_run_batch, ..., translate_cmd, ...)`）。
- `tools/pack/wiki/run.py:93-195 _prepare_pages(pages, target, manifest, *, translate_cmd: str | None, translate_all: bool, lint_pool, console)`（`:164-170` 传 `_translation_state`、`:176-182` 无 translator 时记录 missing/stale）；`run(target: Path, translate_cmd: str | None, *, force=False, translate_all=False, check=False, push=False, repo_root=None, jobs=None) -> int` `:198-208`；`:251-255` 无 hook 时 `--translate-all` 提示；`:265-273` 传 `_prepare_pages`；`:275-296` `if translate_cmd is not None` → `:283-291 _translate_pending(plans, translate_cmd, ...)`。
- 参数来源：`tools/pack/cli.py:93-104 wiki_cmd = subparsers.add_parser("wiki", ...)`；`:113-121 wiki_cmd.add_argument("--translate-cmd", default=None, metavar="CMD", help="shell command translating Chinese markdown on stdin to English on stdout ... it is run via the shell and must come from a trusted source")`；`:122-134 --force` / `--translate-all`；`:135-160 --check` / `--push` / `--jobs` / `--debug`；`:203-209 return wiki.run(target, args.translate_cmd, force=args.force, translate_all=args.translate_all, ...)`。
- `tools/translate/__init__.py:3-6`：`python -m tools.translate [IN] [OUT]`，无 IN 时读 stdin，"exactly the protocol `tools.pack.wiki` speaks through `--translate-cmd`"。

**现有测试文件与用例名**

- `tests/test_pack_wiki.py:98 test_run_reports_missing_without_translator`、`:153 test_translate_cmd_fills_missing_pages`、`:199 test_stale_is_reported_then_retranslated`、`:248 test_failed_fresh_retranslation_does_not_bless_manifest`、`:280 test_translate_all_mode_retranslates_every_page`、`:307 test_translate_all_with_force_is_accepted`、`:323 test_force_without_translator_reports_stale`、`:356 test_translate_helper_gives_up_on_a_slow_command`、`:519 test_translate_helper_runs_shell_command()`、`:533 test_cli_wiki_subcommand_wiring`、`:580 test_needs_translation_decision_matrix`、`:608 test_run_previews_pending_count_and_failure_lines`、`:634 test_run_reports_nothing_to_translate_when_fresh`、`:651 test_keyboard_interrupt_maps_to_exit_130`。
- `tests/test_pack_wiki_errors.py:321 test_translate_via_cmd_failure_reports_wiki_0201_on_stderr`、`:337 ...timeout_reports_wiki_0202_on_stderr`、`:488 test_an_unstartable_shell_is_reported_as_wiki_0201`、`:574 test_translate_via_cmd_maps_a_console_interrupt_to_keyboard_interrupt`、`:715 test_empty_translation_stage_reports_nothing`、`:738 test_translate_all_without_a_hook_says_it_has_no_effect`、`:963 test_feed_stdin_failure_goes_through_the_failure_channel`、`:971 ...is_queued_while_collecting`。
- 另有 `tests/test_pack_wiki_parallel.py`、`tests/test_pack_wiki_lint.py`、`tests/test_wiki_subpackage.py` 含 `translate_cmd` / `translate_via_cmd` / `_run_translate` 符号。

**相关文档（tools / .trae/documents）**

- `.trae/documents/translate-cmd-tool-plan.md:1-45`（`:1` 标题、`:3` 实施状态、`:22-23` `python -m tools.translate [IN] [OUT]`、`:30-31` 非目标"不改 `tools/pack/wiki.py` 的钩子协议"、`:38` Windows argv 上限、`:44` 接口设计）。
- `.trae/documents/wiki-translate-progress-plan.md:1-19`（`:8` `python -m tools.pack wiki --translate-cmd ...`、`:16` "不改 `translate_via_cmd` 的 I/O 协议与 900s 超时语义"、`:18-19` rich 传递依赖先例）。
- 其他命中 `translate-cmd`/`translate_cmd`/`shell=True` 的计划文档：`.trae/documents/pack-wiki-plan.md`、`.trae/documents/pack-wiki-parallel-translate-plan.md`、`.trae/documents/pack-wiki-review-fixes-plan.md`、`.trae/documents/pack-wiki-progress-refresh-plan.md`、`.trae/documents/pr59-pack-wiki-refresh-review-fixes-plan.md`、`.trae/documents/mdlint-plans/mdlint-wiki-plan-b.md`、`.trae/documents/full-repo-audit-plan.md`、`.trae/documents/repo-audit-r2-plans/overview.md`、`.trae/documents/split-module-tests-plans/overview.md`、`.trae/documents/test-speedup-plans/test-speedup-slow-tests-plan-b.md`、`.trae/documents/closure-sweep-plans/closure-sweep-reviews-plan-c.md`、`.trae/documents/trae-review-fixes-plans/trae-review-fixes-plan-e.md`、`.trae/documents/code-review-fix-plans/code-review-fix-suggestions-plan-b.md`、`.trae/documents/overview.md`、`.trae/documents/extension-trust-hardening-issue.md`。
- `tools/pack/cli.py:96-103` wiki 子命令 description 亦为 `--translate-cmd` 的 CLI 内文档。

---

## 附加 A：`tests/test_architecture.py` 守卫常量与内容概要

常量（`:` 为定义行；关联测试行号并列）：

- `:114 PROJECT = Path(__file__).resolve().parent.parent`、`:115 YATE = PROJECT / "yate"`、`:120 APP_IMPORTERS_ALLOWED = {"cli.py"}`（测试 `:723 test_only_cli_imports_app`）、`:123 UPWARD_MODULES`、`:129 ALLOWED_PROTOCOLS`、`:168 UPWARD_EDGES_FROZEN = frozenset()`。
- `:177-183 UI_FREE_PACKAGES`（`session`/`registries`/`config`/`...`/`editor_core` 等）；`:186-193 UI_FREE_FILES: tuple[str,...] = ("session.py", "registries.py", "config.py", "yaterc.py", "yaterc_options.py", "dist_meta.py")`；使用点 `:762`、`:1036`；测试 `:752 test_keymaps_services_and_models_stay_ui_free`、`:1026 test_ui_free_layers_do_not_import_textual_app`。
- `:198 UI_FROZEN_FILES: dict[str, set[str]]`（`flows/document_flows.py`、`flows/window_flows.py` 等允许的 `editor_components` 耦合）；测试 `:830 test_collaborators_keep_widget_coupling_frozen`。
- `:267-272 EXTENSION_SUBMODULES` = 4 个（`...api` / `...bridges` / `...loader` / `...lua`）；`:277-281 EXTENSION_FORMER_MODULES` = 3 个旧模块名；`:286-301 EXTENSION_FACADE_NAMES` = 14 个冻结导出名（`AnyCallback`…`load_startup_extensions`）；测试 `:1367 test_extension_machinery_hides_behind_facade`、`:1388 test_extension_facade_exports_the_frozen_plugin_names`；`:304 EDITOR_FORBIDDEN_IMPORTS`、`:307 BUILTIN_TABLE_MODULES`、`:313-317 BANNED_SUFFIXES` / `BANNED_SUFFIX_WHITELIST={"PaneHost"}` / `BANNED_NAMES={"AppProtocol"}`。
- `:324 MAX_SOURCE_LINES: int = 800`；`:360-365 SIZE_EXEMPT_FILES: frozenset[str]` = `{"keymaps/vim.py", "editor_components/file_manager/screen.py", "editor_core/buffer.py", "editor_syntax/langdefs.py"}`（`:350-359` 为拆分历史注释）；使用点 `:916`；测试 `:899 test_source_files_within_size_threshold`。
- `:374-380 BANNED_COMMENT_RANGES`（`0x00A7`、`0x00B0`、`0x3000-0x303F`、`0x4E00-0x9FFF`、`0xFF00-0xFFEF`）；`:391-408 NON_ASCII_COMMENT_EXEMPT: frozenset[tuple[str,str]]` = 6 个 `(路径, 符号或 <module>:行号)` 条目，涉及 `tests/test_pack_spec.py`、`tools/changelog/__init__.py`、`tools/changelog/segments.py`、`tools/probes/pb6_real_input_harness.py`、`yate/editor_sprites/characters.py`；使用点 `:1442`、`:1462`；测试 `:1417 test_comments_and_docstrings_stay_ascii`。
- `:417-419 HOME_PATH_PATTERN`（POSIX home / macOS Users / Windows Users 三类），`:430 HOME_PATH_EXEMPT = frozenset()`；测试 `:1524 test_no_machine_local_home_paths_in_sources`。
- `:436 SCROLLABLE_BASES`、`:450 SCROLLBAR_EXEMPT = frozenset()`。
- `:474-478 PRINT_EXEMPT_SITES: dict[str, frozenset[str]]` = `{"cli.py": {"main", "_manage_extensions"}, "diagnostics.py": {"print_report"}, "logs.py": {"warn"}}`；使用点 `:1512`；测试 `:1496 test_no_debug_prints_in_library_modules`。
- `:936 LOG_LEVEL_METHODS`；另有 `:956 test_log_calls_use_lazy_percent_formatting`、`:1016 test_logging_never_touches_devtools_channel`、`:1339 test_leaf_package_reexports_carry_exception_note`、`:899` 等守卫用例（完整 `^def test_` 列表位于 `:584-1556`）。

---

## 附加 B：CHANGELOG 生成 / 检查命令的既有约定

- 工具目录 `tools/changelog/`：`classify.py`、`cli.py`、`gitdata.py`、`gitee.py`、`model.py`、`render.py`、`segments.py`、`translations.py`、`zh_overrides.json`、`__init__.py`、`__main__.py`（`search_file` 结果 11 项）。
- `tools/changelog/__main__.py:1-8`：`python -m tools.changelog` → `from tools.changelog.cli import main` → `raise SystemExit(main())`。
- `tools/changelog/__init__.py:1-20`：`:3-5` 由 git 历史生成 `CHANGELOG.md` / `CHANGELOG.zh.md`、遵循 `.trae/documents/changelog_plan.md`；`:7-12` 版本段/Conventional Commits/`zh_overrides.json`/`[缺中文]`；`:14` "Entry point: `python -m tools.changelog --help`"。
- `tools/changelog/cli.py:5-20` 子命令契约：`generate [--online] [--limit N] [--date YYYY-MM-DD] [--check] [--require-zh] [--overrides PATH] [--root-only|--bundle-only]`、`check [--online] [--require-zh] [--overrides PATH]`、`zh-commit <hash> <summary> [<detail>] [--overrides PATH]`；函数 `generate(repo, ...)` `:121`（`:141-142` 无 git 历史时 SKIP）、`check(repo, ...)` `:252-262`（等价于 `generate --check`）、`main(argv)` `:299`；argparse `:308-356`（`:318 gen --check`、`:321 gen --require-zh`、`:338 chk`、`:340-343 chk --require-zh`、`:349-356 zc`）；dispatch `:362-387`。
- CI 约定：`.github/workflows/test.yml:5-8`（`CHANGELOG*` 不在 paths-ignore，因门禁校验这些编辑）、`:9-12` 本地复现命令、`:58-62 fetch-depth: 0`、`:74-80` `git remote set-url origin https://gitee.com/jermaine/yate.git`、`:82-87` "Changelog gate" `python -m tools.changelog check`；`.workflow/test.yml:19-22`、`:24-31`（Gitee Go 不跑 pyright 与 py3.13、双方均不启用 `--require-zh`）、`:64-65` 同一步 `python -m tools.changelog check`。
- 计划文档 `.trae/documents/changelog-plan.md:23-24`（两份 CI 同步加入门禁）、`:127-129`（`pack.ps1 / pack.sh` → `python -m tools.changelog` → PyInstaller）、`:460-462`（`--changelog` argparse）、`:518-522`（`fetch-depth: 0` 与门禁步骤）、`:530-533`（发布流程第 3-4 步 `zh-commit <hash> "中文摘要"`、`generate --online`）、`:606-622`（"生成与门禁（自举场景）"命令清单：`generate`、`check`、`generate --check`、`generate --online`、无 `.git` 时 `check` 输出 SKIP 且退出码 0）。
- 相关测试/资源：`tests/test_changelog_tool.py`、`tests/test_changelog_view.py`、`tests/test_cli.py`（`--changelog` 分支 `yate/cli.py:194-202`）、`tools/smoke_test/smoke_baselines/manual_changelog_modals.json`；生成产物 `CHANGELOG.md`、`CHANGELOG.zh.md`、`yate/resources/changelog.en.md`、`yate/resources/changelog.zh.md`。
