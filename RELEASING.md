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
[`showsaver/version.py`](showsaver/version.py). You no longer edit it by hand —
[release-please](#how-releases-work) writes it (and the git tag) from the same
source, so the two can never drift.

## Branching

- `dev` — integration branch. All work lands here first.
- `main` — release branch. Releases are only ever cut from `main`.

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

## How releases work

Releases are driven by [release-please](https://github.com/googleapis/release-please).
There is **no manual version bump and no manual `git tag`**. The flow is:

### 1. Land work on `main` with Conventional Commit titles

Merge PRs to `main` as usual. The PR title (squash-merge commit) must follow
[Conventional Commits](https://www.conventionalcommits.org/), because the next
version and the changelog are computed from them:

| Commit prefix                        | Effect on next version |
|--------------------------------------|------------------------|
| `fix:`                               | PATCH bump             |
| `feat:`                              | MINOR bump             |
| `feat!:` / `BREAKING CHANGE:` footer | MAJOR bump             |
| `chore:`, `docs:`, `refactor:`, …    | no release on their own |

A push to `main` always publishes `:edge` and `:sha-…` to DockerHub. It does
**not** touch `:latest`.

### 2. release-please maintains a "release PR"

On every push to `main`, the `release-please` workflow opens (or updates) a
single PR titled **`chore(main): release X.Y.Z`**. That PR:

- bumps [`showsaver/version.py`](showsaver/version.py) to the computed version,
- creates/updates `CHANGELOG.md` from the commits since the last release.

As more PRs merge, this release PR keeps itself up to date. Nothing is released
while it sits open.

### 3. Merge the release PR to cut the release

When you're ready to release, **merge the release PR**. release-please then:

1. creates the `vX.Y.Z` git tag, and
2. creates the GitHub Release with auto-generated notes.

The new tag triggers
[`build-and-publish-docker-image.yml`](.github/workflows/build-and-publish-docker-image.yml),
which runs the full pytest suite and publishes `:X.Y.Z`, `:X.Y`, `:latest`, and
`:sha-…` to DockerHub.

> The tag is pushed with a PAT (`RELEASE_PLEASE_TOKEN`) rather than the default
> `GITHUB_TOKEN` precisely so that this build workflow fires — token-created
> tags do not trigger other workflows.

## Overriding the computed version

To force a specific version (e.g. graduate to `1.0.0`), add a footer to any
commit that lands on `main`:

```
Release-As: 1.0.0
```

release-please will set the next release PR to that version.

## Pre-releases

For a release candidate, set the version explicitly via a `Release-As` footer:

```
Release-As: 0.4.0-rc.1
```

When the release PR merges, release-please creates a tag with the `-` in it; the
GitHub Release is marked as a pre-release and DockerHub gets `:0.4.0-rc.1` only
(`:latest` and `:0.4` are untouched).

## Configuration

- [`release-please-config.json`](release-please-config.json) — release type,
  changelog sections, and the `extra-files` entry that writes
  `showsaver/version.py` (keyed off the `# x-release-please-version` annotation).
- [`.release-please-manifest.json`](.release-please-manifest.json) — the
  last-released version (release-please's source of truth for the baseline).
- [`.github/workflows/release-please.yml`](.github/workflows/release-please.yml)
  — runs release-please on every push to `main`.
