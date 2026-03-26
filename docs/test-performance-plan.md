# Grape Test Performance Plan

## Summary
This document tracks the test-speed work for the root `test/` suite in this repository. It records the current plan, the baseline timings from the original runner, and the measured impact after each implementation phase.

Scope is limited to the repository's root `test/` suite. Vendored suites under `python-gitlab/`, `stashy/`, and `docopt/` are out of scope.

## Measurement Environment
- Repository: `grape`
- Baseline commit: `8e30d114`
- OS: `Linux 4.18.0-553.111.1.1toss.t4.x86_64 #1 SMP Thu Mar 12 13:50:19 PDT 2026 x86_64 GNU/Linux`
- Python: `3.13.2`
- Runner command: `./grape test`
- Measurement helper: `python3 tools/measure_grape_tests.py`

## Rolling Summary
| Date | Phase | Serial | W4 | W8 | W16 | W32 | W64 | Heavy Suites Summary | Delta vs Baseline | Delta vs Previous | Commit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| 2026-03-26 | Baseline | 44.75 | n/a | n/a | n/a | n/a | n/a | Status 12.00, MergeDown 7.32, NestedSubproject 6.91, Clone 5.71, Publish 5.12, GrapeUp 4.35, CO 3.03 | 0.00 | 0.00 | `8e30d114` |
| 2026-03-26 | Phase 2 | 48.51 | n/a | n/a | n/a | n/a | n/a | Status 11.89, MergeDown 7.72, NestedSubproject 7.89, Clone 6.72, Publish 5.54, GrapeUp 4.36, CO 3.70 | +3.76 | +3.76 | `fd996b72` |
| 2026-03-26 | Phase 3 | 64.77 | 42.63 | n/a | n/a | n/a | n/a | Status 12.98, MergeDown 8.31, NestedSubproject 8.14, Clone 6.74, Publish 5.54, GrapeUp 4.63, CO 3.80 | -2.12 in parallel mode | -5.88 in parallel mode | `6daa0f32` |
| 2026-03-26 | Phase 4 | 40.84 | 31.55 | n/a | n/a | n/a | n/a | Status 10.47, MergeDown 7.36, NestedSubproject 7.35, Clone 6.07, Publish 4.86, GrapeUp 3.71, CO 3.73 | -13.20 in parallel mode | -11.08 in parallel mode | `1619f924` |
| 2026-03-26 | Phase 5 | 38.29 | 30.76 | 31.74 | 31.84 | 31.78 | 32.96 | Status 9.54, MergeDown 7.72, NestedSubproject 7.76, Clone 6.60, Publish 5.52, GrapeUp 3.95, CO 3.85 | -13.99 at W4 | -0.79 at W4 | `df98b191` |
| 2026-03-26 | Phase 6 | 38.29 | 30.76 | 31.74 | 31.84 | 31.78 | 32.96 | CI shards: fast_core 4.96, git_workflow 8.28, workspace_topology 15.47, publish 4.88 | CI critical path 15.47 | unchanged local timings | `5bed0280` |
| 2026-03-26 | Phase 7 | 38.42 | 30.64 | 31.49 | 31.86 | 31.99 | 31.94 | Default `./grape test` now 30.68s; `--changed` selects mapped suites; docs-only/CI-only diffs map to no suites | -14.11 at W4 | -0.12 at W4 | `pending phase 7 commit` |

## Baseline Measurements

### Full Suite
`./grape test`

| Target | Seconds | Return Code |
| --- | ---: | ---: |
| full | 44.75 | 1 |

Notes:
- The original suite currently fails because `Publish` has existing failures.
- The wall time above still serves as the baseline for speed work because the failure occurs late in the run and exercises nearly the full suite.

### Per-Suite Timings From Original Runner

