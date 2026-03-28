from unittest import TestCase
from unittest.mock import MagicMock, patch

from vine import pull


class TestPull(TestCase):

    @patch("vine.pull.Pull.set_progress_file")
    @patch("vine.grapeMenu.menu")
    @patch("vine.pull.git.remoteBranches")
    @patch("vine.pull.git.fetch")
    @patch("vine.pull.git.currentBranch")
    def testPullFetchesBeforeTreatingBranchAsLocalOnly(
            self, mock_current_branch, mock_fetch, mock_remote_branches,
            mock_menu, mock_set_progress_file):
        mock_current_branch.return_value = "topic/test"
        mock_remote_branches.side_effect = [
            [],
            ["origin/topic/test"],
        ]
        mock_option = MagicMock()
        mock_option.execute.return_value = True
        mock_menu.return_value.getOption.return_value = mock_option

        command = pull.Pull()
        command._workspace_dir = "/tmp/workspace"

        ret = command.execute({"--continue": False, "--noRecurse": False})

        self.assertTrue(ret)
        mock_fetch.assert_called_once_with("origin",
                                           execution_path="/tmp/workspace")
        mock_option.execute.assert_called_once()

    @patch("vine.pull.logging.info")
    @patch("vine.pull.Pull.set_progress_file")
    @patch("vine.pull.git.remoteBranches")
    @patch("vine.pull.git.fetch")
    @patch("vine.pull.git.currentBranch")
    def testPullLogsAndReturnsWhenBranchStillMissingAfterFetch(
            self, mock_current_branch, mock_fetch, mock_remote_branches,
            mock_set_progress_file, mock_info):
        mock_current_branch.return_value = "topic/test"
        mock_remote_branches.side_effect = [
            [],
            [],
        ]

        command = pull.Pull()
        command._workspace_dir = "/tmp/workspace"

        ret = command.execute({"--continue": False, "--noRecurse": False})

        self.assertTrue(ret)
        mock_fetch.assert_called_once_with("origin",
                                           execution_path="/tmp/workspace")
        mock_info.assert_called_once_with(
            "No remote reference to topic/test in origin. "
            "You may want to push this branch.")
