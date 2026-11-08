# 子计划 a — S-02 `.yxp` 无 checksum 默认拒绝（wave-1）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-02。
> 只改「独占文件清单」列出的 5 个文件，其它任何文件不得改动。

## 一、目标与非目标

- 目标：`install_package` 默认拒绝对缺少 `checksum` 成员的 `.yxp` 执行安装；
  CLI 提供显式 `--allow-unverified` 透传；既有「允许」路径保留并告警；
  新增回归用例覆盖默认拒绝、允许开关、无副作用、命令侧默认拒绝。
- 非目标：不改 `read_package` 的格式契约（`checksums=None` 仍合法）、不改
  `tools/yxp` 打包 / `--verify`、不改 `:install-extension` 命令语义（保持
  最严格默认）、不引入签名机制、不改报告格式。

## 二、独占文件清单

1. `yate/services/yxp/manifest.py`
2. `yate/services/yxp/install.py`
3. `yate/cli.py`
4. `tests/test_yxp.py`
5. `tests/test_cli.py`

## 三、具体改动（定位到文件:行号 / 签名）

### 3.1 `yate/services/yxp/manifest.py:1-28`

模块 docstring 第 9-13 行现写「without it the payload installs unverified」。
改为准确描述：`checksum` 缺失时 `read_package` 仍返回
`YxpPackage(checksums=None)`，但 `install_package` 默认拒绝安装，只有显式
`allow_unverified=True` 才继续（并告警）。保持英文 ASCII 注释 / docstring。

### 3.2 `yate/services/yxp/install.py:29-39, 53-83`

- 在 `from yate.services.yxp.manifest import (...)` 列表补入 `CHECKSUM_NAME`
  （字母序位置 `CHECKSUM_NAME` 在 `NAME_RE` 之前？按现有清单字典序：
  `CHECKSUM_NAME`, `NAME_RE`, `RECORDS_DIRNAME`, ...）。
- 签名改为：
  ```python
  def install_package(
      package_path: Path,
      base_dir: Path | None = None,
      *,
      allow_unverified: bool = False,
  ) -> InstallReport:
  ```
- docstring 增补一段：`*allow_unverified*` 默认 ``False``：缺少 ``checksum``
  成员时抛 :class:`YxpError` 且在任何目录创建 / 写盘之前返回；只有显式
  ``True`` 才走历史「未校验安装 + warning」路径。
- 在 `package = _facade.read_package(package_path)` 之后、`manifest = ...`
  之前，把 `:77-82` 的单分支 warning 改为：
  ```python
      if package.checksums is None:
          if not allow_unverified:
              raise YxpError(
                  f"cannot install {package.manifest.name}: missing "
                  f"{CHECKSUM_NAME!r} member; pass --allow-unverified to "
                  "install an unverified package"
              )
          log.warning(
              "installing extension package %s without a checksum member: "
              "contents cannot be verified",
              package.manifest.name,
          )
  ```
  该拒绝必须早于 `ext_dir.mkdir` / `records.mkdir` / `_extract_payload`，
  保证零副作用（含 `_manifests` 记录与目录）。

### 3.3 `yate/cli.py:64-65, 139-162, 299-322`

- 内建 help 文本（`examples` 字符串）在 `--install-extension FILE` 行后补一行
  示例：`yate --install-extension FILE --allow-unverified`（说明「for packages
  without a checksum member」），保持对齐风格。
- 在 `pkg_group` 三个互斥参数之后（`--list-extensions` 定义之后、`setup_group`
  之前）新增**独立**参数（不进互斥组）：
  ```python
      parser.add_argument(
          "--allow-unverified",
          action="store_true",
          help="install .yxp packages without a checksum member "
               "(unverified executable code; use only for packages you built "
               "yourself)",
      )
  ```
- `_manage_extensions()` 安装调用改为：
  ```python
  yxp.format_install_report(
      yxp.install_package(
          Path(package_path), allow_unverified=args.allow_unverified
      )
  )
  ```
  保持现有 `except yxp.YxpError` / 失败计数 / stdout+stderr 语义。
- 不改 `PRINT_EXEMPT_SITES`：`_manage_extensions` 已在豁免名单，
  未新增带 `print()` 的函数。

### 3.4 `tests/test_yxp.py`

