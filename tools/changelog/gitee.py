"""Gitee remote parsing, offline link construction and the optional online check.

The offline helpers never touch the network.  The online check uses the
standard library only and degrades to ``None`` (unknown) on any network
problem — callers must treat network failures as warnings, never as errors.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

_HTTPS_RE = re.compile(
    r"^https?://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)
_SSH_RE = re.compile(
    r"^ssh://git@(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)
_SCP_RE = re.compile(r"^git@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")

_ONLINE_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class RemoteInfo:
    """A parsed git remote, e.g. ``gitee.com/jermaine/yate``."""

    host: str
    owner: str
    repo: str

    @property
    def web_base(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.repo}"


def parse_remote(url: str) -> RemoteInfo | None:
    """Parse HTTPS, SSH and SCP-style remote URLs; ``None`` when unmatched."""
    url = url.strip()
    for pattern in (_HTTPS_RE, _SSH_RE, _SCP_RE):
        match = pattern.match(url)
        if match is not None:
            return RemoteInfo(
                host=match.group("host"),
                owner=match.group("owner"),
                repo=match.group("repo"),
            )
    return None


def commit_url(remote: RemoteInfo, sha: str) -> str:
    return f"{remote.web_base}/commit/{sha}"


def compare_url(remote: RemoteInfo, range_from: str, range_to: str) -> str:
    return f"{remote.web_base}/compare/{range_from}...{range_to}"


def check_commit_pushed(
    remote: RemoteInfo, sha: str, *, timeout: float = _ONLINE_TIMEOUT_S
) -> bool | None:
    """Whether ``sha`` exists on the remote host.

    ``True`` = pushed, ``False`` = host answered 404 (not pushed), ``None`` =
    unknown (network error or unsupported host).  Only gitee.com's public
    read-only OpenAPI v5 is consulted; no token is involved.
    """
    if remote.host != "gitee.com":
        return None
    api_url = (
        f"https://{remote.host}/api/v5/repos/{remote.owner}/{remote.repo}"
        f"/commits/{sha}"
    )
    request = urllib.request.Request(api_url, headers={"User-Agent": "yate-changelog"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        return None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def pushed_flags(
    remote: RemoteInfo | None, shas: Mapping[str, str]
) -> dict[str, bool]:
    """Check a mapping of ``short_sha -> full_sha``; stops at the first
    network failure and keeps only definite answers (``False`` = unpushed).
    """
    if remote is None:
        return {}
    flags: dict[str, bool] = {}
    for short_sha, sha in shas.items():
        state = check_commit_pushed(remote, sha)
        if state is False:
            flags[short_sha] = False
        elif state is None:
            break  # network trouble: degrade instead of hammering the API
    return flags
