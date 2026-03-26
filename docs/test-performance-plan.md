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
| Date | Phase | Full Suite (s) | Heavy Suites Summary | Delta vs Baseline | Delta vs Previous | Commit |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 2026-03-26 | Baseline | 44.75 | Status 12.00, MergeDown 7.32, NestedSubproject 6.91, Clone 5.71, Publish 5.12, GrapeUp 4.35, CO 3.03 | 0.00 | 0.00 | `8e30d114` |
| 2026-03-26 | Phase 2 | 48.51 | Status 11.89, MergeDown 7.72, NestedSubproject 7.89, Clone 6.72, Publish 5.54, GrapeUp 4.36, CO 3.70 | +3.76 | +3.76 | `fd996b72` |
| 2026-03-26 | Phase 3 | 64.77 serial, 42.63 with `--workers=4` | Status 12.98, MergeDown 8.31, NestedSubproject 8.14, Clone 6.74, Publish 5.54, GrapeUp 4.63, CO 3.80 | -2.12 in parallel mode | -5.88 in parallel mode | `6daa0f32` |
| 2026-03-26 | Phase 4 | 40.84 serial, 31.55 with `--workers=4` | Status 10.47, MergeDown 7.36, NestedSubproject 7.35, Clone 6.07, Publish 4.86, GrapeUp 3.71, CO 3.73 | -13.20 in parallel mode | -11.08 in parallel mode | `pending phase 4 commit` |

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
