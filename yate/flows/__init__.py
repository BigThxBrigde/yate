"""L3 flow modules: single-purpose orchestration split out of the editor.

Each module here is constructed by :class:`yate.editor.Editor` with explicit
collaborators and callbacks; none of them imports upward (no ``yate.editor``
/ ``yate.app``) and none holds the App handle (architecture-boundaries
section 1 L3, R11).  The package ``__init__`` stays lazy (architecture-boundaries
rule 3.5): no re-exports, import every module by its full path, e.g.
``from yate.flows.completion_flows import CompletionFlows``.
"""
