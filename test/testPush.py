import logging
from unittest.mock import patch

from vine import push as push_module


def default_push_args(quiet_remote_messages=False):
    """Builds parsed grape push args for push option tests.

    Args:
        quiet_remote_messages (bool): Whether remote messages should be
            suppressed by the push option.

    Returns:
        dict: Parsed grape push option values used by Push.execute().
    """
    return {
        "--noRecurse": False,
        "--noRecurseSubprojects": False,
        "--noTopLevel": False,
        "--pushAll": False,
        "--quietRemoteMessages": quiet_remote_messages,
    }


def test_gitlab_merge_request_urls_extracts_create_mr_links():
    """Verifies GitLab create-MR URLs are extracted from remote output."""
    output = """
remote:
remote: To create a merge request for feature/test, visit:
remote:   https://example.invalid/group/repo/-/merge_requests/new?merge_request%5Bsource_branch%5D=feature%2Ftest
remote:
remote: Create a merge request for master:
remote:   https://example.invalid/group/other/-/merge_requests/new
"""

    assert push_module.gitlabMergeRequestUrls(output) == [
        "https://example.invalid/group/repo/-/merge_requests/new?merge_request%5Bsource_branch%5D=feature%2Ftest",
        "https://example.invalid/group/other/-/merge_requests/new",
    ]


def test_push_execute_summarizes_gitlab_merge_request_hints(tmp_path, caplog):
    """Verifies grape push summarizes GitLab MR hints after multi-repo pushes."""
    (tmp_path / ".git").mkdir()
    gitlab_hint_1 = """
remote:
remote: To create a merge request for feature/test, visit:
remote:   https://example.invalid/group/repo/-/merge_requests/new?merge_request%5Bsource_branch%5D=feature%2Ftest
"""
    gitlab_hint_2 = """
remote: informational policy message
remote:
remote: To create a merge request for feature/test, visit:
remote:   https://example.invalid/group/other/-/merge_requests/new?merge_request%5Bsource_branch%5D=feature%2Ftest
"""

    with patch("vine.push.multi_repo_cmd_launcher.MultiRepoCommandLauncher") as launcher_cls:
        launcher = launcher_cls.return_value
        launcher.launchFromWorkspaceDir.return_value = [
            push_module.PushResult(True, "/workspace/repo", "feature/test", gitlab_hint_1),
            push_module.PushResult(True, "/workspace/other", "feature/test", gitlab_hint_2),
        ]

        caplog.set_level(logging.INFO)
        option = push_module.Push()
        option.workspace_dir = str(tmp_path)

        assert option.execute(default_push_args()) is True

    logs = caplog.text
    assert "remote: informational policy message" in logs
    assert "GitLab reported merge request creation links for 2 pushed repos." in logs
    assert "Run grape review to create or update merge requests for this workspace:" in logs
    assert "  grape review" in logs
    assert "To create a merge request" not in logs
    assert "https://example.invalid" not in logs
    assert launcher_cls.call_args.kwargs["globalArgs"]["_accumulateRemoteMessages"] is True
    launcher.launchFromWorkspaceDir.assert_called_once_with(
        handleMRE=push_module.handlePushMRE)


def test_push_execute_quiet_suppresses_gitlab_review_hint(tmp_path, caplog):
    """Verifies quiet remote-message mode suppresses the grape review hint."""
    (tmp_path / ".git").mkdir()
    gitlab_hint = """
remote: To create a merge request for feature/test, visit:
remote:   https://example.invalid/group/repo/-/merge_requests/new
"""

    with patch("vine.push.multi_repo_cmd_launcher.MultiRepoCommandLauncher") as launcher_cls:
        launcher = launcher_cls.return_value
        launcher.launchFromWorkspaceDir.return_value = [
            push_module.PushResult(True, "/workspace/repo", "feature/test", gitlab_hint),
        ]

        caplog.set_level(logging.INFO)
        option = push_module.Push()
        option.workspace_dir = str(tmp_path)

        assert option.execute(default_push_args(quiet_remote_messages=True)) is True

    logs = caplog.text
    assert "GitLab reported merge request creation links" not in logs
    assert "grape review" not in logs
    assert launcher_cls.call_args.kwargs["globalArgs"]["_accumulateRemoteMessages"] is False


@patch("vine.push.git.push")
def test_push_accumulates_remote_messages_by_quieting_git_push(mock_git_push):
    """Verifies push collection keeps git.push from logging remote lines early."""
    mock_git_push.return_value = "remote: To create a merge request for feature/test, visit:"
    args = {
        "--pushAll": True,
        "--quietRemoteMessages": False,
        "_accumulateRemoteMessages": True,
    }

    result = push_module.push(
        repo="/workspace/repo",
        branch="feature/test",
        args=args,
        workspace_dir="/workspace")

    assert result.pushed is True
    assert result.output == "remote: To create a merge request for feature/test, visit:"
    mock_git_push.assert_called_once_with(
        "-u origin feature/test",
        throwOnFail=True,
        quietRemoteMessages=True,
        execution_path="/workspace/repo")
