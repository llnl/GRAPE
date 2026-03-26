# Grape Test Performance Handoff

## Current State
- Goal: make root-suite testing faster for both local development and Linux CI.
- Current phase: complete
- Latest baseline commit before speed changes: `8e30d114`
- Original full-suite timing: `44.75s`
- Original known failures: `Publish` suite
- Latest accepted post-phase timing:
  - serial full suite `38.42s` with `--workers=1`, return code `1`
  - default broad-run full suite `30.68s`, return code `1`
  - best explicit worker run `30.64s` with `--workers=4`, return code `1`
  - worker matrix:
    - `--workers=4`: `30.64s`
    - `--workers=8`: `31.49s`
    - `--workers=16`: `31.86s`
    - `--workers=32`: `31.99s`
    - `--workers=64`: `31.94s`

## Current Runner Architecture
- Public entrypoint: `vine/grapeTest.py`
- Current implementation routes `grape test` through `pytest.main(...)`
- Suite alias metadata lives in `vine/test_suites.py`
- `Status` and `GrapeUp` now run through pytest-native parametrized tests in `test/testWorkspaceScenarios.py`
- `grape test --workers=<n>` parallelizes across suite selectors by launching subprocess pytest runs
- Plain `./grape test` defaults to 4 workers for broad runs
- `grape test --changed [--base=<ref>]` maps changed files to suite aliases using `vine/test_suites.py`
- `Publish` is marked serial and stays out of the parallel lane
- Common test setup in `test/testGrape.py` now copies a seeded process-local bootstrap template instead of rebuilding the initial repo from scratch
- Heavy scenario restore now snapshots prepared state in `test/gridTesting.py` and reuses that state across the pytest scenario matrix in `test/testWorkspaceScenarios.py`

## Baseline Numbers
- Full suite: `44.75s`, return code `1`
- Heavy suites:
  - `Status`: `12.00s`
  - `MergeDown`: `7.32s`
  - `NestedSubproject`: `6.91s`
  - `Clone`: `5.71s`
  - `Publish`: `5.12s`, return code `1`
  - `GrapeUp`: `4.35s`
  - `CO`: `3.03s`

## Latest Accepted Numbers
- Full suite serial: `38.42s`, return code `1`
- Full suite default broad run: `30.68s`, return code `1`
- Full suite with `--workers=4`: `30.64s`, return code `1`
- Full suite with `--workers=8`: `31.49s`, return code `1`
- Full suite with `--workers=16`: `31.84s`, return code `1`
- Full suite with `--workers=32`: `31.99s`, return code `1`
- Full suite with `--workers=64`: `31.94s`, return code `1`
- Heavy suites:
  - `Status`: `9.54s`
  - `MergeDown`: `7.72s`
  - `NestedSubproject`: `7.76s`
  - `Clone`: `6.60s`
  - `Publish`: `5.52s`, return code `1`
  - `GrapeUp`: `3.95s`
  - `CO`: `3.85s`
- Local CI-shard timing proxy:
  - `fast_core`: `4.96s`
  - `git_workflow`: `8.28s`
  - `workspace_topology`: `15.47s`
  - `publish`: `4.88s`, return code `1`

## Reproduction Commands
- Full suite: `./grape test`
- Full suite parallel: `./grape test --workers=4`
- Full suite parallel: `./grape test --workers=8`
- Full suite parallel: `./grape test --workers=16`
- Full suite parallel: `./grape test --workers=32`
- Full suite parallel: `./grape test --workers=64`
- All suite timings: `python3 tools/measure_grape_tests.py --mode all`
- Heavy suite timings only: `python3 tools/measure_grape_tests.py --mode heavy`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 4`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 8`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 16`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 32`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 64`
- List current suite aliases: `./grape test listSuites`

## Constraints And Decisions
- Scope is only the root `test/` suite.
- Vendored suites remain excluded from root test execution.
- Keep `grape test` as the public command.
- End every phase with:
  - updated docs
  - refreshed measurements
  - a git commit with subject prefixed `PHASE <number>:`
- Avoid assuming `pytest-xdist`; use process-parallel strategies that work with stock `pytest`.
- Phase 2 already landed the public runner migration, so future work should improve speed without breaking alias compatibility.
- Phase 3 landed `--workers`, but the default serial path is still too slow to leave as-is.
- Phase 4 recovered the default serial path below the original baseline by caching the shared bootstrap repo.
- Phase 5 keeps the worker matrix in the progress log; the current best point is `--workers=4`, and higher worker counts do not help on this machine.
- Phase 6 shards Linux CI around the measured suite groups; `workspace_topology` is now the expected critical-path shard.
- Phase 7 makes the broad-run default match the best measured worker count and adds changed-suite targeting.

## Next Recommended Step
- If more speed is needed, investigate why `MergeDown`, `NestedSubproject`, and `Clone` remain the dominant suites after the shared setup and scenario caching work.
- Keep the worker matrix (`4/8/16/32/64`) in the progress doc for later runner changes.
