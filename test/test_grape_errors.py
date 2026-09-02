from unittest.mock import call
from unittest.mock import patch

from vine import grape_errors


def test_index_lock_log_error_includes_context_and_git_details():
    error = grape_errors.GrapeGitIndexLockError(
        gitOutput="Unable to create '/tmp/repo/.git/index.lock': File exists.",
        gitCommand="git fetch origin",
        cwd="/tmp/repo",
        indexLockPath="/tmp/repo/.git/index.lock",
    )

    with patch("vine.grape_errors.logging.error") as log_error:
        error.LogError("fetch in /tmp/repo")

    log_error.assert_has_calls([
        call(
            "Index Lock during fetch in /tmp/repo: git index is locked at "
            "/tmp/repo/.git/index.lock."),
        call("Git command: git fetch origin"),
        call("Working directory: /tmp/repo"),
        call("Unable to create '/tmp/repo/.git/index.lock': File exists."),
    ])
