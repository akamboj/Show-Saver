# Releasing Show-Saver

This document describes how to cut a new release of Show-Saver.

## Versioning

Show-Saver follows [SemVer 2.0.0](https://semver.org/):

| Bump  | When to use                                                                 |
|-------|-----------------------------------------------------------------------------|
| MAJOR | Backwards-incompatible API, route, or env-var changes                       |
| MINOR | New features, processors, routes, or env vars                               |
| PATCH | Bug fixes, dependency bumps, internal refactors                             |

Pre-releases use the form `v0.4.0-rc.1` / `v0.4.0-beta.1` and do not move
the `:latest` Docker tag.

The single source of truth for the version is
[`showsaver/version.py`](showsaver/version.py). The git tag must match
this file — CI enforces this on every `v*` tag push.

## Branching

- `dev` — integration branch. All work lands here first.
- `main` — release branch. Tags are only ever cut from `main`.

## Docker image tag policy

Published to `akamboj2000/show-saver` on DockerHub:

| Image tag      | Source                          | Stability        |
|----------------|---------------------------------|------------------|
| `:latest`      | latest non-prerelease `v*` tag  | stable           |
| `:X.Y.Z`       | the matching `v*` tag           | immutable        |
| `:X.Y`         | latest patch of that minor      | rolling-stable   |
| `:edge`        | every push to `main`            | unstable         |
| `:sha-abcdef0` | every build                     | immutable, debug |

Pre-release tags (`v0.4.0-rc.1`) publish `:0.4.0-rc.1` and `:sha-…` only
— they do **not** touch `:latest` or `:0.4`.

## Release process

The flow is manual and takes four steps.

### 1. Bump the version on `dev`

```bash
git checkout dev
git pull
# Edit showsaver/version.py — set __version__ to the new number.
git add showsaver/version.py
git commit -m "chore: bump version to X.Y.Z"
git push
```

Open a PR from `dev` to `main`.

### 2. Merge the PR

Once CI is green, merge to `main`. The merge commit publishes
`:edge` and `:sha-…` to DockerHub. `:latest` is **not** touched.

### 3. Tag the release commit on `main`

```bash
git checkout main
git pull
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

### 4. CI takes over

The tag push triggers the build workflow, which runs:

1. `tests` — full pytest suite
2. `verify-version` — asserts the tag matches `showsaver/version.py`
3. `build` — publishes `:X.Y.Z`, `:X.Y`, `:latest`, `:sha-…` to DockerHub
4. `release` — creates a GitHub Release with auto-generated notes

The release notes are built from PR titles since the previous tag, so
**keep PR titles descriptive**.

## Helper script

[`scripts/release.sh`](scripts/release.sh) wraps steps 1 and 3 in a
single command:

```bash
bash scripts/release.sh 0.4.0
```

It bumps `showsaver/version.py`, commits on the current branch, and
prints the exact `git tag` / `git push` commands to run on `main` after
the PR merges. It does not push tags itself — that stays manual on
purpose.

## Pre-releases

For a release candidate:

```bash
# After bumping showsaver/version.py to "0.4.0-rc.1" and merging to main:
git tag -a v0.4.0-rc.1 -m "Release candidate 0.4.0-rc.1"
git push origin v0.4.0-rc.1
```

The `release` job sees the `-` in the tag name and creates a GitHub
Release marked as a pre-release. DockerHub gets `:0.4.0-rc.1` only.
