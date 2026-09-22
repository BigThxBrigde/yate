# Refinement Plan: Eliminate `Any` in `yate/interfaces.py`

> **实施状态（2026-09-22 核对）：✅ 已实现。**
>
> `yate/interfaces.py::AppProtocol` 的成员已全部精化为具体类型
> （`workspace: Workspace`、`keymaps: dict[str, Keymap]`、`config: YateConfig`、
> `panes: Optional[PaneManager]`、`run_shell_command(...) -> ShellResult` …）；
> `TYPE_CHECKING` + 字符串前向引用块也已按 §2–§3 落地。
> 仅剩 Textual 泛型参数的 `Any`（`Screen[Any]` / `WorkType[Any]` /
> `Callable[[Any], None]`），与 §1.1 的"keep Any"清单一致。
> §4 的附带修复（`completion.py::accept()` 行范围判定）同样已落地。
>
> 本文档 §1.1 的 `Any` 审计清单可作为"已完成工作"的核对表；§3 的导入验证
> 命令在当前实现下仍可照跑。

## 1. Background

The previous refactor (`b4a354f`) introduced `yate/interfaces.py` with an
`AppProtocol` to break the circular imports between `yate.app` and its
downstream modules.  To stay leaf-level, many protocol members were typed as
`Any` with a comment indicating the real type (e.g. `workspace: Any  # Workspace`).
This plan upgrades every `Any` to its concrete type where the import is safe,
and to a precise forward reference where it is not.

### 1.1 Full `Any` Audit (current state)

| # | Location                              | Current Type       | Target Type            | Safety     |
|---|---------------------------------------|--------------------|------------------------|------------|
| 1 | `workspace`                           | `Any`              | `Workspace`            | ✅ direct  |
| 2 | `keymaps: dict[str, ...]`             | `Any`              | `Keymap`               | ⚠️ forward |
| 3 | `actions`                             | `Any`              | `ActionRegistry`       | ⚠️ forward |
| 4 | `commands`                            | `Any`              | `CommandRegistry`      | ⚠️ forward |
| 5 | `extension_loader`                    | `Any`              | `ExtensionLoader`      | ⚠️ forward |
| 6 | `active_keymap` (property)            | `Any`              | `Keymap`               | ⚠️ forward |
| 7 | `config`                              | `Any`              | `YateConfig`           | ✅ direct  |
| 8 | `completion_popup`                    | `Optional[Any]`    | `Optional[CompletionPopup]` | ⚠️ forward |
| 9 | `prompt_bar`                          | `Optional[Any]`    | `Optional[PromptBar]`  | ⚠️ forward |
|10 | `panes`                               | `Optional[Any]`    | `Optional[PaneManager]`| ⚠️ forward |
|11 | `editor_view`                         | `Optional[Any]`    | `Optional[EditorView]` | ⚠️ forward |
|12 | `explorer_tree`                       | `Optional[Any]`    | `Optional[ExplorerTree]` | ⚠️ forward |
|13 | `terminal_panel`                      | `Optional[Any]`    | `Optional[TerminalPanel]` | ⚠️ forward |
|14 | `screen_stack` (property)             | `list[Any]`        | **Keep `list[Any]`**   | Textual    |
|15 | `screen` (property)                   | `Any`              | **Keep `Any`**         | Textual    |
|16 | `_terminal_factory`                   | `Optional[Callable[..., Any]]` | **Keep** | callback   |
|17 | `_open_document_path(..., target_leaf)` | `Optional[Any]`  | `Optional[Leaf]`       | ✅ direct  |
|18 | `try_window_prefix(event)`            | `Any`              | **Keep `Any`**         | Textual    |
|19 | `run_worker(work, ...) -> Any`        | `Any`              | **Keep `Any`**         | Textual    |
|20 | `_push_overlay(screen)`               | `Any`              | **Keep `Any`**         | Textual    |
|21 | `_split_with_path(axis, ...)`         | `Any`              | `Axis`                 | ✅ direct  |
|22 | `run_shell_command(...) -> Any`       | `Any`              | `ShellResult`          | ✅ direct  |

