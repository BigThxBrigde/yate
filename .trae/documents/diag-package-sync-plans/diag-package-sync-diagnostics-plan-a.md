# plan-a：diagnostics 包清单派生逻辑 + 测试（wave-1）

> 所属总纲：[overview.md](overview.md) ｜ wave-1，与 plan-b 并行（文件不重叠）

## 一、独占文件清单

只改以下两个文件，不动其它任何文件：

- `yate/diagnostics.py`
- `tests/test_diagnostics.py`

## 二、现状取证（文件:行号）

- [yate/diagnostics.py](../../yate/diagnostics.py#L18)：`from importlib import
  metadata as importlib_metadata`（既有导入，复用）；
- [yate/diagnostics.py](../../yate/diagnostics.py#L415-L428)：
  `_section_packages()` 硬编码
  `names = ["textual", "tree_sitter", "tree_sitter_python", "tree_sitter_bash"]`
  → 缺 pyperclip（issue 根因）；
- [yate/diagnostics.py](../../yate/diagnostics.py#L431-L436)：
  `_package_version(name)` 探测版本，缺失返回 `None`（复用，不改）；
- [yate/diagnostics.py](../../yate/diagnostics.py#L49-L55)：着色正则
  `_KV_LINE_RE = r"^( +)([^ -].*?): (.+)$"` 与 `_LABEL_LINE_RE =
  r"^( +)(\S.*):$"` —— 分组标签行（如 `  core:`）命中后者、明细 kv 行命中
  前者，格式兼容；
- [yate/diagnostics.py](../../yate/diagnostics.py#L87-L93)：`format_report`
  best-effort 机制——单节异常降级为 `<probe failed: ...>` 行；
- 实测（worktree 沙箱）：`importlib.metadata.requires("yate")` 返回 13 条
  Requires-Dist，extras 带 `; extra == 'x'` 标记；`version("tree-sitter")`
  规范名命中 `0.25.2`；无 Requires-Dist 的 dist `requires()` 返回 `None`。

## 三、具体修改

### 3.1 新增两个模块级正则与一个跳过集（放在 `_LABEL_LINE_RE` 之后、`_SECTION_TITLE_RE` 附近）

```python
#: Distribution name at the start of a Requires-Dist string.
_REQ_DIST_RE: re.Pattern[str] = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

#: Extra group inside a requirement marker (``; extra == 'ts'``).
_REQ_EXTRA_RE: re.Pattern[str] = re.compile(r"\bextra\s*==\s*['\"]([^'\"]+)['\"]")

#: Tooling extras kept out of the diagnostics inventory: their members are
#: development / build machinery, not runtime packages (user decision on
#: issue IKJJFI). Membership still comes from metadata -- only the display
#: of these extra groups is filtered.
_SKIPPED_EXTRAS: frozenset[str] = frozenset({"dev", "build"})
```

### 3.2 重写 `_section_packages()`（替换 415-428 行整段）

签名不变（`() -> list[str]`），数据流：
`requires("yate")` → 逐条解析（名字 + extra 组）→ 按组聚合
（`dict[str, dict[str, str]]`，组内以规范名去重）→ core 恒最前、extra 组按
名排序、组内按名排序 → 标签行 + kv 行（名宽全局对齐）。

```python
def _section_packages() -> list[str]:
    """Derive the package inventory from yate's own dist metadata.

    Single source of truth (issue IKJJFI): hatchling bakes pyproject.toml's
    dependencies and extras into the installed dist-info (Requires-Dist
    headers), so the report always matches what was declared at build time
    -- no hand-kept list to drift. Core requirements render under a
    ``core:`` label first, then one label per extra in name order; the
    tooling extras in :data:`_SKIPPED_EXTRAS` stay out of the report.
    """
    raw = importlib_metadata.requires("yate")
    if raw is None:
        return []
    groups: dict[str, dict[str, str]] = {}
    for req in raw:
        name_match = _REQ_DIST_RE.match(req)
        if name_match is None:
            continue  # malformed entry -- hatchling output is always valid
        name = name_match.group(1)
        marker = _REQ_EXTRA_RE.search(req)
        group = marker.group(1) if marker else "core"
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        groups.setdefault(group, {})[canonical] = name
    ordered = ["core"] + sorted(
        name for name in groups if name != "core" and name not in _SKIPPED_EXTRAS
    )
    # "core" leads unconditionally but may be empty (every requirement
    # carries an extra marker); drop empty groups before rendering.
    ordered = [name for name in ordered if groups.get(name)]
    if not ordered:
        return []
    width = max(len(name) for group in ordered for name in groups[group])
    lines: list[str] = []
    for group in ordered:
        lines.append(f"  {group}:")
        for name in sorted(groups[group].values()):
            version = _package_version(name)
            display = version if version is not None else "not installed"
            lines.append(_kv(name, display, width=width))
    return lines
```

行为要点：

- `requires()` 抛 `PackageNotFoundError`（无 yate dist-info 的怪异安装）→
  向上传播，由 `format_report` 降级为 `<probe failed: ...>` 行，不炸整报；
- `requires()` 返回 `None`（理论上不发生）或过滤后无组可显示 → 空清单，
  节渲染 `(none)`；
- `dev` / `build` extra 组按 `_SKIPPED_EXTRAS` 过滤（展示策略，成员资格仍
  自动派生）；tree-sitter 三包由 ts extra 声明，照常显示——即使某环境只装
  了 dev extra，ts 组声明的成员也在清单中（显示安装状态）；
- 组间不去重：tree-sitter 同属 dev 与 ts，在 ts 组显示一行（dev 组已整组
  过滤，无重复行）；
- 展示名用 Requires-Dist 里的书写形态（如 `tree-sitter-python` 连字符形态）。

## 四、新增测试用例（三要素齐全）

测试文件：`tests/test_diagnostics.py`（沿用既有 patch 风格：
`patch("yate.diagnostics.importlib_metadata.requires", ...)` /
`patch("yate.diagnostics.importlib_metadata.version", ...)`，模块对象共享，
两处调用同步生效）。

### T1 `test_packages_section_derives_core_dependencies_from_metadata`

- **验证目标**：真实元数据驱动（pyproject 单一事实来源），core 依赖齐全
  （issue 主诉：pyperclip 不再缺失）。
- **前置**：worktree 沙箱（yate editable 安装，dist-info 带 Requires-Dist）；
  无需 fixture。
- **操作**：`lines = diagnostics._section_packages()`。
- **断言**：
  - `"  core:" in lines`；
  - core 组切片内存在 `pyperclip` 与 `textual` 的明细行（名字在行内、行含
    `": "` 分隔）；
  - 两行的值都不是 `"not installed"`（core 依赖必然随 yate 安装）。

### T2 `test_packages_section_lists_declared_feature_extras_and_skips_tooling`

- **验证目标**：功能 extra 自动成组（自动同步的核心承诺）；dev / build
  工具链 extra 按策略过滤。
- **前置**：同 T1。
- **操作**：`lines = diagnostics._section_packages()`；从
  `importlib.metadata.requires("yate")` 解析出声明的 extra 名集合。
- **断言**：
  - 对每个声明的、不在 `_SKIPPED_EXTRAS` 中的 extra 名 `e`，`f"  {e}:" in
    lines`（当前 pyproject 即 `ts` 组出现）；
  - `  dev:` 与 `  build:` 标签行不存在；
  - `pyright` / `pytest` / `pyinstaller` / `pillow` 不出现在任何行；
  - core 标签行索引小于全部 extra 标签行索引（core 恒最前）；
  - `tree-sitter` 出现在 ts 组切片内。

### T3 `test_packages_section_parses_controlled_requirements`

- **验证目标**：解析逻辑的确定性——extra 归组、组内去重、规范名键、
  展示名保留书写形态、not installed 降级、跳过集过滤。
- **前置**：patch `yate.diagnostics.importlib_metadata.requires` 返回：

  ```python
  [
      "textual>=8.0",
      "pyperclip>=1.8.2; extra == 'ts'",
      "pyperclip>=1.8.2; extra == 'ts'",  # 组内重复 → 去重为 1 行
      "Foo_Bar>=1.0; extra == 'ts'",      # 规范名 foo-bar，展示名保留
      "pyright>=1.1.400; extra == 'dev'", # 跳过集成员 → 不显示
  ]
  ```

  patch `yate.diagnostics.importlib_metadata.version` 为普通函数
  `side_effect`：`Foo_Bar` 返回 `"9.9"`，其余名字抛
  `importlib.metadata.PackageNotFoundError`。
- **操作**：`lines = diagnostics._section_packages()`；按标签行切片分组。
- **断言**：
  - `core` 组恰有 1 条 textual 行；
  - `ts` 组恰有 2 条：pyperclip（not installed）与 `Foo_Bar : 9.9`
    （展示名保留大小写/下划线书写形态）；
  - `dev` 组不渲染，`pyright` 不出现在任何行；
  - 明细行缩进 4 空格、标签行缩进 2 空格（命中着色正则的形态）。

### T4 `test_packages_section_without_requires_metadata_is_empty`

- **验证目标**：`requires()` 返回 `None` 的边界 → 空清单（节渲染 `(none)`）。
- **前置**：patch `requires` 返回 `None`。
- **操作 / 断言**：`diagnostics._section_packages() == []`。

### T6 `test_packages_section_without_core_requirements_renders_extras_only`（审核轮 1 追加）

- **验证目标**：全带 extra marker（core 组为空）时不抛 `KeyError: 'core'`、
  不渲染空 core 标签（评审轮 1 major 缺陷的回归守卫）。
- **前置**：patch `requires` 返回仅含 `extra == 'ts'` 的两条；patch
  `version` 全抛 `PackageNotFoundError`。
- **操作**：`lines = diagnostics._section_packages()`。
- **断言**：`lines` 非空；`"  core:" not in lines`；分组恰为 `["ts"]` 且
  全部行含 `not installed`。

### T5 既有 `test_missing_packages_are_reported_as_not_installed`（不改，回归）

- **验证目标**：patch `version` 全抛后报告仍含 `not installed`（降级语义），
  且新增派生逻辑在该 patch 下不炸（`requires` 未 patch → 真实元数据照常
  解析）。

## 五、验证方案

| 目标 | 命令 | 通过判定 |
|---|---|---|
| 新增用例 + 既有回归 | `.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py -q` | 退出码 0，全绿 |
| 端到端核对 | `.venv\Scripts\python.exe -m yate --diag` | `[packages]` 节含 `core:` 标签与 pyperclip 行 |
| 架构守卫 | `python -m pytest tests/test_architecture.py -q` | 22 passed |

无法自动化的部分：无（分组渲染为纯文本，可直接断言）。

## 六、风险与回滚

- 着色正则冲突：T3 断言缩进形态即守卫；回滚 = revert 本文件改动；
- 受控测试 patch 泄漏：全部经 `patch` 上下文管理器自动还原（既有测试同款
  机制）。
