---
name: irun-sync
description: Synchronize and ship changes in the IRUN repository using a gh-first PR workflow. Use when the user asks to sync/synchronize, push changes, open/update a PR, or merge to main. This skill standardizes creating a `codex/*` branch when needed, using `gh` for PR/remote lifecycle, handling conflicts safely, merging (squash), and syncing local main.
---

# IRUN Sync/Ship Workflow

## Definitions

- Sync/Ship means one automatic flow: push branch changes, create/update PR to `main`, merge PR (squash), then fast-forward local `main` from `origin/main`.

## gh-First Policy

- Prefer `gh` for GitHub-facing operations (PR create/view/check/update/merge).
- Use `git` only for local-only steps (`switch`, `add`, `commit`, local conflict edits, local fast-forward).
- Use Windows/PowerShell-safe commands (no Bash-only syntax).
- Authenticate first: `gh auth status -h github.com` (if failed: ask user to run `gh auth login -h github.com`).

## Preferred Execution (No Helper Script)

1. If current branch is `main`, create/switch to `codex/<topic>` with `git switch -c`.
2. Commit local changes on that branch (`git add` + `git commit`).
3. Push branch (`git push -u origin HEAD`).
4. Create or reuse PR to `main`:
   - Create: `gh pr create --base main --head <branch> --title "<title>" --body "<body>"`
   - Reuse existing PR when present: `gh pr view <branch>` or `gh pr list --head <branch> --state open`
5. Check PR status when needed:
   - `gh pr view <pr> --json mergeStateStatus,state,url`
   - `gh pr checks <pr> --required` (or `--watch`)
6. Merge PR:
   - Preferred: `gh pr merge <pr> --squash --delete-branch`
   - If checks are pending: `gh pr merge <pr> --squash --auto --delete-branch`
7. Sync local `main`:
   - `git switch main`
   - `git pull --ff-only origin main`

## Guardrails

- Never push directly to `main`.
- Never force-push.
- Prefer `gh` over raw `git` for remote/PR operations.
- If PR merge state is `CONFLICTING`, try safe update first:
  - `gh pr update-branch <pr>` (or `gh pr update-branch <pr> --rebase` when appropriate)
  - resolve straightforward conflicts locally if needed, push, re-check PR
  - if conflict is non-trivial/risky, ask user before proceeding
- If `gh auth status -h github.com` fails, log in (`gh auth login -h github.com`) and stop.

## Useful gh Commands (Quick Reference)

- `gh pr status` - show current repo PR status for your branches.
- `gh pr list --state open --base main` - list open PRs to `main`.
- `gh pr view <pr> --web` - open PR page in browser.
- `gh pr checks <pr> --watch --required` - watch required checks.
- `gh pr merge <pr> --squash --delete-branch` - squash merge and clean branch.

