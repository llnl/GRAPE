---
name: address-reviewer-comments
description: Gather unresolved GitLab merge request comments for a GRAPE branch or stack, fix trivial feedback, verify the resulting code changes, create a commit, and summarize how each comment was addressed. Use when working in this repository on review follow-up, reviewer comment triage, or merge request cleanup.
---

# Address Reviewer Comments

## Overview

Use this workflow when the task is "check unresolved comments on this branch", "address reviewer feedback", or "come up with answers for remaining MR comments" in this repository.

## Workflow

1. Inspect the workspace before making changes. Run `git status --short --branch` and note unrelated files so they are not reverted or committed by accident.
2. Determine whether the current branch belongs to a local stack by running `./grape -d stack status`. If it does, gather comments for every stack level in read-only mode with `./grape -d stack review --printUnresolvedComments`; this walks the levels in dependency order and uses each level's immediate review target. Use `--stack=<name-or-id>` when the intended stack is not the current/active one, and `--from=<level>` only when the request explicitly limits the review to that level and its descendants. If no stack is found, use `./grape -d review --printUnresolvedComments` for the current branch. Rely on the sandbox setup to provide `GRAPE_GITLAB_ACCESS_TOKEN` in the environment.
3. Group stack results by level and repository before editing. Identify the source branch for every comment; do not assume that a comment reported for an upper-level merge request belongs in the current checkout.
4. Classify the comments before editing:
   - Fix immediately only when the request is specific, low-risk, and clearly correct.
   - Do not make speculative behavioral changes just to silence a comment.
   - Treat stylistic or documentation requests as trivial only when the intent is unambiguous.
5. For a fix belonging to a non-current stack level, preserve local work, switch to that level with `./grape -d stack checkout <level>`, and make the change there. After committing a lower-level fix, keep descendants consistent with `./grape -d stack sync --from=<level>` before reviewing or editing descendant levels. Do not switch branches over uncommitted work.
6. Verify the exact area you touched. Prefer targeted tests such as `python3 -m pytest test/testReview.py` over broad suites unless the change genuinely needs broader coverage. For stack changes, also rerun `./grape -d stack status` and confirm the affected level targets and descendants remain coherent; rerun stack comment collection when a fix changes descendant diffs.
7. Create a commit for the code and skill changes. Do not include unrelated worktree noise.
8. Print a concise summary of the review comments, including stack level and repository, and how each one was addressed. Link each resolved item to the relevant local change using clickable file references with line numbers when possible, and note any comment that still needs follow-up.

## Review Response Rules

- Since this environment has read-only GitLab access, do not attempt to resolve threads or post replies remotely. The `--printUnresolvedComments` paths are for inspection only; do not treat stack review's normal submission behavior as authorization to push or update merge requests.
- For each unresolved comment left open, prepare a concrete proposal:
  - what change should be made next, if any
  - why it was not included in the trivial-fix pass
  - a likely reviewer-facing response when the comment is a question
- If a comment was effectively addressed by a nearby refactor, say that directly and cite the local change.
- If a lower-level change requires descendant rewrites or retargeting, report that follow-up explicitly rather than hiding it in the comment summary.

## Command Reference

- Detect the current stack: `./grape -d stack status`
- Gather comments for a stack: `./grape -d stack review --printUnresolvedComments`
- Gather comments for a selected stack or level range: `./grape -d stack review --stack=<name-or-id> --from=<level> --printUnresolvedComments`
- Gather comments for a non-stacked branch: `./grape -d review --printUnresolvedComments`
- Pass `--ignoreCommenter=<user>` to either review command when requested.
