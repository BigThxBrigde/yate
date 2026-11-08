# 子计划 f — S-07 `--diag` 报告隐私提示（wave-2）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-07。
> 只改 2 个文件。按主计划 §二 E 否决全量路径脱敏。

## 一、目标与非目标

- 目标：`--diag` 报告在抬头给出显式隐私提示，让用户在贴到 issue 前知道报告
  含本机绝对路径、Python 解释器前缀与终端环境变量；新增用例钉住提示位置。
- 非目标：不删 / 不遮蔽任何既有字段值、不改 `_TERMINAL_ENV` 白名单、不改
  `cli.py:466` 的 tracing argv 记录（该事实由 plan_g 在手册说明）、不改
  `print_report` 的着色 / stdout 语义、不改 12 个 section 的顺序。

## 二、独占文件清单

1. `yate/diagnostics.py`
2. `tests/test_diagnostics.py`

## 三、具体改动

### 3.1 `yate/diagnostics.py:57-66（常量区）, 98-102（抬头）`

- 在常量区（与 `_SKIPPED_EXTRAS` / `type SectionFn` 同区）新增带 `#:` 说明的
  模块级常量：
  ```python
  #: Shown before any section so users know the report identifies their machine.
  _PRIVACY_NOTE: str = (
      "note: this report contains absolute paths, interpreter details and "
      "terminal environment values; review it before sharing."
  )
  ```
  字符串与注释均英文 ASCII；行宽 ≤100。
- `format_report()` 的 `lines` 初始列表在 `"=" * 40,` 与空行之后插入
  `_PRIVACY_NOTE` 与一个空行：
  ```python
      lines: list[str] = [
          f"yate {__version__} — diagnostics",
          "=" * 40,
          "",
          _PRIVACY_NOTE,
          "",
      ]
  ```
  这样提示位于第一个 `[system]` 之前，且不改变任何 section 内容。
- docstring 可补一句：报告是为粘贴到 issue 设计的，抬头提示用户复核机器信息；
  不改 `format_report` 签名（仍 `editor, *, color=False`）。

### 3.2 `tests/test_diagnostics.py`

先读 `:44-84`（`test_report_contains_all_twelve_sections` /
`test_report_has_header_and_divider` / `test_kv_separator_is_colon_everywhere`）
确认抬头与行解析假设；提示行不含 `": "` 分隔，不会触发
`test_kv_separator_is_colon_everywhere` 的非空行分支。

- 新增 `test_report_warns_about_machine_details_before_sections()`：
  - act：`report = diagnostics.format_report(_build_app().editor)`；
  - assert：`diagnostics._PRIVACY_NOTE in report`；
    `report.index(diagnostics._PRIVACY_NOTE) < report.index("[system]")`；
    `"absolute paths" in report`。
- 新增 `test_privacy_note_is_plain_text_in_colored_report()`：
  `report = diagnostics.format_report(_build_app().editor, color=True)`；
  断言 `_PRIVACY_NOTE` 仍以纯文本出现（不着色、不被 ANSI 切断）。
- 既有 `test_report_has_header_and_divider()` 与
  `test_plain_report_has_no_ansi_escapes()` 不改，作为回归锚点。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/diagnostics.py tests/test_diagnostics.py
.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py tests/test_cli.py -q
.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

> `tests/test_cli.py` 在 wave-1 由 plan_a 修改，本子计划**只运行、不修改**它；
> 若 wave-2 启动时 wave-1 已提交，则该命令验证 CLI 的 `--diag` 路径未回归。

通过判定：三条退出码全 0；新增 2 例通过；12 个 section 与着色用例无回归。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 提示行被报告解析类测试当成 KV 行 | 文案不含 `": "`，且有 `test_kv_separator_is_colon_everywhere` 回归 | `git checkout -- yate/diagnostics.py tests/test_diagnostics.py` |
| 彩色报告把提示行拆成 ANSI 片段 | 新增用例断言纯文本完整出现；`_colorize_line` 只按标题/KV 规则着色 | 把提示放到 `color` 分支之外（本设计即如此） |
| 与 smoke 基线快照的 `--diag` 输出比对 | 收尾冒烟由主代理跑；若快照含完整报告文本需按规则更新基线并写明依据 | 同上 |

## 六、报告格式

改动清单、实跑命令与退出码、未解决项与原因。
