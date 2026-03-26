# Grape Test Performance Handoff

## Current State
- Goal: make root-suite testing faster for both local development and Linux CI.
- Current phase: 2
- Latest baseline commit before speed changes: `8e30d114`
- Original full-suite timing: `44.75s`
- Original known failures: `Publish` suite

## Current Runner Architecture
- Public entrypoint: `vine/grapeTest.py`
- Current implementation calls the custom `unittest` aggregator in `test/testGrape.py`
- `test/testGrape.py` builds suites manually and runs them serially with `unittest.TextTestRunner`
- `Status` and `GrapeUp` are dynamically generated through `gridTesting.gridifyTestClass`
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

## Next Recommended Step
- Introduce a pytest-backed compatibility layer behind `grape test`.
- Preserve existing suite aliases and `<Suite>.<test>` selection while adding new runner flags.
