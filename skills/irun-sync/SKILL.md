---
name: irun-sync
description: Synchronize and ship changes in the IRUN repository using the PR-only GitHub workflow. Use when the user asks to sync/synchronize, push changes, open/update a PR, or merge a PR into main. This skill standardizes creating a `codex/*` branch when needed, pushing changes, creating/updating a PR to main, handling merge conflicts, merging (squash), and syncing local main from origin/main.
---

# IRUN Sync/Ship Workflow

## Definitions

- Sync/Ship means one automatic flow: push branch changes, create/update PR to `main`, merge PR (squash), then fast-forward local `main` from `origin/main`.

## Preferred Execution (No Helper Script)

Run from repo root with git + GitHub CLI:

1. If current branch is `main`, create and switch to `codex/<topic>`.
2. Ensure working changes are committed on the branch.
3. Push branch: `git push -u origin HEAD`
4. Create or update PR to `main`: `gh pr create --base main --head <branch> --fill` (or reuse existing PR).
5. Merge PR: `gh pr merge --squash --delete-branch` (or `--auto --delete-branch` when checks are pending).
6. Return to `main` and sync: `git fetch origin main && git switch main && git pull --ff-only origin main`

## Guardrails

- Never push directly to `main`.
- Never force-push.
- If GitHub reports merge conflicts (PR merge state is `CONFLICTING`), first attempt safe conflict resolution by updating branch from latest `main` and resolving straightforward conflicts; if conflicts are non-trivial, ask the user.
- If `gh auth status -h github.com` fails, log in (`gh auth login -h github.com`) and stop.

