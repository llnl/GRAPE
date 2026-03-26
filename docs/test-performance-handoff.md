# Grape Test Performance Handoff

## Current State
- Goal: make root-suite testing faster for both local development and Linux CI.
- Current phase: 5
- Latest baseline commit before speed changes: `8e30d114`
- Original full-suite timing: `44.75s`
- Original known failures: `Publish` suite
- Latest accepted post-phase timing:
  - serial full suite `40.84s`, return code `1`
  - parallel full suite `31.55s` with `--workers=4`, return code `1`

## Current Runner Architecture
- Public entrypoint: `vine/grapeTest.py`
- Current implementation routes `grape test` through `pytest.main(...)`
- Suite alias metadata lives in `vine/test_suites.py`
- `Status` and `GrapeUp` now run through pytest-native parametrized tests in `test/testWorkspaceScenarios.py`
- `grape test --workers=<n>` parallelizes across suite selectors by launching subprocess pytest runs
- `Publish` is marked serial and stays out of the parallel lane
- Common test setup in `test/testGrape.py` now copies a seeded process-local bootstrap template instead of rebuilding the initial repo from scratch
- Heavy scenario replay logic lives in `test/gridTesting.py` and `test/testProjectScenarios.py`

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
- Full suite serial: `40.84s`, return code `1`
- Full suite with `--workers=4`: `31.55s`, return code `1`
- Heavy suites:
  - `Status`: `10.47s`
  - `MergeDown`: `7.36s`
  - `NestedSubproject`: `7.35s`
  - `Clone`: `6.07s`
  - `Publish`: `4.86s`, return code `1`
  - `GrapeUp`: `3.71s`
  - `CO`: `3.73s`

## Reproduction Commands
- Full suite: `./grape test`
- Full suite parallel: `./grape test --workers=4`
- All suite timings: `python3 tools/measure_grape_tests.py --mode all`
- Heavy suite timings only: `python3 tools/measure_grape_tests.py --mode heavy`
- Full suite timing with workers: `python3 tools/measure_grape_tests.py --mode full --workers 4`
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

## Next Recommended Step
- Snapshot the heavy scenario setup in `test/gridTesting.py` and `test/testProjectScenarios.py` so `Status` and `GrapeUp` stop replaying full command lists for every parametrized case.
- Keep `grape test --workers=4` as the comparison point while reducing the remaining serial scenario overhead.
