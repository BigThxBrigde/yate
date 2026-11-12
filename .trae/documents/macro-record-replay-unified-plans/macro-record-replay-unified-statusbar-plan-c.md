# 子计划 c：L2 状态栏录制指示（wave-1）

> 唯一规范来源：`overview.md` §1.7 + 主计划 `../macro-record-replay-unified-plan.md`
> §5.5(6) / AC5；本文件自包含。状态：待批准。

## 0. 输入 / 上游依赖 / 输出

- 输入：主计划取证 F15（`statusbar.py` 注入面 + `refresh_status` fingerprint 短路）、
  F10（`_build_widgets` 构造 StatusBar）、R13/R14。
- 上游依赖：**无**（plan-c 用可变的假 `recording_label` 回调即可单测，不依赖
  `MacroState` 落盘；与 plan-a / plan-b 并行）。
- 输出：状态栏可注入「录制指示」回调，`rec @a` 出现在 mode chip 旁、停止后消失，
  且状态变化必定触发重绘。

## 1. 独占文件清单（只改这些）

- `yate/editor_components/statusbar.py`
- `tests/test_macro_statusbar.py`（新增）

> 不改 `yate/editor_compose.py`（注入接线归 plan-f）、`tests/test_architecture.py`。
> 产品源码 `yate/**` 归属依据见 `overview.md` §2。

## 2. 具体修改（文件:行号）

### 2.1 `yate/editor_components/statusbar.py`

- `StatusBar.__init__` 现有构造参数区（**第 88-91 行** `extension_segments` /
  `loaded_extensions`），在 `id` 之前追加**带缺省值**的关键字参数：

```python
recording_label: Callable[[], str | None] | None = None,
```

  并在实例属性保存区（**第 99-102 行** 附近）追加
  `self.recording_label = recording_label`，附 `#:` 风格或行内注释说明「pull model:
  returns ``rec @<reg>`` or ``None``」。缺省 `None` 保证既有独立构造（测试 /
  `StatusBar(...)` 直构）零破坏。`Callable` 已在第 17 行从
  `collections.abc` 导入，不新增 import。

- `refresh_status()`（**第 122-193 行**）：
  1. 在 `mode, chip_bg = mode_chip(...)`（**第 132 行**）之后计算
     `rec_text = self.recording_label() if self.recording_label is not None else None`，
     并用 `try/except Exception` 按既有 `_extension_texts`（第 250-254 行）的
     「provider 抛异常降级为省略 + `log.exception`」语义处理（禁止静默吞异常，
     `python-coding-style.md` §4.5，捕获附 `# noqa: BLE001` 注释说明）。
  2. 把 `rec_text` **加入 fingerprint 元组**（**第 173-190 行**，例如追加为
     元组最后一个元素）。理由：F15 第 191-193 行 `if fingerprint ==
     self._last_fingerprint: return`，若不加，录制开始 / 停止时其余状态不变 →
     短路 → 指示不刷新（AC5 失败）。
  3. 在 `text.append(chip, style=...)`（**第 197 行**）之后追加渲染：
     `text.append(f" {rec_text} ", style=f"bold {t.on_accent} {bar}")`（`rec_text`
     非 None 时）。
  4. `name_budget`（**第 200-202 行**）扣减新增文本宽度：
     `rec_cells = theme.cell_len(rec_text) + 2 if rec_text else 0`，把 `- rec_cells`
     加进 `budget - chip_len - 3 - dot_cells - lock_cells - left_ext_len` 表达式，
     避免文件名区溢出。
- **不改**：`mode_chip`（第 46-74 行）、`_lsp_segment`（第 266 行）、
  `_extension_texts`（第 238-254 行）、`on_mount`（第 113 行）、主题自持逻辑、
  任何 `.styles.*` 之外的 L3 调用。L2 **不得 import 任何 L3 名字**（R13/R14）。

### 2.2 `tests/test_macro_statusbar.py`（新增）

复用项目既有 statusbar 测试 fixture（构造 `StatusBar` 所需 `session` / `lsp` /
`keymaps` / `prompt` 的现成 fixture，见 `tests/conftest.py` 或既有 statusbar 测试），
不得自建完整 App。渲染结果通过 `str(statusbar.render())` 断言（若既有测试用别的
读取方式，执行者按既有惯例取，须在报告注明）。用例见 §3。

## 3. 详细测试用例（`tests/test_macro_statusbar.py`）

