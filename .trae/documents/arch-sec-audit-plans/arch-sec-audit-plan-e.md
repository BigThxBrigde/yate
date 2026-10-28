# arch-sec-audit plan-e：yxp 解包拒绝穿符号链接（S4）+ 无校验包安装告警（S6）

## 输入与依据

- 取证 1（S4）：`yate/services/yxp.py:419-453` `_extract_payload` 对每个 manifest 成员
  `target.is_file() or target.is_symlink()` 时先读旧内容（经链接），随后
  `target.write_bytes(...)` **穿预置符号链接写出**到 `~/.yate/extensions` 外的任意目标。
  前置条件是攻击者已能写扩展目录（低危），但 yxp 其余防护（zip-slip `_check_member_name`、
  炸弹水位线、TOCTOU 二次校验）都已闭环，此为最后缺口。
- 取证 2（S6）：`yxp.py:9-13,179-186` 无 `checksum` 成员的包按格式契约"未校验安装"，
  安装路径无任何告警。
- 既有测试面：`tests/test_yxp.py`（基线 collect 61 条用例），应已具备构建包 fixture
  （先通读 fixture 与 helper 再写用例，复用现有构造方式）。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `yate/services/yxp.py`
2. `tests/test_yxp.py`

## 具体修改

### 1. `yate/services/yxp.py` — `_extract_payload`（:431-439 循环）

循环体内、写盘之前加卫语句：

```python
            for rel in package.manifest.files:
                target = ext_dir / rel
                if target.is_symlink():
                    raise YxpError(
                        f"cannot install {package.manifest.name}: {rel!r} target "
                        "is a symlink; refusing to write through it"
                    )
                if target.is_file():
                    previous[rel] = target.read_bytes()
                ...
```

- 语义决策（登记）：**拒绝并失败整个安装**（而非 unlink 后重写常规文件）——目标位出现
  符号链接只能来自外部干预，属可疑状态；失败让用户自行清点。异常走既有
  `except YxpError` 回滚分支（此时 `extracted` 为空或不含该成员，回滚安全）。
- 模块 docstring 的防护清单（:9-13 附近若有逐条列举）同步补一句 symlink 拒写。

### 2. `yate/services/yxp.py` — 安装入口告警（S6）

- 定位 `install()`（或等价入口，约 :380-409 区域，`log.info("installed extension ...")`
  所在函数）：函数开头（写盘前）加：

```python
    if package.checksums is None:
        log.warning(
            "installing extension package %s without a checksum member: "
            "contents cannot be verified",
            package.manifest.name,
        )
```

- 惰性 `%` 格式（coding-style §4.6）；不加 UI 交互（保持无 checksum 包可装，
  仅告警，格式契约不变）。

### 3. `tests/test_yxp.py` 追加用例

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_install_refuses_symlinked_member_target` | 正常安装一次；随后把其中一个已安装成员文件替换为指向外部文件的符号链接（`os.symlink` 可能因权限失败 → `try/except (OSError, NotImplementedError): pytest.skip(...)`） | 再次 `install` 同一包 | 抛 `YxpError` 且消息含 `"symlink"`；外部目标文件内容**未被改写**（读回与预置一致）；扩展目录状态与安装前一致 |
| `test_install_overwrites_regular_member_still_works` | 正常安装一次（成员为常规文件） | 再次 `install` 同一包 | 成功返回 `InstallReport`；目标文件为新内容（守护"不过度收紧"） |
| `test_install_without_checksum_logs_warning` | 构造**无 checksum 成员**的包（fixture 支持与否先核实；不支持则按现有 helper 手工去表） | `install` + caplog 捕获 `yate.services.yxp` logger | 安装成功；记录含 `"without a checksum member"` 且级别为 WARNING |
| `test_install_with_checksum_no_warning` | 构造**带 checksum** 的包 | `install` + caplog | 安装成功；无该 WARNING 记录 |

- 符号链接用例的 skip 在 Windows 无特权环境是预期结果（CI Windows 腿可能跳过，
  POSIX 腿真实执行）；skip 理由写明 "symlink creation unavailable"。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yxp.py -q
.venv\Scripts\python.exe -m pyright yate/services/yxp.py
```

通过判定：`tests/test_yxp.py` exit 0（新增 4 条全过或 symlink 1 条合规 skip）；
pyright 零诊断。

## 风险与回滚

- 行为收紧仅覆盖"成员目标已是符号链接"这一非常规前置态；常规安装/升级/回滚路径有
  正向用例守护（`test_install_overwrites_regular_member_still_works`）。
- 回滚 = revert 本子计划提交。
