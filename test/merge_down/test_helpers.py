from unittest.mock import patch

from vine import mergeDown


@patch("vine.mergeDown.checkout.applyMovedSubmodules")
def test_reconcile_moved_submodules_maps_active_paths(mock_apply_moved):
    mock_apply_moved.return_value = ({"old/sub": "new/sub"}, {})

    moved_active, moved_submodules = mergeDown.reconcileMovedSubmodules(
        {"old/sub": "new/sub"},
        ["old/sub", "unchanged/sub"],
        ["old/sub", "other/sub"],
        workspace_dir="/tmp/workspace",
    )

    assert moved_active == ["new/sub", "unchanged/sub"]
    assert moved_submodules == ["new/sub", "other/sub"]


@patch("vine.mergeDown.checkout.applyMovedSubmodules")
def test_reconcile_moved_submodules_returns_none_on_failure(mock_apply_moved):
    mock_apply_moved.return_value = ({}, {"old/sub": "new/sub"})

    moved = mergeDown.reconcileMovedSubmodules(
        {"old/sub": "new/sub"},
        ["old/sub"],
        ["old/sub"],
        workspace_dir="/tmp/workspace",
    )

    assert moved is None


def test_remap_moved_submodule_paths_deduplicates_moved_entries():
    moved = mergeDown.remapMovedSubmodulePaths(
        ["old/sub", "new/sub", "unchanged/sub"],
        {"old/sub": "new/sub"},
    )

    assert moved == ["new/sub", "unchanged/sub"]


def test_merge_submodule_candidates_includes_moved_active_submodules():
    merged = mergeDown.mergeSubmoduleCandidates(
        ["new/location/sub1", "new/location/sub2"],
        ["new/location/sub2", "new/location/sub3"],
    )

    assert merged == [
        "new/location/sub1",
        "new/location/sub2",
        "new/location/sub3",
    ]
