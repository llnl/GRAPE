---
name: prepare-for-review
description: Run through a checklist to prepare a branch for review by other developers.
---

# Prepare For Review

## Overview

Use this workflow to make a branch review-ready without changing its intended behavior. Focus on reducing review noise, documenting non-obvious new code, and leaving the branch in a state that is ready for the user to commit and send for review.

## Workflow

0. Ensure you're running on a backend node so that you can do builds and run tests when called for below.
1. Inspect the workspace before editing. Run `git status --short --branch` so unrelated files are visible and do not get cleaned up or committed by accident.
2. Review the branch surface area with `./grape diff develop --name-only`. If you need to compare against a specific base branch, use the appropriate GRAPE option rather than shell placeholder syntax.
3. Ensure the working tree is clean before proceeding. Run `grape status -u` and do not disturb unrelated user changes.
4. For each checklist item below, make any needed changes to address issues you find. If you make a change, create a commit on the current branch with a commit message that names the checklist item and summarizes the findings that justified the change.
5. Use your default Plan tool to track the checklist work below and address applicable items.
   - Review the code for alternative designs that would lead to a simpler implementation.
   - Review the code for opportunities to use standard software design patterns were appicable.
   - Review any dev\_docs changes for simplicity, conduct a more thorough design review for any new goals.
   - Review any .agents/skills changes for clarity and brevity for token conservation.
   - Remove dead code, commented-out experiments, and obvious debug scaffolding.
   - Remove experimental test harnesses that were added only for development.
   - Ensure all new code has google style docs (Python).
   - Ensure any method with multiple code blocks has documentation at each block explaining what it is doing.
   - Fix any obvious typos in both newly added code documentation and surrounding code documentation.
   - If any tpls were modified, make sure their version string in host-configs/BaseLibraryInfo.cmake was ticked (the last slot)
   - Review the code changes for possible race conditions, and apply any fixes.
   - Review the code for adhering to Dont Repeat Yourself (DRY) principles.
   - Review the code for obvious performance issues.
   - Review any new algorithms for correctness.

6. Print the results of the above steps in an organized table, one row per step, with a description of any changes or a LGTM for items that seem fine. (with a justification for why it's good as is).

7. Craft a Merge Request description that has a high level Summary describing the changes wholistically across the repositories in the workspace, a detail section with up to a few bullets per modified workspace describing specifics. Do not write a file - print it in markdown to the screen.

## Guardrails

- Treat this as a review-preparation pass, not a feature rewrite.
- Prefer targeted cleanup in files that are already part of the branch diff.
- Do not revert unrelated user changes outside the cleanup scope.
- Call out remaining risky or ambiguous changes instead of guessing.