| Suite | Seconds | Return Code |
| --- | ---: | ---: |
| Branches | 0.75 | 0 |
| Bundle | 0.57 | 0 |
| Clone | 5.42 | 0 |
| Config | 0.73 | 0 |
| DeleteBranch | 0.84 | 0 |
| GrapeGit | 1.42 | 0 |
| MergeDown | 6.71 | 0 |
| ResolveConflicts | 0.55 | 0 |
| Review | 1.32 | 0 |
| Stash | 0.64 | 0 |
| Unbundle | 1.04 | 0 |
| Version | 0.90 | 0 |
| Publish | 5.08 | 1 |
| CO | 3.25 | 0 |
| NestedSubproject | 6.71 | 0 |
| Status | 10.82 | 0 |
| GrapeUp | 3.95 | 0 |

### Heavy-Suite Script Baseline
`python3 tools/measure_grape_tests.py --mode heavy --format markdown`

| Suite | Seconds | Return Code |
| --- | ---: | ---: |
| Status | 12.00 | 0 |
| MergeDown | 7.32 | 0 |
| NestedSubproject | 6.91 | 0 |
| Clone | 5.71 | 0 |
| Publish | 5.12 | 1 |
| GrapeUp | 4.35 | 0 |
| CO | 3.03 | 0 |

## Known Correctness Issues
- `Publish` currently fails under the original runner. These failures should be tracked separately from speed regressions.
- `pytest` is available in the environment, but `xdist` is not installed. Parallelism work should not depend on adding that package.

## Planned Phases
1. Add tracking docs and a reusable baseline measurement script.
2. Move `grape test` to a pytest-backed runner while preserving current CLI behavior.
3. Make heavy suites parallel-safe and reshape generated coverage into pytest-native collection.
4. Cache repeated repository bootstrap in the common test base.
5. Snapshot heavy scenario state instead of replaying every setup command per test.
6. Shard Linux CI so merge-request wall clock is driven by the longest shard rather than one full-suite job.
7. Add changed-test targeting and faster local defaults.

## Phase Log

### Phase 1
Status: complete

Completed output:
- `docs/test-performance-plan.md`
- `docs/test-performance-handoff.md`
- `tools/measure_grape_tests.py`

What changed:
- Added a reusable timing script that can measure the full suite or the heavy suites with stable command lines.
- Added the long-lived progress document and a handoff document for new agents.

Measured impact:
- No test-runner speed change was expected in this phase.
- Baseline measurement for the original runner is now documented and reproducible.

### Phase 2
Status: complete

What changed:
- Added `pytest.ini` so the root `test/` directory is the default collection target.
- Added [`vine/test_suites.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/test_suites.py) as the suite alias manifest for `grape test`.
- Switched [`vine/grapeTest.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/grapeTest.py) from the custom `unittest` aggregator to `pytest.main(...)` while preserving:
  - `./grape test`
  - `./grape test listSuites`
  - `./grape test <Suite>`
  - `./grape test <Suite>.<test>`
- Added pytest-visible aliases for `Status` and `GrapeUp` in:
  - [`test/testStatus.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testStatus.py)
  - [`test/testUpdateLocal.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testUpdateLocal.py)
