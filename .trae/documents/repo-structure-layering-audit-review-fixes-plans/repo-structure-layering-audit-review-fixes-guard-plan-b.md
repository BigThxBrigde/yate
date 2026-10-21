# 子计划 b —— 层秩向上连线守卫（Fix-D / Fix-C4 守卫面）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)（v3）
- 波次：wave-2（**必须在 plan-f 之后**）｜独占文件：`tests/test_architecture.py`（**只改这一个文件**）
- 前置依赖：plan-f（记法切分）已落地；否则 `keyproto/legacy.py → keymaps/base` 仍是向上连线，本用例会红

## 一、目标

把规则 §一 的层秩声明变成**可执行守卫**：新增用例 `test_no_unregistered_upward_imports`
（第 32 个用例），断言全仓 `yate/` 的向上连线条目 ⊆ 已登记白名单（切分后**仅 statusbar 2 条**）；
白名单外的向上连线即失败，失败信息指引到规则登记位置。顺带落 S-8 守卫侧
（`UI_FREE_FILES` 补 `dist_meta.py`）。

## 二、逐处改动

### 改动 1 —— `UI_FREE_FILES` 增补（约 `:138`）

现状：

```python
UI_FREE_FILES: tuple[str, ...] = (
    "session.py",
    "registries.py",
    "config.py",
    "yaterc.py",
    "yaterc_options.py",
)
```

目标：

```python
UI_FREE_FILES: tuple[str, ...] = (
    "session.py",
    "registries.py",
    "config.py",
    "yaterc.py",
    "yaterc_options.py",
    "dist_meta.py",
)
```

并在该常量上方注释追加两行（英文，misc-rules §四）：

```
#: ``dist_meta.py`` joined in the 2026-10-17 structure audit: stdlib-only dist
#: metadata parsing shared by ``diagnostics.py`` (runtime) and ``pack/`` (build).
```

### 改动 2 —— 层秩表与白名单常量（紧随 `ALLOWED_PROTOCOLS` 之后插入）

```python
#: Layer rank of every ``yate/`` module, mirroring the inventory in
#: architecture-boundaries.md section 1.  ``keymaps`` is split per file: the
#: key notation leaf ``keys.py`` is L0 (no upward dependency), every other
#: keymap module is L1.  Prefixes are matched in order, so the ``keys.py``
#: entry must precede the ``keymaps/`` default; anything unlisted ranks as L0,
#: which makes a new leaf module reaching upward fail the guard.
_LAYER_RANKS: tuple[tuple[str, int], ...] = (
    ("app.py", 4),
    ("cli.py", 4),
    ("__main__.py", 4),
    ("editor.py", 3),
    ("actions.py", 3),
    ("commands.py", 3),
    ("diagnostics.py", 3),
    ("flows/", 3),
    ("services/extensions/", 3),
    ("editor_view/", 2),
    ("session.py", 1),
    ("registries.py", 1),
    ("keymaps/keys.py", 0),
    ("keymaps/", 1),
)

#: Upward import edges registered in the rule text (2026-10-17 structure
#: audit, rules section 1 / R14).  After the keymaps split these are the only
#: ones left: L2 ``statusbar.py`` reads the L3 extension facade plus the
#: R14-frozen ``bridges`` type to paint extension segments (constructor
#: injected, ``statusbar.py:83-84``).
UPWARD_EDGES_FROZEN: frozenset[str] = frozenset({
    "editor_view/statusbar.py -> yate.services.extensions",
    "editor_view/statusbar.py -> yate.services.extensions.bridges",
})
```

### 改动 3 —— 辅助函数（放在既有 `_yate_imports` 之后）

```python
def _layer_rank(rel: str) -> int:
    """Rank a ``yate/``-relative path; unlisted modules default to L0."""
    for prefix, rank in _LAYER_RANKS:
        if rel.startswith(prefix):
            return rank
    return 0


def _ranked_target(module: str) -> str | None:
    """Resolve a ``yate.x.y`` import to its ``yate/``-relative file path."""
    parts = module.split(".")[1:]
    while parts:
        rel = "/".join(parts)
        if (YATE / f"{rel}.py").is_file():
            return f"{rel}.py"
        if (YATE / rel / "__init__.py").is_file():
            return f"{rel}/__init__.py"
        parts.pop()
    return None
```

### 改动 4 —— 新增用例（放在 `test_keymaps_services_and_models_stay_ui_free` 附近）

```python
def test_no_unregistered_upward_imports() -> None:
    """Every upward import edge is registered in the rule text (2026-10-17).

    ``architecture-boundaries.md`` section 1 declares a layer for every
    ``yate/`` module; this guard makes that declaration executable: an import
    pointing at a *higher* layer must be listed in ``UPWARD_EDGES_FROZEN``,
    which mirrors the exceptions registered in the rule.  Unlisted modules
    rank as L0.  ``yate/extensions/`` (the shipped plugin examples) sits
    outside the L0-L4 stack and is skipped here -- its facade discipline is
    guarded by R14 (``test_extension_machinery_hides_behind_facade``).
    """
    offenders: list[str] = []
    for path in _yate_files():
        source = path.relative_to(YATE).as_posix()
        if source.startswith("extensions/"):
            continue
        source_rank = _layer_rank(source)
        for module in _yate_imports(path):
            target = _ranked_target(module)
            if target is None or target == source:
                continue
            if _layer_rank(target) > source_rank:
                offenders.append(f"{source} -> {module}")
    unregistered = sorted(set(offenders) - UPWARD_EDGES_FROZEN)
    assert not unregistered, (
        "unregistered upward import(s): "
        f"{unregistered}; register them in architecture-boundaries.md "
        "section 1 / R14, then extend UPWARD_EDGES_FROZEN"
    )
```

### 改动 5 —— 既有用例措辞同步（**不重命名用例**）

`test_leaf_package_reexports_carry_exception_note` 的函数名与 `leaf_packages` 变量名保持不变
（避免 §六 对照表编号漂移），仅：docstring 的 "leaf package" 表述改为 "re-exporting package"，
并在 `leaf_packages` 注释补一句："``keymaps`` is L1 since the 2026-10-17 split (its
``keys.py`` is the L0 leaf); its re-export exception note is still required."

## 三、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q          # 期望 32 passed
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/                   # 期望 0/0/0
(Select-String -Path tests\test_architecture.py -Pattern '^def test_').Count   # 期望 32
```

## 四、负向演练（硬性，演练后必须还原）

1. 把 `yate/keyproto/legacy.py` 的 `from yate.keymaps.keys import SPECIAL_KEYS` 临时改回
   `from yate.keymaps.base import SPECIAL_KEYS`（模拟切分回退）；
2. 跑 `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k upward` →
   **必须失败**，失败信息含 `keyproto/legacy.py -> yate.keymaps.base` 与登记指引；
3. 还原该行，复跑架构用例 → 32 passed；`git status --short` 中 `yate/keyproto/legacy.py` 无 diff；
4. 两次输出（含退出码）如实写入报告。

## 五、风险与回滚

- 白名单与层秩表必须与 plan-a 登记语句/总纲 §三 逐字一致；不一致即阻塞回报；
- 若出现白名单外命中：**不得**放宽表或私自扩白名单，停止并回报实测命中项；
- 回滚：`git revert <本步提交 sha>`（演练临时改动不入库）。
