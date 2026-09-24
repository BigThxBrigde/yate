"""Service layer: workspace tree, shell execution and extension loading.

Submodules are deliberately **not** re-exported: importing this package
(e.g. ``from yate.services import fonts``) must not eagerly load the
extension loader and the rest of the service stack. Import from the
submodule that defines the symbol
(``from yate.services.workspace import Workspace``).
"""
