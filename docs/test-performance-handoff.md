# Grape Test Performance Handoff

## Current State
- Goal: make root-suite testing faster for both local development and Linux CI.
- Current phase: Phase 10 complete
- Latest baseline commit before speed changes: `8e30d114`
- Original full-suite timing: `44.75s`
- Original known failures: `Publish` suite
- Latest accepted post-phase timing:
  - accepted external broad-run timing on `rzwhippet3`: about `11.72s` with `--workers=29`, all listed suites returned `0`
  - the split publish layout now yields `29` default broad-run selectors, so no-flag broad runs will also default to `29` workers on that suite set
  - local sandbox timing remained materially slower and should not be used as the accepted comparison point for this phase
  - worker matrix:
    - `--workers=4`: `27.29s` on the pre-split Phase 9 layout
    - `--workers=8`: `29.44s` on the pre-split Phase 9 layout
    - `--workers=16`: `29.59s` on the pre-split Phase 9 layout
    - `--workers=32`: `30.05s` on the pre-split Phase 9 layout
    - `--workers=64`: `30.60s` on the pre-split Phase 9 layout
    - `--workers=29`: `11.72s` on `rzwhippet3` with the split publish layout

## Current Runner Architecture
- Public entrypoint: `vine/grapeTest.py`
- Current implementation routes `grape test` through `pytest.main(...)`
- Suite alias metadata lives in `vine/test_suites.py`
- Broad-run launch priority is defined in `test/suite_order.txt`
- ASCII schedule rendering lives in `tools/render_timing_chart.py`
- `Status` and `GrapeUp` now run through pytest-native parametrized tests in `test/testWorkspaceScenarios.py`
- Publish coverage is now split across the `test/publish/` package for broad-run scheduling, while `Publish` remains as an aggregate user-facing alias
- `grape test --workers=<n>` parallelizes across suite selectors by launching subprocess pytest runs
- Plain `./grape test` now defaults to one worker per selected suite for broad runs
- Plain interactive `./grape test` keeps the broad-run chart live in place in the terminal
- The live broad-run chart starts from a `15s` time window and renormalizes upward as needed
- `grape -d test` keeps the static one-shot summary so CI logs stay readable
- `grape test --changed [--base=<ref>]` maps changed files to suite aliases using `vine/test_suites.py`
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
- Accepted broad run on `rzwhippet3`: about `11.72s` with `--workers=29`, all listed suites returned `0`
- Reference Phase 9 local matrix:
  - `--workers=4`: `27.29s`, return code `1`
  - `--workers=8`: `29.44s`, return code `1`
  - `--workers=16`: `29.59s`, return code `1`
  - `--workers=32`: `30.05s`, return code `1`
  - `--workers=64`: `30.60s`, return code `1`
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
- Non-interactive broad run: `./grape -d test`
- Full suite broad run matching the current default suite count: `./grape test --workers=29`
- Full suite parallel: `./grape test --workers=4`
- Full suite parallel: `./grape test --workers=8`
- Full suite parallel: `./grape test --workers=16`
- Full suite parallel: `./grape test --workers=32`
- Full suite parallel: `./grape test --workers=64`
- Standalone chart rendering: `python3 tools/render_timing_chart.py --width 60 < timings.json`
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
- Phase 8 adds live broad-run schedule visibility plus a repo-owned suite-order file for hand-tuned overlap.
- Phase 9 relaxes the serial-lane scheduling rule so `Publish` can overlap the normal worker lane instead of waiting until the end.
- Phase 10 splits publish into shardable broad-run suites and switches the broad default worker count to the number of selected suites.

## Next Recommended Step
- If more speed is needed, investigate why `MergeDown`, `NestedSubproject`, and `Clone` remain the dominant suites after the shared setup and scenario caching work.
- Keep the worker matrix (`4/8/16/32/64`) in the progress doc for later runner changes.
- If schedule overlap needs tuning, edit `test/suite_order.txt` first before changing worker counts or runner code.
- If the host topology matters, keep recording host-specific measurements separately; the `rzwhippet3` result suggests this runner benefits from a much wider process fan-out than the sandbox host used during development.
