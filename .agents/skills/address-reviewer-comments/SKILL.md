---
name: address-reviewer-comments
description: Gather unresolved GitLab merge request comments for the current branch with `grape -d review --printUnresolvedComments`, fix trivial feedback, verify the resulting code changes, create a commit, and summarize how each comment was addressed. Use when working in this repository on review follow-up, reviewer comment triage, or merge request cleanup.
---

# Address Reviewer Comments

## Overview

Use this workflow when the task is "check unresolved comments on this branch", "address reviewer feedback", or "come up with answers for remaining MR comments" in this repository.

## Workflow

1. Inspect the workspace before making changes. Run `git status --short --branch` and note unrelated files so they are not reverted or committed by accident.
2. Gather unresolved comments in read-only mode with `./grape -d review --printUnresolvedComments`. Rely on the sandbox setup to provide `GRAPE_GITLAB_ACCESS_TOKEN` in the environment.
3. Classify the comments before editing:
   - Fix immediately only when the request is specific, low-risk, and clearly correct.
   - Do not make speculative behavioral changes just to silence a comment.
   - Treat stylistic or documentation requests as trivial only when the intent is unambiguous.
4. Verify the exact area you touched. Prefer targeted tests such as `python3 -m pytest test/testReview.py` over broad suites unless the change genuinely needs broader coverage.
5. Create a commit for the code and skill changes. Do not include unrelated worktree noise.
6. Print a concise summary of the review comments and how each one was addressed. Link each resolved item to the relevant local change using clickable file references with line numbers when possible, and note any comment that still needs follow-up.

## Review Response Rules

- Since this environment has read-only GitLab access, do not attempt to resolve threads or post replies remotely.
- For each unresolved comment left open, prepare a concrete proposal:
  - what change should be made next, if any
  - why it was not included in the trivial-fix pass
  - a likely reviewer-facing response when the comment is a question
- If a comment was effectively addressed by a nearby refactor, say that directly and cite the local change.

## Command Reference

- Gather comments: `./grape -d review --printUnresolvedComments`
- Gather comments non-interactively with extra flags: `./grape -d review --printUnresolvedComments ...`
- Focus on a smaller surface if needed by passing extra `grape review` flags directly.
