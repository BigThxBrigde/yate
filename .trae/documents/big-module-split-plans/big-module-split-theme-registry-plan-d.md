# 波次 d：theme → themes + cells + theme_files（issue IKK5F7）

## 目标

`yate/editor_view/theme.py`（805 行）拆为"广播枢纽 + 门面"与三个独立模块：

- 新增 `yate/editor_view/themes.py`（~500 行）：`Theme` 类（53–126）；
  Catppuccin/One/Gruvbox 全部工厂与色表（129–383）；`THEMES` /
  `DEFAULT_THEME`（374–385）；`available()`（484–486）；`register_theme()`
  （489–503）；`TEXTUAL_THEME_PREFIX` / `textual_theme_name` /
  `_MAPPED_COLOR_FIELDS` / `_OPAQUE_FIELDS` / `_DOC_HIT_RE` /
  `validate_theme` / `to_textual_theme`（506–657）。
- 新增 `yate/editor_view/cells.py`（~80 行）：`cell_width`…`expand_char`
  全部 6 个字符几何函数（732–805）；仅依赖 `unicodedata`，零项目内依赖。
- 新增 `yate/editor_view/theme_files.py`（~75 行）：
  `_loaded_theme_files` / `_theme_namespace` / `load_theme_file` /
  `load_theme_paths`（660–729）；依赖 `from .themes import Theme,
  register_theme`。
- `theme.py` 瘦身（~140 行）：保留广播机制 `_active` / `active()` /
  `set_theme()` / `ThemeListener` / `Unsubscribe` / `_listeners` /
  `subscribe()` / `_notify()` / `attach()` / `detach()`（387–481）；
  头部再导出 `themes` / `cells` / `theme_files` 的全部公共符号作门面。

## 关键不变量

1. **门面策略**：40+ 处 `from . import theme` / `from yate.editor_view import
   theme` / 文档示例 `from yate.editor_view.theme import THEMES` 一行不改。
2. `_active` 全局与 `set_theme` 留在 theme.py——"当前主题"单一真源；
   `register_theme`（themes.py）不触碰 `_active`。
3. import 方向（无环）：`cells`（零依赖）←；`themes →
   editor_syntax.tokens`（既有）；`theme_files → themes`；
   `theme → themes, cells, theme_files`；外部 → theme（门面）。

## 架构守卫

- 不新增对外 `editor_view` 导入面，`UI_FROZEN_FILES` 不动；
- 行数守卫豁免集合移除 `editor_view/theme.py`。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/
.venv\Scripts\python.exe -m pytest tests/test_theme_palettes.py tests/test_config.py -q
.venv\Scripts\python.exe -c "from yate.editor_view.theme import THEMES, active, set_theme, cell_len; print(len(THEMES))"
```

## 预估

`themes.py` ~500；`cells.py` ~80；`theme_files.py` ~75；`theme.py` ~140。