| 用例名 | 前置 / fixture | arrange / act | 断言（具体值） |
|---|---|---|---|
| `test_statusbar_shows_recording_label_when_provider_returns_text` | statusbar fixture；provider 为返回 `"rec @a"` 的 lambda | 构造后调 `refresh_status()` | `str(statusbar.render())` 含子串 `"rec @a"`；且含既有 mode chip 文本（`"VSC"` 或 `"NORMAL"`，按 fixture keymap 取其一） |
| `test_statusbar_hides_recording_label_when_provider_returns_none` | 同上；provider 返回 `None` | 调 `refresh_status()` | 渲染文本**不含** `"rec @"`；其余状态栏文本（位置 / 文件名）与未注入时一致 |
| `test_statusbar_repaints_when_recording_label_changes`（fingerprint 关键） | 可变容器 `box = {"v": "rec @a"}`；provider `lambda: box["v"]` | 第一次 refresh → `box["v"] = "rec @b"` → 第二次 refresh | 第一次含 `"rec @a"` 不含 `"rec @b"`；第二次含 `"rec @b"` 且不含 `"rec @a"`（证明 label 入 fingerprint，否则短路不重绘） |
| `test_statusbar_standalone_construction_without_provider`（边界 / 兼容） | 按既有方式构造 StatusBar，**不传** `recording_label` | 调 `refresh_status()` | 不抛异常；渲染不含 `"rec @"`；`statusbar.recording_label is None` |
| `test_statusbar_raising_provider_degrades_gracefully`（异常流） | provider 抛 `RuntimeError("boom")` | 调 `refresh_status()` | 不抛异常；渲染不含 `"rec @"`；`caplog` 含 `"status ... provider failed"` 级别 log（对齐第 254 行既有降级）；fingerprint 不因异常残留 |
| `test_statusbar_recording_indicator_counts_into_name_budget`（边界） | 极窄 `size.width`（如 40） + provider 返回很长 label | `refresh_status()` | 渲染文本总单元格宽度 ≤ width；文件名按既有 `truncate_to_cells` 逻辑被截断或省略，不出现溢出 |

## 4. 验证方案

- **验证目标**：证明 AC5「录制态有状态栏指示、停止后指示消失」在 L2 自持实现，
  且 R13（L3 只注入纯数据 / 回调、不直改样式）成立、fingerprint 短路不吞掉指示。
- **需一并回归的既有测试**：`pytest tests/ -k "statusbar or status_bar" -q`；
  `tests/test_architecture.py::test_editor_components_does_not_import_upward`、
  `test_editor_does_not_paint_widget_styles`、`test_comments_and_docstrings_stay_ascii`。
- **通过判定标准**：pyright 退出码 0 零诊断；pytest 退出码 0、断言全绿；架构守卫
  无违规（L2 不 import L3）。
- **无法自动化部分**：真实终端下 `rec @a` 的视觉位置 / 颜色需人工验证：启动编辑器、
  开始录制，肉眼确认 mode chip 右侧出现 `rec @a`、停止后消失；记录在 wave-5 复核。
  本子计划只做 widget 渲染断言。

## 5. 可执行验收命令

```
.venv\Scripts\python.exe -m pyright yate/editor_components/statusbar.py
.venv\Scripts\python.exe -m pytest tests/test_macro_statusbar.py -q
.venv\Scripts\python.exe -m pytest tests/ -q -k "statusbar or status_bar"
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k "import_upward or paint_widget_styles or ascii"
```

## 6. 架构边界与守卫

- 触碰层级：仅 L2（`editor_components/statusbar.py`，`_LAYER_RANKS` 第 153 行）。
- R 条款：R3（不 import `yate.editor` / `yate.app`）、R13（组件自持、只接
  `Callable`）、R14（L2→L3 零向上连线，`UPWARD_EDGES_FROZEN` 保持空集）、
  T2（`test_editor_does_not_paint_widget_styles` 不误伤，本计划改的是组件自身）。
- 守卫用例：`tests/test_architecture.py::test_editor_components_does_not_import_upward`、
  `test_no_unregistered_upward_imports`、`test_editor_does_not_paint_widget_styles`
  （**只跑不改**；新增守卫归 plan-d）。

## 7. 风险与回滚路径

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 漏把 label 加入 fingerprint → 指示不刷新（AC5 失败） | §2.1(2) 明确 + 专门用例 `test_statusbar_repaints_when_recording_label_changes` | `git checkout -- yate/editor_components/statusbar.py tests/test_macro_statusbar.py` |
| 新增参数破坏既有独立构造 | 缺省 `None` + 兼容用例 | 同上 |
| provider 异常静默吞掉 / 无日志 | `try/except` + `log.exception` + `# noqa: BLE001` 注释 + 异常流用例 | 同上 |
| 为拿状态而 import L3 名字破坏 R13/R14 | 只接 `Callable`；跑 R3 / 层秩守卫 | 同上 |
| 指示占宽导致文件名区溢出 | `name_budget` 扣减 + 极窄宽度用例 | 同上 |
