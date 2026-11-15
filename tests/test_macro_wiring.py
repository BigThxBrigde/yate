"""Wave-3 macro wiring acceptance tests (plan-f).

Covers the ``Editor.macro_flows`` contract, the factory-injected bound
methods, the status-bar recording-label callback, the rule-text and
guard-set synchronisation, and the R5 / R9 regressions.  Editors are built
through the project's existing ``YateApp(target=...)`` construction, the
same shape ``tests/test_macro_statusbar.py`` uses.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from types import MethodType
from typing import cast

import pytest
import yate.editor_compose as compose
from yate.app import YateApp
from yate.editor import Editor
from yate.flows.macro_flows import MacroFlows
from yate.session import EditorSession

PROJECT = Path(__file__).resolve().parent.parent
RULES = PROJECT / ".trae" / "rules" / "architecture-boundaries.md"
EDITOR_SRC = PROJECT / "yate" / "editor.py"
COMPOSE_SRC = PROJECT / "yate" / "editor_compose.py"
ARCH_SRC = PROJECT / "tests" / "test_architecture.py"


def _editor(tmp_path: Path) -> Editor:
    """Build a fully assembled Editor over a scratch target file."""
    target = tmp_path / "wiring.txt"
    target.write_text("x\n", encoding="utf-8")
    return YateApp(target=target).editor


def test_editor_exposes_macro_flows_bound_to_session(tmp_path: Path) -> None:
    """Editor exposes a MacroFlows instance wired to its session."""
    ed = _editor(tmp_path)
    assert ed.macro_flows is not None
    assert isinstance(ed.macro_flows, MacroFlows)
    session = cast(EditorSession, getattr(ed.macro_flows, "_session"))
    assert session is ed.session


def test_macro_flows_dispatch_raw_routes_to_handle_raw_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The factory injects ed.handle_raw_key as a bound method, not a protocol."""
    calls: list[str] = []

    def recorder(self: Editor, raw: str) -> bool:
        calls.append(raw)
        return True

    monkeypatch.setattr(Editor, "handle_raw_key", recorder)
    ed = _editor(tmp_path)
    bound = cast(MethodType, getattr(ed.macro_flows, "_dispatch_raw"))
    assert bound.__self__ is ed
    assert bound.__func__ is recorder
    assert bound("x") is True
    assert calls == ["x"]


def test_macro_flows_notify_is_bound_to_editor_message(tmp_path: Path) -> None:
    """The notify callable is the bound Editor.message method."""
    ed = _editor(tmp_path)
    bound = cast(MethodType, getattr(ed.macro_flows, "_notify"))
    assert bound.__self__ is ed
    assert bound.__func__ is type(ed).message


def test_statusbar_receives_recording_label_from_session_macro(
    tmp_path: Path,
) -> None:
    """StatusBar pulls rec @<reg> from session.macro and drops it when idle."""
    ed = _editor(tmp_path)
    label = ed.status_bar.recording_label
    assert label is not None
    ed.session.macro.recording = "a"
    assert label() == "rec @a"
    ed.session.macro.recording = None
    assert label() is None


def test_editor_compose_all_exports_macro_flows_factory() -> None:
    """The private factory is exported through __all__ for editor.py."""
    assert "_build_macro_flows" in compose.__all__
    assert callable(compose._build_macro_flows)


def test_size_exemption_rule_and_guard_are_in_sync() -> None:
    """Rule text and SIZE_EXEMPT_FILES both list editor.py; measured > 800."""
    arch = ARCH_SRC.read_text(encoding="utf-8")
    start = arch.index("SIZE_EXEMPT_FILES: frozenset[str] = frozenset({")
    end = arch.index("})", start)
    assert '"editor.py"' in arch[start:end]

    rules = RULES.read_text(encoding="utf-8")
    section = rules[
        rules.index("7. **文件体量阈值处置") : rules.index("8. **新增 L3 流程模块接入清单")
    ]
    assert "editor.py" in section
    lines = len(EDITOR_SRC.read_text(encoding="utf-8").splitlines())
    assert lines > 800
    assert str(lines) in section

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_architecture.py::test_source_files_within_size_threshold",
            "-q",
            "--tb=no",
        ],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_rule_l3_and_r11_lists_include_macro_flows() -> None:
    """Section 1 L3 and R11 list macro_flows; it stays off UI_FROZEN_FILES."""
    rules = RULES.read_text(encoding="utf-8")
    l3 = rules[rules.index("L3 调度：") : rules.index("L2 组件：")]
    r11 = rules[
        rules.index("**R11 — 冻结 UI 耦合**") : rules.index("**R7 — 外壳装载内置表**")
    ]
    assert "macro_flows.py" in l3
    assert "macro_flows.py" in r11
    assert "不进" in r11
    assert "flows/macro_flows.py" not in rules


def test_editor_does_not_import_action_tables_after_wiring() -> None:
    """R5: editor.py imports the new flows class, never the built-in tables."""
    tree = ast.parse(EDITOR_SRC.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    assert "yate.actions" not in modules
    assert "yate.commands" not in modules
    assert "yate.flows.macro_flows" in modules
    arch = ARCH_SRC.read_text(encoding="utf-8")
    assert "UPWARD_EDGES_FROZEN: frozenset[str] = frozenset()" in arch


def test_wiring_preserves_statusbar_id_and_existing_injections(
    tmp_path: Path,
) -> None:
    """R9: the statusbar id and the existing injections survive wiring."""
    ed = _editor(tmp_path)
    assert ed.status_bar.id == "statusbar"
    assert ed.status_bar.extension_segments is not None
    assert ed.status_bar.loaded_extensions is not None


def test_missing_macro_flows_attribute_is_a_type_error() -> None:
    """Pyright strict stays clean with the annotation and the factory assignment."""
    tree = ast.parse(EDITOR_SRC.read_text(encoding="utf-8"))
    editor_cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Editor"
    )
    annotations = {
        node.target.id
        for node in editor_cls.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "macro_flows" in annotations
    assert "ed.macro_flows = MacroFlows(" in COMPOSE_SRC.read_text(encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "pyright", "yate/editor.py"],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 errors" in proc.stdout
