---
name: irun-sync
description: Synchronize and ship changes in the IRUN repository using the PR-only GitHub workflow. Use when the user asks to sync/synchronize, push changes, open/update a PR, or merge a PR into main. This skill standardizes pushing the current branch, creating/updating a PR to main, detecting GitHub merge conflicts, optionally merging (squash), and updating local main from origin/main.
---

# IRUN Sync/Ship Workflow

## Definitions

- Sync means: push the current topic branch to `origin`, create/update a PR targeting `main`, then fast-forward local `main` from `origin/main`.
- Ship means: do Sync, then attempt to squash-merge the PR (if not blocked).

## Commands (preferred)

Run these from the repo root:

- Sync: `./scripts/pr sync`
- Ship (attempt merge): `./scripts/pr ship`
- Push + PR only (no merge): `./scripts/pr ship --no-merge`

## Guardrails

- Never push directly to `main`.
- Require a clean working tree before sync/ship (commit or stash first).
- If GitHub reports merge conflicts (PR merge state is `CONFLICTING`), stop and resolve manually (rebase or merge `main` into the branch), then push and rerun.
- If `gh auth status -h github.com` fails, log in (`gh auth login -h github.com`) and stop.

## Expected Behavior

- `./scripts/pr sync` should leave you on the original topic branch (it temporarily switches to `main` to pull, then switches back).
- If required checks prevent merging, `./scripts/pr ship` may enable auto-merge or fail to merge immediately; report PR state and stop.