- Added debug-mode environment plumbing in [`test/testGrape.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testGrape.py).

Measured impact:
- Full suite after the final Phase 2 fix: `48.51s` with return code `1`.
- Net change vs baseline: `+3.76s`.
- Heavy suites after Phase 2:
  - `Status`: `11.89s`
  - `MergeDown`: `7.72s`
  - `NestedSubproject`: `7.89s`
  - `Clone`: `6.72s`
  - `Publish`: `5.54s`
  - `GrapeUp`: `4.36s`
  - `CO`: `3.70s`

Notes:
- The first pytest-backed attempt regressed to `63.47s` because `Status` and `GrapeUp` were being collected twice.
- That regression was fixed by exposing pytest-only subclasses instead of renaming the generator classes in place.
- Phase 2 intentionally prioritizes compatibility over speed; Phase 3 and later phases are expected to recover and beat the baseline.

### Phase 3
Status: complete

What changed:
- Added [`test/testWorkspaceScenarios.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testWorkspaceScenarios.py) so `Status` and `GrapeUp` are collected as pytest-native parametrized suites instead of dynamic class mutation.
- Added [`test/conftest.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/conftest.py) to configure root-suite test markers and git test flags in pytest.
- Added markers across the heavy suites:
  - `slow`
  - `scenario`
  - `publish`
  - `serial`
- Extended [`vine/grapeTest.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/grapeTest.py) with `--workers=<n>` and a subprocess-based parallel suite runner.
- Updated [`tools/measure_grape_tests.py`](/usr/WS1/probinso/git/grape_workspaces/grape/tools/measure_grape_tests.py) so measurements can include `--workers`.
- Updated [`vine/test_suites.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/test_suites.py) so `Publish` stays in the serial lane and the `Status`/`GrapeUp` aliases point at the pytest-native scenario file.

Measured impact:
- Default serial full suite after Phase 3: `64.77s`, return code `1`.
- Opt-in parallel full suite after Phase 3: `42.63s` with `./grape test --workers=4`, return code `1`.
- Net change vs baseline in parallel mode: `-2.12s`.
- Heavy suites remain individually slower because `--workers` parallelizes across suite selectors, not within a single suite:
  - `Status`: `12.98s`
  - `MergeDown`: `8.31s`
  - `NestedSubproject`: `8.14s`
  - `Clone`: `6.74s`
  - `Publish`: `5.54s`
  - `GrapeUp`: `4.63s`
  - `CO`: `3.80s`

Notes:
- This phase achieves the first measured end-to-end win only when parallel mode is used.
- The serial regression is expected because the pytest-native scenario layer still rebuilds expensive workspace state per test case.
- Phase 4 and Phase 5 should target that repeated setup cost directly so the default path can recover, not just the parallel path.

### Phase 4
Status: complete

What changed:
- Replaced the per-test bootstrap sequence in [`test/testGrape.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testGrape.py) with a process-local seeded template.
- The seeded template now contains:
  - a bare origin
  - a working repo clone
  - the initial committed file
  - `master` and `develop` already pushed
- Each test now copies the prepared origin and working repo into its own temp workspace and retargets `origin` locally instead of re-running repository creation from scratch.

Measured impact:
- Serial full suite after Phase 4: `40.84s`, return code `1`.
- Parallel full suite after Phase 4: `31.55s` with `./grape test --workers=4`, return code `1`.
- Net change vs baseline:
  - serial: `-3.91s`
  - parallel: `-13.20s`
- Net change vs Phase 3:
  - serial: `-23.93s`
  - parallel: `-11.08s`
- Heavy suites after Phase 4:
  - `Status`: `10.47s`
  - `MergeDown`: `7.36s`
  - `NestedSubproject`: `7.35s`
  - `Clone`: `6.07s`
  - `Publish`: `4.86s`
  - `GrapeUp`: `3.71s`
  - `CO`: `3.73s`

Notes:
- An initial concurrent measurement attempt produced invalid numbers and was discarded.
- Accepted Phase 4 timings were rerun sequentially with the measurement script to avoid resource contention.

### Phase 5
Status: complete

