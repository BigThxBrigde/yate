# 子计划 b —— 层秩向上连线守卫（Fix-D / Fix-C4 守卫面）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 波次：wave-1｜独占文件：`tests/test_architecture.py`（**只改这一个文件**）
- 前置依赖：无（与 plan-a 并行；白名单逐字契约见总纲 §三.1——两边以总纲为准）

## 一、目标

把规则 §一 的层秩声明变成**可执行守卫**：新增用例 `test_no_unregistered_upward_imports`
（第 32 个用例），断言全仓 `yate/` 的向上连线条目 ⊆ 已登记白名单；白名单外的向上连线即失败，
失败信息指引到规则登记位置。

- 覆盖：审计 S-1（`keymaps/base.py -> yate.session`）、S-2（`editor_view/statusbar.py` → L3 门面）；
- 顺带落 S-8 的守卫侧：`UI_FREE_FILES` 补 `dist_meta.py`。

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
并在该常量上方注释追加一行（英文，misc-rules §四）：
```
#: ``dist_meta.py`` joined in the 2026-10-17 structure audit: stdlib-only dist
#: metadata parsing shared by ``diagnostics.py`` (runtime) and ``pack/`` (build).
```

### 改动 2 —— 新增层秩表与白名单常量

插入位置：紧随 `ALLOWED_PROTOCOLS` 之后（与其它"冻结白名单"常量同区）。逐字插入：

```python
#: Layer rank of every ``yate/`` module, mirroring the inventory in
#: architecture-boundaries.md section 1 (``keymaps`` is split per file: the
#: key contract in ``base|vim|vsc`` is L0, ``registry.py`` / the re-exporting
#: package root are L1).  Prefixes are matched in order; anything unlisted
#: ranks as L0, so a new leaf module reaching upward fails the guard.
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
    ("keymaps/__init__.py", 1),
    ("keymaps/registry.py", 1),
)

#: Upward import edges registered in the rule text (2026-10-17 structure
#: audit, rules section 1 / R14): the L0 key contract ``keymaps/base.py``
#: holds an L1 ``ActionContext`` (``session``), and L2 ``statusbar.py`` reads
#: the L3 extension facade plus the R14-frozen ``bridges`` type to paint
#: extension segments (constructor-injected, ``statusbar.py:83-84``).
UPWARD_EDGES_FROZEN: frozenset[str] = frozenset({
    "keymaps/base.py -> yate.session",
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

`test_leaf_package_reexports_carry_exception_note` 的函数名与 `leaf_packages` 变量名**保持不变**
（避免 §六 对照表编号漂移），仅：

- docstring 中"leaf package"表述改为"re-exporting package"；
- `leaf_packages` 变量上方注释补一句："``keymaps`` additionally sits on the L0/L1 boundary
  (see rules section 1); its re-export exception note is still required."

## 三、验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q          # 期望 32 passed
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/                   # 期望 0 errors, 0 warnings, 0 informations
(Select-String -Path tests\test_architecture.py -Pattern '^def test_').Count   # 期望 32
```

## 四、负向演练（硬性，演练后必须还原）

1. 在 `yate/keymaps/vsc.py` 顶部临时加一行 `import yate.session`；
2. 跑 `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k upward` →
   **必须失败**，失败信息含 `keymaps/vsc.py -> yate.session` 与"register them in …"指引；
3. 还原该行，复跑全量架构用例 → 32 passed；`git status --short` 中 `yate/keymaps/vsc.py` 无 diff；
4. 把两次输出（含退出码）如实写入报告，供主计划 §七 回填。

## 五、风险与回滚

- 白名单必须与 plan-a 登记语句**逐字一致**（总纲 §三.1）；不一致即阻塞，回报主代理；
- 若守卫在既有代码上出现白名单外命中：**不得**放宽表或新增白名单，须停止并回报（说明实测命中项），
  由主代理按"登记 + 冻结"流程处置；
- 回滚：`git revert <本步提交 sha>`（演练临时改动不入库）。
