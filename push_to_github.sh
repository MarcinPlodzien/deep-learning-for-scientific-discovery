#!/usr/bin/env bash
# Publish the course website to GitHub as one snapshot commit, with no history.
#
# The current files in this folder (as built by ./build.sh) become the only
# commit of the branch main on GitHub. The old history on GitHub is replaced.
# Your local branch main and its history are kept unchanged.
#
# Usage:   ./push_to_github.sh            (asks for confirmation)
#          ./push_to_github.sh -y         (no question)
set -euo pipefail
cd "$(dirname "$0")"

REMOTE=origin
BRANCH=main
MSG="Course website: snapshot of $(date +%Y-%m-%d)"

if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  echo "Please switch to the branch $BRANCH first (git checkout $BRANCH)." >&2
  exit 1
fi

echo "Files that differ from the last local commit:"
git status --short | head -30 || true
echo
echo "This replaces the whole history of $REMOTE/$BRANCH on GitHub"
echo "with one commit containing the current files of this folder."
if [[ "${1:-}" != "-y" ]]; then
  read -r -p "Type yes to publish: " answer
  [[ "$answer" == "yes" ]] || { echo "Nothing published."; exit 0; }
fi

# record the current state locally as well, so the local history stays complete
git add -A
git diff --cached --quiet || git commit -q -m "$MSG"

# build a commit without parents from the same files and force it to GitHub
tree=$(git write-tree)
snapshot=$(git commit-tree "$tree" -m "$MSG")
git push -f "$REMOTE" "$snapshot:refs/heads/$BRANCH"

echo "Published $snapshot to $REMOTE/$BRANCH as a single commit."
echo "GitHub Actions now deploys ./docs; check the Actions tab of the repository."
