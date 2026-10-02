"""Markdown-to-English translator backed by the ``codebuddy-code`` CLI.

Entry point: ``python -m tools.translate [IN] [OUT]``.  With no ``IN`` the
document is read from stdin, which is exactly the protocol
:mod:`tools.pack.wiki` speaks through ``--translate-cmd``; the translation
(and only the translation) is printed to stdout and, when ``OUT`` is given,
also written there as UTF-8.  Prompt/command assembly and the subprocess
call live in :mod:`tools.translate.runner`; the argparse front end lives in
:mod:`tools.translate.cli`.

Security note: the agent runs unattended with ``--tools "Read"`` and
``bypassPermissions``, so it can read any path the user can.  A malicious
source document could carry instructions that make it exfiltrate files into
the "translation", which then lands on publicly pushable wiki remotes.  Only
feed documents from trusted sources; never point this tool at untrusted
content.
"""

from __future__ import annotations