**Summary**:
- **5** direct-safe replacements (no import cycle, no TYPE_CHECKING needed)
- **9** forward-reference replacements (need TYPE_CHECKING block + string annotations)
- **8** intentionally kept as `Any` (Textual framework internals or opaque callbacks)

### 1.2 Why Some Imports Are Unsafe

```
interfaces.py  ←──  keymaps/base.py  (imports AppProtocol)
     ↑                                        ↑
     └──── would cause cycle if we import ────┘
              Keymap at runtime
```

Every module in the editor_view/app_features/services layers now imports
`AppProtocol` for type annotations.  If `interfaces.py` imports *them* at
runtime, Python hits the import cycle before either module can finish
initializing.  The fix is `TYPE_CHECKING`: the static analyzer sees the
import, but the runtime interpreter skips it.  Combined with
`from __future__ import annotations` (stringified annotations), the forward
reference is safe at runtime while still being precise for pyright.

**This is architecturally different from the old pattern:** the previous
`TYPE_CHECKING` blocks were used by *downstream* modules to import the
*composition root* (`yate.app.YateApp`) in the opposite direction of
dependency.  Here, `interfaces.py` uses `TYPE_CHECKING` only to name the
*actual concrete classes* that implement the protocol -- it does not
import anything that depends on it at runtime.  This is a legitimate
application of `TYPE_CHECKING`, not a workaround for a broken architecture.

---

## 2. Safe / Unsafe Import Verification

### 2.1 Direct-Safe Imports (zero internal dependencies)

| Target | Module | Internal Imports | Cycle Risk |
|--------|--------|-----------------|------------|
| `Workspace` | `yate.services.workspace` | `fnmatch, dataclasses, pathlib, typing` | None |
| `ShellResult` | `yate.services.shell` | `subprocess, sys, dataclasses, pathlib, typing` | None |
| `YateConfig` | `yate.config` | `dataclasses, pathlib, typing, yate.editor_view.theme` | theme only imports `editor_syntax.tokens` → None |
| `Axis` | `yate.editor_view.pane_types` | `dataclasses, typing, yate.editor_core.*` | None |
| `Leaf` | `yate.editor_view.pane_types` | same as above | None |

### 2.2 Forward-Only Imports (would cycle at runtime)

| Target | Module | Reverse Imports | Why Cycle |
|--------|--------|----------------|-----------|
| `Keymap` | `yate.keymaps.base` | `from yate.interfaces import AppProtocol` | direct |
| `ActionRegistry` | `yate.actions` | imports `keymaps.base.ActionContext` → keymaps.base imports interfaces | indirect |
| `CommandRegistry` | `yate.app_features.commands` | `from yate.interfaces import AppProtocol` | direct |
| `ExtensionLoader` | `yate.services.extensions` | `from yate.interfaces import AppProtocol` | direct |
| `CompletionPopup` | `yate.editor_view.completion` | `from yate.interfaces import AppProtocol` | direct |
| `PromptBar` | `yate.editor_view.commandline` | `from yate.interfaces import AppProtocol` | direct |
| `EditorView` | `yate.editor_view.editor` | `from yate.interfaces import AppProtocol` | direct |
| `ExplorerTree` | `yate.editor_view.explorer` | `from yate.interfaces import AppProtocol` | direct |
| `PaneManager` | `yate.editor_view.panes` | imports `editor` → editor imports interfaces | indirect |
| `TerminalPanel` | `yate.editor_view.terminal` | `from yate.interfaces import AppProtocol` | direct |

---

## 3. Implementation Steps

### Step 1: Add direct-safe imports to `interfaces.py`

```python
# New top-level imports (no cycle risk)
from yate.config import YateConfig
from yate.editor_view.pane_types import Axis, Leaf
from yate.services.shell import ShellResult
from yate.services.workspace import Workspace
```

