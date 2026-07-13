import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from vine import grape_errors
from vine import grapeGit
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


def test_handle_index_lock_error_defaults_to_not_removing_lock():
    """Verifies that the default index.lock prompt response preserves the lock."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = os.path.join(temp_dir, "index.lock")
        open(lock_path, "w").close()
        error = grape_errors.GrapeGitIndexLockError(
            gitOutput=f"Unable to create '{lock_path}': File exists.",
            cwd=temp_dir,
            indexLockPath=lock_path,
        )

        with patch("vine.mergeDown.utility.userInput", return_value=False) as user_input:
            removed = mergeDown.handleIndexLockError(error)

        assert removed is False
        assert os.path.exists(lock_path)
        user_input.assert_called_once()
        assert user_input.call_args[0][1] == "n"


def test_handle_index_lock_error_removes_lock_when_user_accepts():
    """Verifies that accepting the prompt removes the reported index.lock file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = os.path.join(temp_dir, "index.lock")
        open(lock_path, "w").close()
        error = grape_errors.GrapeGitIndexLockError(
            gitOutput=f"Unable to create '{lock_path}': File exists.",
            cwd=temp_dir,
            indexLockPath=lock_path,
        )

        with patch("vine.mergeDown.utility.userInput", return_value=True):
            removed = mergeDown.handleIndexLockError(error)

        assert removed is True
        assert not os.path.exists(lock_path)


def test_handle_index_lock_error_ignores_missing_lock_during_remove():
    """Verifies that a disappearing index.lock does not crash recovery."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = os.path.join(temp_dir, "index.lock")
        error = grape_errors.GrapeGitIndexLockError(
            gitOutput=f"Unable to create '{lock_path}': File exists.",
            cwd=temp_dir,
            indexLockPath=lock_path,
        )

        with patch("vine.mergeDown.utility.userInput", return_value=True), \
                patch("vine.mergeDown.os.path.isfile", return_value=True), \
                patch("vine.mergeDown.os.remove",
                      side_effect=FileNotFoundError):
            removed = mergeDown.handleIndexLockError(error)

        assert removed is False


def test_handle_index_lock_error_warns_on_permission_error():
    """Verifies that permission failures are reported without crashing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = os.path.join(temp_dir, "index.lock")
        error = grape_errors.GrapeGitIndexLockError(
            gitOutput=f"Unable to create '{lock_path}': File exists.",
            cwd=temp_dir,
            indexLockPath=lock_path,
        )

        with patch("vine.mergeDown.utility.userInput", return_value=True), \
                patch("vine.mergeDown.os.path.isfile", return_value=True), \
                patch("vine.mergeDown.os.remove",
                      side_effect=PermissionError), \
                patch("vine.mergeDown.logging.warning") as warning:
            removed = mergeDown.handleIndexLockError(error)

        assert removed is False
        warning.assert_any_call(
            f"Could not remove {lock_path}: permission denied.")


def test_merge_retries_after_removing_index_lock():
    """Verifies that merge-down retries once after handling an index.lock error."""
    error = grape_errors.GrapeGitIndexLockError(
        gitOutput="Unable to create '/tmp/repo/.git/index.lock': File exists.",
        gitCommand="git merge develop",
        indexLockPath="/tmp/repo/.git/index.lock",
    )
    args = {
        "--squash": False,
        "--at": False,
        "--ay": False,
    }

    with patch("vine.mergeDown.git.merge", side_effect=[error, ""]), \
            patch("vine.mergeDown.handleIndexLockError", return_value=True) as handle_lock:
        assert mergeDown.merge("develop", "", args, execution_path="/tmp/repo") is True

    handle_lock.assert_called_once_with(error)


def test_gitcmd_raises_index_lock_error_with_lock_path():
    """Verifies that gitcmd raises the typed error with git's reported path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = os.path.join(temp_dir, ".git", "index.lock")
        completed_process = SimpleNamespace(
            returncode=128,
            stdout=b"",
            stderr=f"fatal: Unable to create '{lock_path}': File exists.".encode(),
        )
        config = SimpleNamespace(has_section=lambda section: False)

        with patch("vine.config_parser_global.grapeConfig", return_value=config), \
                patch("vine.grapeGit.vine_subprocess.executeSubProcess",
                      return_value=completed_process):
            try:
                grapeGit.gitcmd("merge develop", "merge failed",
                                execution_path=temp_dir)
            except grape_errors.GrapeGitIndexLockError as error:
                assert error.indexLockPath == lock_path
                assert error.gitCommand.endswith("merge develop")
            else:
                raise AssertionError("Expected GrapeGitIndexLockError")


def test_gitcmd_does_not_raise_index_lock_error_for_unrelated_index_lock_text():
    """Verifies that incidental index.lock text remains a plain git error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        completed_process = SimpleNamespace(
            returncode=128,
            stdout=b"",
            stderr=b"fatal: pathspec 'index.lock' did not match any files.",
        )
        config = SimpleNamespace(has_section=lambda section: False)

        with patch("vine.config_parser_global.grapeConfig", return_value=config), \
                patch("vine.grapeGit.vine_subprocess.executeSubProcess",
                      return_value=completed_process):
            try:
                grapeGit.gitcmd("checkout index.lock", "checkout failed",
                                execution_path=temp_dir)
            except grape_errors.GrapeGitIndexLockError:
                raise AssertionError("Expected plain GrapeGitError")
            except grape_errors.GrapeGitError:
                pass
            else:
                raise AssertionError("Expected GrapeGitError")
