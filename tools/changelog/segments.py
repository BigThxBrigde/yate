"""Version segmentation — pure functions over collected git data (no IO).

Conventions frozen in ``.trae/documents/changelog_plan.md`` §2:

* a boundary commit starts its version: the segment spans
  ``[boundary commit, next newer boundary)`` — the bump commit itself
  belongs to the NEW version;
* repeated bumps of the same version merge into one segment starting at the
  first (oldest) bump; a ``vX.Y.Z`` tag wins over a bump of the same version;
* with no tags and no bumps at all the whole history is one cold-start
  segment for the current version, dated at the newest commit;
* commits newer than the newest boundary become the leading ``Unreleased``
  segment; commits older than the oldest boundary fold into the oldest
  segment (nothing is dropped);
* ordering uses topo positions only — author dates are display fields and
  never influence segment boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence

from .model import Boundary, Commit, RawCommit, ReleaseSegment, TagRef, VersionBump

#: Position used for boundaries whose sha is not in the collected history
#: (unreachable/shallow) — treated as older than everything collected.
_UNREACHABLE = 10**9


def build_boundaries(
    tags: Sequence[TagRef],
    bumps: Sequence[VersionBump],
    full_commits: Sequence[RawCommit],
    *,
    current_version: str,
) -> list[Boundary]:
    """Merge tag and bump boundaries into one old→new list.

    ``bumps`` must be oldest-first (as produced by
    :func:`gitdata.read_version_bumps`); the first bump of a version wins.
    Tags override bumps for the same version.

    Cold start: when the version never changed (no tags, and every recorded
    bump still carries the current version — i.e. just the initial import),
    the bumps do not count as boundaries.
    """
    if not tags and bumps and all(b.version == current_version for b in bumps):
        bumps = ()
    dates = {commit.sha: commit.author_date for commit in full_commits}
    by_version: dict[str, tuple[str, str, bool]] = {}
    for bump in bumps:  # oldest-first: keep the FIRST bump per version
        if bump.version not in by_version:
            by_version[bump.version] = (bump.sha, dates.get(bump.sha, ""), False)
    for tag in tags:
        version = tag.name[1:] if tag.name.startswith("v") else tag.name
        by_version[version] = (tag.sha, dates.get(tag.sha, ""), True)
    index = {commit.sha: i for i, commit in enumerate(full_commits)}
    ordered = sorted(
        by_version.items(), key=lambda item: -index.get(item[1][0], _UNREACHABLE)
    )
    return [
        Boundary(version=version, sha=sha, date=date, from_tag=from_tag)
        for version, (sha, date, from_tag) in ordered
    ]


def build_segments(
    full_commits: Sequence[RawCommit],
    entries: Sequence[Commit],
    boundaries: Sequence[Boundary],
    *,
    current_version: str,
) -> list[ReleaseSegment]:
    """Slice classified ``entries`` into version segments, newest first.

    ``full_commits`` (newest first, merges included) provides the topo
    positions used to place boundaries and assign entries.
    """
    if not boundaries:  # cold start: one segment holding the entire history
        newest_date = full_commits[0].author_date if full_commits else None
        return [
            ReleaseSegment(
                version=current_version,
                date=newest_date,
                commits=list(entries),
                range_from="ROOT",
                range_to=f"v{current_version}",
                initial=True,
            )
        ]

    index = {commit.sha: i for i, commit in enumerate(full_commits)}
    ordered = sorted(
        boundaries, key=lambda b: -index.get(b.sha, _UNREACHABLE)
    )  # old → new
    cut_indexes = [index.get(b.sha, _UNREACHABLE) for b in ordered]

    # Segment p covers topo positions [cut_indexes[p], cut_indexes[p + 1])
    # (the newest segment reaches up to position 0); Unreleased covers
    # everything newer than the newest cut.
    per_boundary: list[ReleaseSegment] = []
    for position, boundary in enumerate(ordered):
        previous_version = ordered[position - 1].version if position > 0 else None
        per_boundary.append(
            ReleaseSegment(
                version=boundary.version,
                date=boundary.date or None,
                range_from=(f"v{previous_version}" if previous_version else "ROOT"),
                range_to=f"v{boundary.version}",
                initial=position == 0,
            )
        )
    newest_cut = cut_indexes[-1]
    unreleased = ReleaseSegment(
        version=None,
        date=None,
        range_from=f"v{ordered[-1].version}",
        range_to="HEAD",
    )

    for commit in entries:
        position = index.get(commit.sha)
        if position is None or position < newest_cut:
            unreleased.commits.append(commit)
            continue
        for p in range(len(cut_indexes)):  # ascending: oldest cut first hit wins
            if position >= cut_indexes[p]:
                per_boundary[p].commits.append(commit)
                break

    # Unreleased leads the output only when commits exist above the newest cut.
    if unreleased.commits:
        return [unreleased, *reversed(per_boundary)]
    return list(reversed(per_boundary))