Update the protocol members:

```python
workspace: Workspace
config: YateConfig
_split_with_path(self, axis: Axis, args: str) -> None: ...
_open_document_path(
    self, path: Path, *, target_leaf: Optional[Leaf] = None
) -> Optional[Document]: ...
run_shell_command(
    self, command: str, show_output: bool = True
) -> ShellResult: ...
```

### Step 2: Add TYPE_CHECKING block for forward-reference imports

```python
from typing import Any, Callable, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from yate.actions import ActionRegistry
    from yate.app_features.commands import CommandRegistry
    from yate.editor_view.commandline import PromptBar
    from yate.editor_view.completion import CompletionPopup
    from yate.editor_view.editor import EditorView
    from yate.editor_view.explorer import ExplorerTree
    from yate.editor_view.panes import PaneManager
    from yate.editor_view.terminal import TerminalPanel
    from yate.keymaps.base import Keymap
    from yate.services.extensions import ExtensionLoader
```

Update the protocol members (string annotations via `from __future__ import annotations`):

```python
keymaps: dict[str, Keymap]
actions: ActionRegistry
commands: CommandRegistry
extension_loader: ExtensionLoader

@property
def active_keymap(self) -> Keymap: ...

completion_popup: Optional[CompletionPopup]
prompt_bar: Optional[PromptBar]
panes: Optional[PaneManager]
editor_view: Optional[EditorView]
explorer_tree: Optional[ExplorerTree]
terminal_panel: Optional[TerminalPanel]
```

### Step 3: Remove all `# SomeType` comments from former `Any` members

After replacement, comments like `# yate.services.workspace.Workspace` are
redundant and should be removed.

### Step 4: Update module docstring

The docstring currently says:

> Types that live in packages that *do* import ``yate.app`` (e.g.
> ``Workspace``, ``Keymap``, ``PaneManager`` ...) are kept as ``Any`` or
> string forward refs so that ``interfaces.py`` stays leaf-level.

Update to reflect the new state — direct imports for leaf types,
`TYPE_CHECKING` + forward refs for cycles:

```python
"""...

This module uses two strategies for type precision:

1. **Direct top-level imports** for types that live in truly leaf-level
   packages (``Workspace``, ``YateConfig``, ``Axis``, ``Leaf``,
   ``ShellResult``).  These create no cycle.

2. **TYPE_CHECKING + string forward refs** for types whose module imports
   ``AppProtocol`` back (``Keymap``, ``ActionRegistry``, ``CommandRegistry``,
   all editor_view widgets).  The imports are resolved at static-analysis
   time only, so no runtime cycle occurs.

Textual framework internals (``screen``, ``run_worker``, ``_push_overlay``)
remain ``Any`` because their concrete types are defined in the third-party
library and are out of this project's control.
"""
```

### Step 5: Verify

```bash
python -c "from yate.interfaces import AppProtocol; print('interfaces OK')"
python -c "from yate.app import YateApp; print('YateApp OK')"
python -m pyright yate/ tests/    # expect 0 errors, 0 warnings
python -m pytest tests/ -q        # expect all pass
python -m yate --help             # expect normal CLI
```

---

## 4. Additional Minor Fix (from code review)

As a bonus, fix the ambiguous row-check in `completion.py::accept()`:

```python
# Before (semantically obscure — "row != r0 or row != r1" means
# "row is not simultaneously equal to both", which is always true when
# r0 != r1)
if row != r0 or row != r1:
    return

# After (semantically clear — "cursor left the completion row range")
if row < r0 or row > r1:
    return
```

Current completion items are single-line (`r0 == r1`) so both forms
behave identically in practice.  The new form expresses intent
unambiguously and handles the hypothetical multi-line case correctly.

---

## 5. Execution Order

```
Step 1: Direct-safe imports + protocol member updates
   ↓
Step 2: TYPE_CHECKING block + forward-reference protocol updates
   ↓
Step 3: Clean up redundant comments
   ↓
Step 4: Update module docstring
   ↓
Step 5: Minor — fix completion.py row-check
   ↓
Step 6: Full verification (pyright + pytest + CLI)
```

