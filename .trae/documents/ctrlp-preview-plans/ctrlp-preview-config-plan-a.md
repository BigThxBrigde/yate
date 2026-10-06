# plan-a：`file_preview` 配置层（L0）

> 总纲见 `overview.md`。前置依赖：无（首波）。

## 一、目标

yaterc 新增 `file_preview` 字典项并提供 `FilePreviewConfig` 类型：
解析、校验、默认值、错误上报全部落位，测试钉死语义。本波**不触碰任何 UI**。

## 二、独占文件清单

- `yate/config.py`（改）
- `tests/test_config.py`（改）

## 三、逐文件改动明细

### `yate/config.py`

1. **模块 docstring**：yaterc 示例代码块中 `screen_saver` 段之后补
   `file_preview` 段（与 §四 默认值一致，注释说明各键含义）。
2. **新增 frozen dataclass**（紧随 `ScreenSaverConfig` 之后）：

   ```python
   @dataclass(frozen=True)
   class FilePreviewConfig:
       """Resolved ``file_preview`` dict option (ctrl+p preview pane)."""

       enable: bool = True
       position: str = "right"     # "right" | "left"
       size: int = 40              # percent of palette width, 10-80
       max_lines: int = 2000       # read/tokenize line cap
       max_size: int = 1048576     # byte cap before refusing to read
   ```

3. **`YateConfig` 增字段**（`screen_saver` 字段之后）：

   ```python
   #: Ctrl+p preview pane settings (the ``file_preview`` dict option).
   file_preview: FilePreviewConfig = field(default_factory=FilePreviewConfig)
   ```

4. **新增 `_extract_file_preview(namespace, config)`**，骨架对齐
   `_extract_screen_saver`（config.py:446-561）：
   - `raw is None` → 直接返回（未声明保持默认）；
   - 非 `dict` → `config.errors.append(f"file_preview must be a dict, got {raw!r}")` 整包拒收；
   - known keys = `("enable", "position", "size", "max_lines", "max_size")`，
     unknown 报 `file_preview has unknown keys: [...]`（排序）；
   - `enable`：仅 `bool` 接受，否则报错回退 `True`；
   - `position`：仅 `str` 且 ∈ `("right", "left")`，否则报错回退 `"right"`；
   - `size`：`int` 且非 `bool` 且 `10 <= v <= 80`，否则报错回退 40；
   - `max_lines`：`int` 且非 `bool` 且 `1 <= v <= 100_000`，否则回退 2000；
   - `max_size`：`int` 且非 `bool` 且 `1024 <= v <= 16_777_216`，否则回退 `1_048_576`；
   - 全部通过后 `config.file_preview = FilePreviewConfig(...)` **整字典替换**
     （与 `screen_saver` 的 "later valid declaration wins" 语义一致）；
   - docstring 散文式（PEP 257 项目风格：无 `:param:` 区块），写明
     "缺省键保持默认；坏键单独报错回退；后一次合法声明整体替换"。
5. **挂接**：`_extract_options()`（config.py:564）末尾调用
   `_extract_file_preview(namespace, config)`。

### `tests/test_config.py`

新增用例组（紧随 screen_saver 组之后，复用 `_load` helper，注释分隔线
`# --- file_preview option ---`）：

| 用例 | 断言 |
|---|---|
| `test_file_preview_defaults` | `cfg.YateConfig().file_preview` 五字段等于 `FilePreviewConfig()` 默认 |
| `test_file_preview_absent_keeps_defaults` | rc 无声明 → `== cfg.FilePreviewConfig()` |
| `test_file_preview_full_valid_dict` | 五键全给合法值 → 逐字段生效 |
| `test_file_preview_partial_dict_keeps_defaults` | 只给 `{"size": 60}` → size=60，其余默认 |
| `test_file_preview_unknown_key_reported` | `{"width": 50}` → errors 含 "unknown keys"，其余字段默认 |
| `test_file_preview_not_a_dict_reported` | `file_preview = True` → errors 含 "must be a dict"，配置回默认 |
| `test_file_preview_bad_position_rejected` | `{"position": "up"}` → 报错，position 回 "right" |
| `test_file_preview_bad_size_rejected` | `{"size": True}` / `{"size": 5}` / `{"size": 90}` → 报错回退 40（bool 冒充 int 被甄别） |
| `test_file_preview_bad_limits_rejected` | `max_lines=0`、`max_size=1` 各报错回退 |
| `test_file_preview_later_declaration_replaces` | 两个 rc 依次声明 → 第二个合法声明整体生效 |

## 四、架构边界自检

- R4：`config.py` 无新 import，不触 `editor_view` ✓
- §三.6（能用函数不造类）：解析为模块级函数，dataclass 只承载数据 ✓
- python-coding-style §2.5：dataclass 有 docstring；§1.4：错误消息 f-string
  （非日志调用，允许）✓
- 类型注解完整，pyright strict 零诊断 ✓

## 五、验收命令（worktree 内）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -q
.venv\Scripts\python.exe -m pyright yate/config.py tests/test_config.py
```

预期：pytest 全绿（既有用例不回归），pyright 零诊断。

## 六、回滚

独立提交 `feat(config): add file_preview dict option`；`git revert` 即净回退，
无跨波耦合。
