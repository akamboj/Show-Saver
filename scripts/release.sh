#!/usr/bin/env bash
# Bump showsaver/version.py to the given version and commit on the current
# branch. Prints the tag/push commands to run on `main` after the version-bump
# PR merges. Tag pushes stay manual on purpose — see RELEASING.md.
#
# Usage: bash scripts/release.sh <version>
# Example: bash scripts/release.sh 0.4.0
#          bash scripts/release.sh 0.4.0-rc.1

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <version>" >&2
    echo "Example: $0 0.4.0" >&2
    exit 1
fi

NEW_VERSION="$1"

if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
    echo "Error: '$NEW_VERSION' is not a valid SemVer string (expected X.Y.Z or X.Y.Z-prerelease)" >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
VERSION_FILE="$REPO_ROOT/showsaver/version.py"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: $VERSION_FILE not found" >&2
    exit 1
fi

CURRENT_VERSION=$(python3 -c "import re,pathlib; print(re.search(r'\"([^\"]+)\"', pathlib.Path('$VERSION_FILE').read_text()).group(1))")

if [ "$CURRENT_VERSION" = "$NEW_VERSION" ]; then
    echo "Error: version is already $NEW_VERSION" >&2
    exit 1
fi

CURRENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "dev" ]; then
    echo "Warning: current branch is '$CURRENT_BRANCH', not 'dev'."
    read -r -p "Continue anyway? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY]) ;;
        *) echo "Aborted."; exit 1 ;;
    esac
fi

if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
    echo "Error: working tree has uncommitted changes. Commit or stash first." >&2
    exit 1
fi

python3 -c "
import pathlib, re
p = pathlib.Path('$VERSION_FILE')
text = p.read_text()
new_text = re.sub(r'__version__\s*=\s*\"[^\"]+\"', '__version__ = \"$NEW_VERSION\"', text, count=1)
if new_text == text:
    raise SystemExit('Failed to rewrite __version__ — pattern not found')
p.write_text(new_text)
"

echo "Bumped $CURRENT_VERSION -> $NEW_VERSION"
git -C "$REPO_ROOT" --no-pager diff -- "$VERSION_FILE"

git -C "$REPO_ROOT" add "$VERSION_FILE"
git -C "$REPO_ROOT" commit -m "chore: bump version to $NEW_VERSION"

cat <<EOF

Done. Next steps:

  1. Push this branch and open a PR to main:
       git push

  2. After the PR merges, tag the release commit on main:
       git checkout main
       git pull
       git tag -a v$NEW_VERSION -m "Release $NEW_VERSION"
       git push origin v$NEW_VERSION

  3. CI publishes the Docker image and creates the GitHub Release.
     See RELEASING.md for the full flow.
EOF
