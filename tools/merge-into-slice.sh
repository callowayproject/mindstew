#!/usr/bin/env bash
# Merge a ticket branch into its slice (integration) branch and push.
#
# Usage: tools/merge-into-slice.sh <ticket-branch> <slice-branch> [commit message]
#
# Works on a detached HEAD, so it succeeds even when the slice branch is checked out in another worktree.
# Pushes only if the full test suite and lint pass. Stops on a merge conflict so a person or agent can resolve it.
set -euo pipefail

ticket="${1:?usage: $0 <ticket-branch> <slice-branch> [message]}"
slice="${2:?usage: $0 <ticket-branch> <slice-branch> [message]}"
message="${3:-Merge ${ticket}}"

git fetch --quiet origin
git checkout --quiet --detach "origin/${slice}"

if ! git merge --no-ff -m "${message}" "origin/${ticket}"; then
    echo "Merge conflict: resolve it, run 'uv run pytest' and 'uv run ruff check', then 'git push origin HEAD:${slice}'." >&2
    exit 1
fi

uv run pytest -q
uv run ruff check

git push origin "HEAD:${slice}"
echo "Merged ${ticket} into ${slice} at $(git rev-parse --short HEAD)"
