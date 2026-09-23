# 代码覆盖率 + 测试补充计划

## Context（为什么做）

当前仓库有较完善的测试，但存在两个缺口：

1. **没有代码行覆盖率**：`tests/`（25 文件 / 620 用例）没有任何行/分支覆盖工具；`pyproject.toml` 的 dev 依赖只有 `pyright`+`pytest`，未配 `coverage.py`/`pytest-cov`。
2. **冒烟测试的 `--coverage` 是「命令/action 注册使用率」**（`tools/smoke_test/harness.py` 的 `track_coverage`），统计哪些 `:command` 与 action 被场景触发，**不是代码行覆盖**——这是两套语义，不能混淆。

目标：为单元测试引入真正的**行覆盖率**（`coverage.py`），设置**报告门槛**（整体 ≥60%，豁免难测的渲染/L4 外壳层）；按覆盖率优先补**核心纯逻辑**单元测试；同时保留并微调冒烟的命令覆盖，补充关键冒烟场景。

已与用户对齐的决策：

- **Coverage 形态**：单元测试行覆盖 + 冒烟命令/action 覆盖都要（两套并存，各自呈现）。
- **门槛策略**：设报告门槛（保守整体 ≥60%），渲染层/`__init__`/外壳可豁免；仅报告不阻塞既有开发流程过严。
- **补测范围**：优先核心纯逻辑（`buffer` / `search` / `config` / `session` / `registries` / `diagnostics` / `trust` / `workspace`）。

---

## 一、单元测试行覆盖率基础设施

### 1.1 依赖

`pyproject.toml` `[project.optional-dependencies].dev` 增加：

```toml
dev = ["pyright>=1.1.400", "pytest>=8.0", "pytest-cov>=5.0"]
```

### 1.2 覆盖率配置（`[tool.pytest.ini_options]` + `[tool.coverage]`）

在 `pyproject.toml` 增加 coverage 配置（避免新增 `.coveragerc` 文件——与仓库「整洁根目录」一致）：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --cov=yate --cov-report=term-missing --cov-report=html --cov-branch --cov-fail-under=60"

[tool.coverage.run]
source = ["yate"]
branch = true
# 豁免：L4 外壳入口 / 渲染层（Textual widget 需 pilot 驱动，属冒烟域）/ 可选后端
omit = [
    "yate/app.py",
    "yate/cli.py",
    "yate/__main__.py",
    "yate/editor_view/editor.py",
    "yate/editor_view/palette.py",
    "yate/editor_view/completion.py",
    "yate/editor_view/terminal.py",
    "yate/editor_core/buffer_syntax_leaf.py",  # 若存在；按实际核对
]

