"""``tools.yxp`` -- scaffold, build and verify yate extension packages.

Development-time packager for the ``.yxp`` format consumed by
``yate --install-extension`` (see :mod:`yate.services.yxp` for the format
contract).  ``--create NAME`` scaffolds a new package source directory
(manifest metadata file plus a starter extension); ``--pack DIR`` reads a
source directory holding a ``manifest`` metadata file (JSON: ``name`` /
``version`` / ``description`` / ``author``; the ``files`` list is
computed, never hand-written), packs every payload file into a zip archive
and records per-file SHA-256 digests; ``--verify FILE`` validates an
existing archive with the install-time rules::

    python -m tools.yxp --create my_ext
    python -m tools.yxp --pack tools/yxp/example/hello_yxp
    python -m tools.yxp --verify hello_yxp.yxp
"""