What changed:
- Updated [`test/gridTesting.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/gridTesting.py) so each scenario instance creates a snapshot root once and later restores that prepared tree instead of replaying its entire command list on every reset.
- Limited path rewriting during snapshot restore to the files that actually carry absolute paths:
  - `.grapeconfig`
  - `.gitmodules`
  - git `config` files inside `.git`
- Updated [`test/testWorkspaceScenarios.py`](/usr/WS1/probinso/git/grape_workspaces/grape/test/testWorkspaceScenarios.py) so the parametrized tests share one scenario-object pool, allowing the snapshot cache to be reused across `Status` and `GrapeUp` cases.

Measured impact:
- Serial full suite after Phase 5: `38.29s`, return code `1`.
- Worker matrix after Phase 5:
  - `--workers=4`: `30.76s`
  - `--workers=8`: `31.74s`
  - `--workers=16`: `31.84s`
  - `--workers=32`: `31.78s`
  - `--workers=64`: `32.96s`
- Best current full-suite point: `30.76s` at `--workers=4`.
- Net change vs baseline:
  - serial: `-6.46s`
  - best parallel: `-13.99s`
- Net change vs Phase 4:
  - serial: `-2.55s`
  - best parallel: `-0.79s`
- Heavy suites after Phase 5:
  - `Status`: `9.54s`
  - `MergeDown`: `7.72s`
  - `NestedSubproject`: `7.76s`
  - `Clone`: `6.60s`
  - `Publish`: `5.52s`
  - `GrapeUp`: `3.95s`
  - `CO`: `3.85s`

Notes:
- Early Phase 5 measurements were invalid because they were taken while multiple timing jobs were running concurrently; only the sequential reruns are recorded above.
- The first snapshot implementation also underperformed because scenario objects were not being reused across parametrized tests. That was fixed before the accepted timings were recorded.

### Phase 6
Status: complete

What changed:
- Replaced the single Linux test template in [.gitlab/test_LC.yml](/usr/WS1/probinso/git/grape_workspaces/grape/.gitlab/test_LC.yml) with four shard templates:
  - `fast_core`
  - `git_workflow`
  - `workspace_topology`
  - `publish`
- Replaced the single MR and merge-train Linux jobs in [.gitlab-ci.yml](/usr/WS1/probinso/git/grape_workspaces/grape/.gitlab-ci.yml) with four shard jobs for merge-request pipelines and four shard jobs for merge-train pipelines.
- The non-publish shards use `./grape test --workers=4 ...`, which is the current best local worker count on this machine.
- The `Publish` shard remains isolated and serial so its known failures do not distort the other shard timings.

Measured impact:
- Local full-suite timings are unchanged from Phase 5 because this phase changes CI topology, not the test runner.
- Local shard timings used as the CI critical-path estimate:
  - `fast_core`: `4.96s`
  - `git_workflow`: `8.28s`
  - `workspace_topology`: `15.47s`
  - `publish`: `4.88s`, return code `1`
- Estimated Linux CI critical path: `15.47s` plus runner queue/startup overhead.

Notes:
- YAML for both [.gitlab-ci.yml](/usr/WS1/probinso/git/grape_workspaces/grape/.gitlab-ci.yml) and [.gitlab/test_LC.yml](/usr/WS1/probinso/git/grape_workspaces/grape/.gitlab/test_LC.yml) was validated locally with `yaml.safe_load(...)`.
- The `workspace_topology` shard is the current pacing item for Linux CI.

### Phase 7
Status: complete

What changed:
- Extended [`vine/grapeTest.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/grapeTest.py) with:
  - `--changed`
  - `--base=<ref>`
  - default worker selection logic for broad runs
- Extended [`vine/test_suites.py`](/usr/WS1/probinso/git/grape_workspaces/grape/vine/test_suites.py) with suite-to-path watch lists and shared-path handling for broad runner changes.
- Updated [`tools/measure_grape_tests.py`](/usr/WS1/probinso/git/grape_workspaces/grape/tools/measure_grape_tests.py) so `--workers=1` can be measured explicitly now that the CLI default is no longer serial.

Behavior changes:
- Broad runs now default to `4` workers when `--workers` is omitted.
- Single explicit suite selectors stay serial by default.
- `--debug` still forces serial execution.
- `--changed` uses the union of:
  - `git diff <base>...HEAD`
  - staged changes
  - unstaged changes
- Explicit suite selectors take precedence over `--changed`.
- Docs-only and CI-only diffs map to no suites and exit successfully with a message.

Measured impact:
- Serial full suite after Phase 7: `38.42s` with `--workers=1`, return code `1`.
- Default full suite after Phase 7: `30.68s`, return code `1`.
- Worker matrix after Phase 7:
  - `--workers=4`: `30.64s`
  - `--workers=8`: `31.49s`
  - `--workers=16`: `31.86s`
  - `--workers=32`: `31.99s`
  - `--workers=64`: `31.94s`
- Best current full-suite point: `30.64s` at `--workers=4`.
- Net change vs baseline:
  - serial: `-6.33s`
  - best parallel/default broad run: `-14.11s`
- Net change vs Phase 6:
  - serial: `+0.13s`
  - best parallel: `-0.12s`

Notes:
- `./grape test` now effectively lands on the best measured broad-run worker count on this machine.
- Verified `test_suites.select_suites_for_changed_paths(['docs/test-performance-plan.md', '.gitlab-ci.yml']) == []`.