- 先用 `grep -n "checksum=None"` 复核本文件内所有构造无 checksum 包的用例；
  凡调用 `yxp.install_package(...)` 且期望成功者，显式补
  `allow_unverified=True`（至少 `:251 test_install_without_checksum_installs_unverified`、
  `:582 test_install_without_checksum_logs_warning`，其余按实查结果处理）。
  **读取层**用例（如 `:51 test_read_package_without_checksum_member`）不动。
- 新增 `test_install_without_checksum_is_rejected_by_default(tmp_path: Path) -> None`：
  - arrange：`pkg = make_yxp(tmp_path / "bare.yxp", {"hello.py": b"x"}, checksum=None)`；
    `base = tmp_path / "ext"`。
  - act / assert：`with pytest.raises(yxp.YxpError, match="missing 'checksum'"):`
    `yxp.install_package(pkg, base)`；断言 `not base.exists()`（或 base 下无
    `hello.py` 且无 `_manifests/hello.json`），证明零副作用。
- 新增 `test_install_without_checksum_opt_in_installs(tmp_path: Path) -> None`：
  `allow_unverified=True` → 返回 `InstallReport`，`base / "hello.py"` 内容 `b"x"`，
  且 `_record_path(base, "hello").exists()`。
- 新增 `test_install_extension_command_rejects_unverified_package(tmp_path: Path) -> None`：
  沿用本文件既有 `register_commands` / `CommandRegistry` 夹具（先读 `:1-40` 与
  `:739` 附近的命令测试形态），注册后执行 `:install-extension <bare.yxp>`，
  断言消息栏收到含 `missing` 或 `checksum` 的 warn，且不产生安装文件。
  **不要**改 `yate/commands.py`。

### 3.5 `tests/test_cli.py`

- `test_extension_package_flags_parse()` 增补：
  `assert build_parser().parse_args([]).allow_unverified is False`；
  `assert build_parser().parse_args(["--install-extension", "a.yxp", "--allow-unverified"]).allow_unverified is True`。
- 新增 `test_main_rejects_unverified_package_by_default(capsys, tmp_path)`：
  沿用 `patch("yate.logs.crash.install")`；`pkg = make_yxp(..., checksum=None)`；
  `main(["--install-extension", str(pkg)]) == 1`；stderr 含 `missing`；
  `not (Path.home() / ".yate" / "extensions" / "hello.py").exists()`。
- 新增 `test_main_allows_unverified_package_with_flag(capsys, tmp_path)`：
  `main(["--install-extension", str(pkg), "--allow-unverified"]) == 0`；
  stdout 含 `installed hello 1.0.0`；payload 文件存在。
- 既有 `test_main_installs_and_lists_extension_packages` /
  `test_main_uninstall_extension_package` 使用 `make_yxp` 默认 `"auto"` checksum，
  保持不动（这是「有 checksum 正常路径」的回归锚点）。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/services/yxp/install.py yate/services/yxp/manifest.py yate/cli.py tests/test_yxp.py tests/test_cli.py
.venv\Scripts\python.exe -m pytest tests/test_yxp.py tests/test_yxp_subpackage.py tests/test_tools_yxp.py tests/test_cli.py -q
.venv\Scripts\python.exe -m pytest tests/test_yxp.py tests/test_cli.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

通过判定：三条退出码全 0；pyright 0 诊断；新增用例全部通过；既有未校验安装
用例仅在显式 `allow_unverified=True` 下通过。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 门面 `__all__` / 补丁缝把 `install_package` 换名或签名不一致 | 不改 `__init__.py`；调用点只新增关键字实参 | `git checkout -- <5 个独占文件>` |
| `make_yxp(checksum=None)` 的既有测试被批量改坏 | 先 grep 再逐例改，读取层用例不动 | 同上 |
| 默认拒绝发生在 `read_package` 之后但写盘之前，仍可能创建 `ext_dir` | 断言 `base` 无文件 / 无记录；代码位置在 `mkdir` 前 | 调整分支顺序（不得移到写盘后） |

## 六、报告格式

改动清单（文件 + 关键函数）、实跑命令与退出码、未解决项与原因；不得声称未
执行的命令已通过。计划外情况停下上报，由主代理裁定。