---

## 6. Practical Suggestions for Task Execution

1. **Do not add `runtime_checkable` to AppProtocol.**  `@runtime_checkable`
   would force `issubclass()` / `isinstance()` to evaluate every protocol
   member at runtime, pulling in the TYPE_CHECKING imports and triggering
   the cycle we carefully avoided.  pyright handles structural subtyping
   without runtime help.

2. **Keep `from __future__ import annotations` at the top of interfaces.py.**
   This is what makes the string forward references work without runtime
   evaluation.  Removing it would immediately cause ImportError.

3. **Verify the TYPE_CHECKING import block incrementally.**  After adding
   each import, run `python -c "from yate.app import YateApp"` to catch
   cycles early.  Some modules (e.g. `PaneManager`) are reached only
   indirectly through EditorView, making the cycle less obvious.

4. **Prefer one commit per logical step.**  Step 1-2 are independent of
   Step 5 (completion.py fix).  Splitting them keeps `git bisect` useful
   if a regression appears.

---

## 7. Potential Risks and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| A TYPE_CHECKING import actually cycles at runtime (missed a transitive import) | Medium | High | Verify with `python -c "from yate.app import YateApp"` after each batch of imports.  pyright does not detect runtime import cycles. |
| pyright strict flags `reportUnknownVariableType` on protocol members that used to be `Any` | Low | Low | `Any` suppresses this; the concrete types will also be inferable.  If it does flag, add explicit property annotations. |
| `TYPE_CHECKING` block grows too large and becomes hard to maintain | Low | Low | Group the imports alphabetically with section comments (e.g. `# editor_view widgets`, `# services`).  The current count (10) is manageable. |
| `Axis` / `Leaf` imported from `pane_types.py` conflicts with other `Axis` names in the codebase | Very Low | Low | No existing `Axis` name conflicts; check grep before finalizing. |
| The `completion.py` row-check change alters behavior for an undocumented multi-line completion case | Very Low | Low | Current LSP/prefix completion never produces multi-line ranges.  The change is strictly more correct. |

---

## 8. Feasible Extension Directions

1. **Generate a `yate.interfaces` type alias re-export module.**  Create
   `yate/interfaces/__init__.py` that re-exports `AppProtocol` plus all
   the concrete types now safe to import (`Workspace`, `YateConfig`, `Axis`,
   `Leaf`, `ShellResult`).  This lets downstream modules write
   `from yate.interfaces import AppProtocol, Workspace, Axis` for a unified
   import surface.

2. **Add an auto-check for remaining `Any` in interfaces.py.**  The
   `reportUnknownType` rule in pyright strict mode does not flag `Any`
   usage inside Protocol definitions.  A small CI script could grep for
   `: Any` in interfaces.py and compare against an allowlist (Textual
   internal types + opaque callbacks).

3. **Consider a `Protocol` for Textual integration surface.**  The 8
   members kept as `Any` are all Textual framework types
   (`screen`, `run_worker`, `_push_overlay`, `try_window_prefix(event)`,
   etc.).  A tiny `_TextualProtocol` could describe just the subset of
   Textual's API that YateApp relies on, replacing all 8 Any usages.
   Useful if Textual upgrades often break YateApp.

4. **Extract `Keymap` / `ActionRegistry` / `CommandRegistry` into their own
   leaf-level stub modules.**  Currently these classes import AppProtocol
   themselves, creating the cycle.  If we split each into a minimal stub
   (interfaces) module and keep the implementation elsewhere, interfaces.py
   could import them directly without TYPE_CHECKING.  Bigger refactor, but
   architecturally cleaner long-term.

5. **Add a `pyright: reportMissingTypeStubs=false` only for Textual-related
   imports.**  If Textual's type stubs improve in the future, the 8
   remaining `Any` usages can be revisited.
