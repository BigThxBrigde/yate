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

#: Hosts with a public read-only commit API that ``check_commit_pushed``
#: understands; everything else must be reported as "cannot verify".
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})


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


def check_supported(host: str) -> bool:
    """Whether :func:`check_commit_pushed` knows a public API for *host*.

    Callers gate on this first so an unsupported host is reported as
    "cannot verify, skipping gate", never as "unpushed".
    """
    return host == "gitee.com" or host in _GITHUB_HOSTS


def check_commit_pushed(
    remote: RemoteInfo, sha: str, *, timeout: float = _ONLINE_TIMEOUT_S
) -> bool | None:
    """Whether ``sha`` exists on the remote host.

    ``True`` = pushed, ``False`` = host answered 404 (not pushed), ``None`` =
    unknown (network error or unsupported host).  gitee.com's public
    read-only OpenAPI v5 and github.com's public REST API are consulted;
    no token is involved.
    """
    if remote.host == "gitee.com":
        api_url = (
            f"https://{remote.host}/api/v5/repos/{remote.owner}/{remote.repo}"
            f"/commits/{sha}"
        )
    elif remote.host in _GITHUB_HOSTS:
        api_url = (
            f"https://api.github.com/repos/{remote.owner}/{remote.repo}"
            f"/commits/{sha}"
        )
    else:
        return None
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