[tool.coverage.report]
show_missing = true
skip_covered = true
# 报告阈值单独放这里，与 addopts 的 fail-under 保持一致并便于集中管理
fail_under = 60
```

**说明**：
- `--cov-fail-under=60` 是硬门槛（跑 `pytest` 时低于 60% 即 exit 1）。豁免项去掉后实际比例应高于门槛。
- HTML 报告输出到 `htmlcov/`（已确认在 `.gitignore` 中，无需改）。
- 分支覆盖用 `--cov-branch`（branch=true），更能暴露未测分支，符合审查目标。

### 1.3 门槛校对

初版先以豁免后的整体 ≥60% 为目标。实施首步先跑一次带 `--cov=yate` 实测，**依据真实数字调整 omit 清单与 fail_under**，不回填账面数字、不误导。

### 1.4 CI/文档

若仓库有 CI 配置（`.github/workflows/` 或等价），追加一条 `pytest --cov` 步骤；无则跳过并在 plan 实施时确认。

---

## 二、优先补核心纯逻辑单元测试

对照现有覆盖现状（`test_editor_core.py`(42) / `test_config.py`(70) / `test_diagnostics.py`(11) / `test_trust.py`(4) / `test_workspace_filter.py`(23) / `test_fonts.py`(5) / `test_crash.py`(12) / `test_syntax_engine.py`(9) …），缺口集中在以下高价值纯逻辑，按顺序补：

### 2.1 `yate/editor_core/buffer.py`（TextBuffer 核心）— 优先
现有 `test_editor_core.py` 已覆盖基础，补：
- 垂直移动 `_goal_col` 期望列穿越短行 / 水平移动 / 编辑 / undo 清除（本批已有部分，补全分支）。
- `word_end`/`word_start` 空行、纯空白行、末尾标点边界。
- outdent/indent logout：整 Tab 剥离、空格对齐 tab stop、空选区。
- undo 栈 `MAX_UNDO_STEPS` 淘汰、合并打字 weight、`_restore` 边界。

### 2.2 `yate/editor_core/search.py`（SearchEngine）
- `replace_all` 光标钳制（`min(c, len(line))`）、替换后 anchor 清理。
- 空 pattern、跨行搜索、大小写敏感/不敏感切换、`replace_current`。
- 加回退出/无匹配时的光标与查询保留。

### 2.3 `yate/config.py`（YateConfig 校验）
现有 70 用例较全，补边界：`tab_width` 边界(1/16/bool)、错误收集不崩溃、env 覆盖优先级、`yaterc` 缺失回退、EXEC 异常隔离。

### 2.4 `yate/editor_core/session.py` 与 `yate/registries.py`
- `EditorSession`：标签增删、doc 生命周期、`on_closed` 回调派发。
- `ActionRegistry` / `CommandRegistry`：注册、重名覆盖、缺失查找、`register(..., allow_override)` 语义。

### 2.5 `yate/diagnostics.py` + `yate/services/trust.py` + `yate/services/workspace.py`
- diagnostics：空/隔离边界、行映射。
- trust：清单读写、注释/# 注释、灵避路径解析（已在 `test_trust.py`，补缺失行覆盖如 `is_trusted` 对未添加路径、删除行撤销）。
- workspace：`walk_files` 排序语义（目录优先/name.lower）、符号链接跳过、过滤大小写、深目录迭代（若改迭代）。

> 新增用例统一放 `tests/test_*.py`，遵守「naming `test_<behavior>_<condition>_<expected>` + docstring + `from __future__ import annotations`」，pyright strict 零诊断。

---

## 三、冒烟测试补充 + 命令覆盖保留

### 3.1 保留 `track_coverage`（命令/action 使用率）
不动其语义——它属于「场景覆盖面」，与行覆盖互补。仅在计划里明确两者区别，避免混淆。

### 3.2 补冒烟场景（按审查项覆盖缺口）
`tools/smoke_test/scenarios/` 下已有 `edit.py`(undo_redo/replace)、`search.py`(replace_single_all)、`files.py`、`explorer.py`、`regression.py` 等。补：
- **`workspace_trust`**（新场景，tag `files`/`extensions`）：未信任工作区启动 → 跳过 `./extensions` 且消息栏提示 → `:trust` → 扩展加载。复用已有 trust 语义。
- **`undo_redo_goal_col`**：垂直移动期望列 + undo 结合（覆盖本次 buffer 改动冒烟往返）。
- **`replace_all_clamp`**：`replace_all` 后光标钳制（若已有 `replace_single_all` 则补 `replace_all` 变体）。
- 场景定义走现有 `_base.py`/注册模式，补进对应 `scenarios/*.py` 的 `SCENARIOS` 表。

### 3.3 冒烟门槛
冒烟退出码不变；`--coverage` 仍为可选报告。**不**给冒烟加覆盖门槛（命令覆盖率低不代表代码没测，避免误拦）。

---

## 四、实施步骤

1. **实测基线**：跑 `python -m pytest tests/ -q --cov=yate --cov-branch --cov-report=term-missing`，记录各模块行/分支覆盖，产出真实缺口清单，据此定 omit 与 fail_under。
2. **搭基础设施**：改 `pyproject.toml`（dev 依赖 + `[tool.pytest.ini_options]` + `[tool.coverage.*]`）；安装 `pytest-cov`。
3. **补 2.1–2.4 核心纯逻辑测试**（buffer/search/config/session/registries），逐模块跑通。
4. **补 3.2 冒烟场景**，跑 `python -m tools.smoke_test run` 验证。
5. **按真实数据校准**：调整 omit/阈值至诚实 ≥60%；确认 `.gitignore` 已忽略 `htmlcov/` 与 `.coverage`。
6. **CI**：如有 workflow 追加 `pytest --cov` 步骤。

---

## 五、验证

- `python -m pyright yate/ tests/ tools/` → 0 诊断。
- `python -m pytest tests/ -q` → 全绿，且 coverage ≥ 门槛（exit 0）。
- `python -m tools.smoke_test run` → 场景全过，`--coverage` 输出命令/action 覆盖正常。
- `python -m tools.smoke_test run --tag files` 等新场景单独验证。
- 确认 `htmlcov/` 输出存在、`git status` 不含脏覆盖率产物。

---

## 六、范围与不做什么

- **不做**：改现有 `track_coverage` 语义；给冒烟加覆盖门槛；本轮不修 issue（调研中发现的新问题仅记录到 `review.md`）。
- **渲染层豁免已申明**：`app.py`/`cli.py`/`editor_view/editor.py` 等 Textual 渲染/外壳走冒烟域（pilot 驱动），不强制行覆盖，避免表单造假。
- 阈值与豁免以**真实首次测量**为准，宁可临时放宽并记录，不粉饰数字。