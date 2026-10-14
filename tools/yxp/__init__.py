"""``tools.yxp`` -- build and verify yate extension packages (``.yxp``).

Development-time packager for the ``.yxp`` format consumed by
``yate --install-extension`` (see :mod:`yate.services.yxp` for the format
contract).  The tool reads a source directory holding a ``manifest``
metadata file (JSON: ``name`` / ``version`` / ``description`` / ``author``;
the ``files`` list is computed, never hand-written), packs every payload
file into a zip archive and records per-file SHA-256 digests::

    python -m tools.yxp build tools/yxp/example/hello_yxp
    python -m tools.yxp verify hello-1.0.0.yxp
"""
