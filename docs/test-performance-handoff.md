# Grape Test Performance Handoff

## Current State
- Goal: make root-suite testing faster for both local development and Linux CI.
- Current phase: 3
- Latest baseline commit before speed changes: `8e30d114`
- Original full-suite timing: `44.75s`
- Original known failures: `Publish` suite
- Latest accepted post-phase timing: full suite `48.51s`, return code `1`

## Current Runner Architecture
- Public entrypoint: `vine/grapeTest.py`
- Current implementation routes `grape test` through `pytest.main(...)`
- Suite alias metadata lives in `vine/test_suites.py`
- `Status` and `GrapeUp` are dynamically generated through `gridTesting.gridifyTestClass`
- `Status` and `GrapeUp` are currently made pytest-visible through thin subclasses in their modules
- Common test setup cost lives in `test/testGrape.py`
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
- Full suite: `48.51s`, return code `1`
- Heavy suites:
  - `Status`: `11.89s`
  - `MergeDown`: `7.72s`
  - `NestedSubproject`: `7.89s`
  - `Clone`: `6.72s`
  - `Publish`: `5.54s`, return code `1`
  - `GrapeUp`: `4.36s`
  - `CO`: `3.70s`

## Reproduction Commands
- Full suite: `./grape test`
- All suite timings: `python3 tools/measure_grape_tests.py --mode all`
- Heavy suite timings only: `python3 tools/measure_grape_tests.py --mode heavy`
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

## Next Recommended Step
- Replace the dynamically generated `Status` and `GrapeUp` unittest collection with pytest parametrization.
- Add marker-based grouping so later phases can split serial and parallel-safe work cleanly.
