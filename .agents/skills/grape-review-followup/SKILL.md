---
name: grape-review-followup
description: Gather unresolved GitLab merge request comments for the current branch with `grape review --printUnresolvedComments`, fix trivial feedback, verify the resulting code changes, create a commit, and draft proposals or reviewer responses for anything still unresolved. Use when working in this repository on review follow-up, reviewer comment triage, or merge request cleanup.
---

# Grape Review Followup

## Overview

Use this workflow when the task is "check unresolved comments on this branch", "address reviewer feedback", or "come up with answers for remaining MR comments" in this repository.

## Workflow

1. Inspect the workspace before making changes. Run `git status --short --branch` and note unrelated files so they are not reverted or committed by accident.
2. Gather unresolved comments in read-only mode. Prefer `scripts/print_unresolved_comments.sh` because it:
   - runs `./grape review --printUnresolvedComments`
   - injects `GRAPE_GITLAB_ACCESS_TOKEN` from `~/.gitlab_agent_authentication/gitlab_token` when available
   - defaults `--user` from `GRAPE_REVIEW_USER` or `$USER` if the caller did not provide one
3. If the helper still fails, debug the implementation in this repo instead of assuming the server is wrong. The relevant code usually lives in `vine/review.py`, `vine/Gitlab.py`, and `vine/utility.py`.
4. Classify the comments before editing:
   - Fix immediately only when the request is specific, low-risk, and clearly correct.
   - Do not make speculative behavioral changes just to silence a comment.
   - Treat stylistic or documentation requests as trivial only when the intent is unambiguous.
5. Verify the exact area you touched. Prefer targeted tests such as `python3 -m pytest test/testReview.py` over broad suites unless the change genuinely needs broader coverage.
6. Re-run the unresolved-comment command after the edits so the final summary is grounded in the latest state of the branch.
7. Create a commit for the code and skill changes. Do not include unrelated worktree noise.

## Review Response Rules

- Since this environment has read-only GitLab access, do not attempt to resolve threads or post replies remotely.
- For each unresolved comment left open, prepare a concrete proposal:
  - what change should be made next, if any
  - why it was not included in the trivial-fix pass
  - a likely reviewer-facing response when the comment is a question
- If a comment was effectively addressed by a nearby refactor, say that directly and cite the local change.

## Command Reference

- Gather comments: `.agents/skills/grape-review-followup/scripts/print_unresolved_comments.sh`
- Gather comments with an explicit user: `.agents/skills/grape-review-followup/scripts/print_unresolved_comments.sh --user=probinso`
- Focus on a smaller surface if needed by passing extra `grape review` flags through the helper.
