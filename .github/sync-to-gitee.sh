#!/usr/bin/env bash
trap 'exit 0' INT
# SIGTERM/SIGHUP kill bash outright without firing the EXIT trap, so route
# them through exit first -- the EXIT trap below then performs the cleanup.
trap 'exit 1' TERM HUP

# Sync the current repository to Gitee:
#   0. Preflight: enter the repo root, refuse to run if a remote named
#      'gitee' already exists (this script owns that remote for its whole
#      lifetime and must never touch one it did not create).
#   1. Connectivity test via ssh -T git@gitee.com. Note: Gitee exits with
#      status 1 even on successful auth ("does not provide shell access"),
#      so success is detected by matching "successfully authenticated" in
#      the output, not by the exit code.
#   2. Add the gitee remote.
#   3. Prompt for a branch name; exit if the branch does not exist locally.
#   4. git push gitee <branch>; exit on failure.
#   5. From step 2 onward, any error/interrupt/normal exit runs the cleanup
#      trap: restore the branch checked out at startup + remove the gitee
#      remote.

# Enter the repository root (Codespaces usually starts there already; this
# is a safety net).
echo "==> [0/5] entering repository root ..."
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "error: not inside a git repository" >&2
    exit 1
}

# Preflight: a pre-existing 'gitee' remote means this is either a leftover
# from a crashed earlier run or a remote the user set up themselves; never
# silently delete either. Refuse to run and let the user decide.
if git remote get-url gitee >/dev/null 2>&1; then
    echo "error: a remote named 'gitee' already exists ($(git remote get-url gitee))" >&2
    echo "       if it is a leftover, remove it first: git remote remove gitee" >&2
    exit 1
fi

GITEE_URL="git@gitee.com:jermaine/yate.git"

# ---------- 1. Connectivity test (exit immediately on failure; nothing to
# clean up yet) ----------
echo "==> [1/5] testing ssh connectivity to gitee ..."
ssh_test="$(ssh -T git@gitee.com 2>&1)"
printf '%s\n' "$ssh_test"
# The match runs on a letters-only projection of the banner: the live Gitee
# greeting has been observed to contain invisible characters that defeat a
# plain substring match even though the text looks identical on screen.
# LC_ALL=C keeps tr byte-oriented and deterministic.
if printf '%s' "$ssh_test" | LC_ALL=C tr -cd '[:alnum:]' | grep -q "successfullyauthenticated"; then
    echo "==> [1/5] ok: authenticated"
else
    echo "error: gitee ssh connectivity test failed" >&2
    exit 1
fi

# Make git's own ssh transport (the push below) accept the Gitee host key on
# first contact and never hang on a dead network.  BatchMode is deliberately
# NOT set: the step-1 ssh may have asked for a key passphrase, and the push
# must be allowed to do the same.
export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

# Branch checked out at startup; restored during cleanup (defensive -- the
# script itself never switches branches).
orig_branch="$(git branch --show-current)"
echo "==> current branch: '${orig_branch:-<detached HEAD>}'"

# ---------- 5. Cleanup: covers every exit path after step 2 ----------
cleanup() {
    echo "==> [5/5] cleaning up ..."
    if [ -n "$orig_branch" ]; then
        git checkout -q "$orig_branch" 2>/dev/null
    fi
    git remote remove gitee 2>/dev/null
    echo "==> [5/5] done: branch restored to '${orig_branch:-<detached HEAD>}', remote 'gitee' removed"
}
trap cleanup EXIT

# ---------- 2. Add the gitee remote ----------
echo "==> [2/5] adding gitee remote ..."
git remote add gitee "$GITEE_URL" || {
    echo "error: git remote add gitee failed" >&2
    exit 1
}
git remote -v || {
    echo "error: git remote -v failed" >&2
    exit 1
}
echo "==> [2/5] ok: remote 'gitee' -> $GITEE_URL"

# ---------- 3. Prompt for the branch name ----------
echo "==> [3/5] waiting for the branch name to sync ..."
printf "branch to sync to gitee: "
read -r branch
# Strip a stray trailing CR (pasting from CRLF sources on Windows would
# otherwise make the branch lookup fail with a confusing name).
branch="$(printf '%s' "$branch" | tr -d '\r')"
if [ -z "$branch" ] || ! git show-ref --verify --quiet "refs/heads/$branch"; then
    echo "error: branch not found: '$branch'" >&2
    exit 1
fi
echo "==> [3/5] ok: branch '$branch' exists locally"

# ---------- 4. Push ----------
# Fully-qualified refspec: a branch name starting with '-' cannot be
# misparsed as an option, and there is no refspec ambiguity warning.
echo "==> [4/5] pushing '$branch' to gitee ..."
if ! git push gitee "refs/heads/$branch:refs/heads/$branch"; then
    echo "error: git push gitee '$branch' failed" >&2
    exit 1
fi
echo "==> [4/5] ok: '$branch' synced to gitee"
