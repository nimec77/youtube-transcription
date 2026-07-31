---
name: release
description: Use when the user asks to record changes in CHANGELOG.md, bump or update the app version, cut or prepare a release, or after merging user-visible changes that are not logged in the changelog yet.
---

# Release: Changelog + Version Bump

## Overview

Log user-visible changes in CHANGELOG.md first; the changelog content then
dictates the version bump. Never pick a version from commit count or gut
feeling.

## Mode decision

- Asked only to record/log changes (no release wanted) → do **Log changes**,
  stop. No version bump.
- Asked to release, bump, or update the version → do **Log changes**, then
  **Cut the release**.

## Log changes

1. Find the last release: the topmost dated `## [X.Y.Z] — YYYY-MM-DD` heading
   in CHANGELOG.md. List commits since it: `git describe --tags --abbrev=0`
   then `git log --oneline <tag>..HEAD`; if no tags exist yet, find the commit
   that added that section (`git log --oneline -S"[X.Y.Z]" -- CHANGELOG.md`).
2. Every **user-visible** change in that range (behavior, output format, CLI
   flags, fixes) gets an entry under `## [Unreleased]` in the proper
   Keep a Changelog category: Added / Changed / Deprecated / Removed / Fixed /
   Security. Skip internal-only work: refactors, tests, CI, docs, specs.
3. Write entries for someone running the tool ("transcript paragraphs gain
   `[M:SS]` prefixes"), not for someone reading the diff ("formatter.py now
   returns tuples").

## Cut the release

1. Choose the bump from what `[Unreleased]` contains:

   | `[Unreleased]` contains | pre-1.0 (0.x) | 1.0+ |
   |---|---|---|
   | breaking change | minor: 0.(y+1).0 | major |
   | any Added / Changed | minor: 0.(y+1).0 | minor |
   | only Fixed / Security | patch: 0.y.(z+1) | patch |

2. Rename `## [Unreleased]` to `## [X.Y.Z] — YYYY-MM-DD` (today, ISO 8601)
   and add a fresh empty `## [Unreleased]` above it.
3. Update the version in **every** location — they must never disagree:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `yt_transcribe/__init__.py` → `__version__ = "X.Y.Z"`
   - then run `uv lock` (uv.lock pins the project's own version)
4. Verify before committing:

   ```bash
   grep -n "X.Y.Z" pyproject.toml yt_transcribe/__init__.py uv.lock CHANGELOG.md
   uv run pytest -q
   ```

   The **old** version string must remain only in historical changelog
   sections — nowhere else.
5. Commit everything as `release: vX.Y.Z`, then tag that commit:
   `git tag vX.Y.Z`. Don't push unless asked.

## Common mistakes

- Bumping `pyproject.toml` but not `yt_transcribe/__init__.py` — the two must
  always carry the same version.
- Skipping `uv lock`, leaving a stale version pin in `uv.lock`.
- Choosing the bump from the number or size of commits instead of the
  `[Unreleased]` categories.
- Logging refactors, test, or doc changes — the changelog is for users.
- Releasing with an empty `[Unreleased]` without first checking git history
  for unlogged user-visible changes.
- Forgetting the `git tag`, or a non-ISO / missing date on the new heading.
