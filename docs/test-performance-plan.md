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
