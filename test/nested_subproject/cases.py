import logging
import os
from unittest.mock import patch

from test import testGrape
from vine import grape_errors
from vine import grapeGit as git


class NestedSubprojectTopologyCase:
    """Topology and checkout coverage for nested-subproject workspaces."""

    def testAddingNewNestedSubproject(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
        except grape_errors.GrapeGitError as exc:
            self.fail(self.get_output() + exc.gitCommand)

    def testSwitchingBranchesWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            git.branch("newBranch", execution_path=self.repo)
            git.branch("newBranch", execution_path=self.subproject)
            self.menu.applyMenuChoice("checkout", ["newBranch"])
            self.assertEqual(
                git.currentBranch(execution_path=self.repo),
                "newBranch",
                "outer level repo not on newBranch after checkout",
            )
            self.assertEqual(
                git.currentBranch(execution_path=self.subproject),
                "newBranch",
                "subproject not on newBranch after checkout",
            )
        except grape_errors.GrapeGitError as exc:
            self.fail(self.get_output() + exc.gitCommand.split()[-10:])


class NestedSubprojectWorkspaceSyncCase:
    """Lifecycle coverage that adds a second workspace and resynchronizes it."""

    @patch("vine.utility.userInput")
    def testDeactivatingAndReactivatingNestProjects(self, mock_userInput):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            self.assertTrue(os.path.isdir(self.subproject))
            mock_userInput.side_effect = ["n\n", "y\n"]
            self.menu.applyMenuChoice("uv")
            self.assertFalse(os.path.isdir(self.subproject))
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject), "\n".join(self.get_output()))
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject))

            second_space = os.path.join(self.defaultWorkingDirectory, "client2")
            args = [self.repo, second_space]
            cwd = os.getcwd()
            mock_userInput.side_effect = ["\n", "y\n", "a\n", "\n", "\n"]
            ret = self.menu.applyMenuChoice("clone", args)
            os.chdir(cwd)

            self.resetMenu(second_space)
            mock_userInput.side_effect = ["y", "\n", "\n"]
            ret = self.menu.applyMenuChoice("checkout", ["master"])
            self.assertTrue(ret, "vine.clone returned failure")
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")

            self.resetMenu(self.repo)
            self.assertCanAddSecondSubproject(self, execution_path=self.repo)
            self.assertCanRemoveFirstSubproject(self, execution_path=self.repo)

            self.resetMenu(second_space)
            mock_userInput.side_effect = ["n\n"]
            self.menu.applyMenuChoice("uv", ["-f", "-F"])
            git.pull("origin master", execution_path=second_space)
            self.resetMenu(second_space)
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv", ["-f", "-F"])
            self.assertFalse(
                os.path.isdir(os.path.join(second_space, "subs", "subproject1")),
                "subproject1 should not be present",
            )
            self.assertTrue(
                os.path.isdir(os.path.join(second_space, "subs", "subproject2")),
                "subproject2 should be present",
            )
        except grape_errors.GrapeGitError as exc:
            output = self.get_output()
            self.fail(("\n".join(output) + exc.gitCommand).split()[-10:])


class NestedSubprojectProjectCommandsCase:
    """Project-wide status and commit checks for nested workspaces."""

    def testProjectWideGrapeStatusWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            f1_path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1_path)
            self.assertTrue(
                git.isWorkingDirectoryClean(execution_path=self.repo),
                f"{os.path.join('subproject1', 'f1')} shows up in git status when it shouldn't",
            )
            logging.critical("STARTING applyMenuChoice")
            self.menu.applyMenuChoice("status", ["-u"])
            logging.critical("FINISHED applyMenuChoice")
            actual_output = self.get_output()
            subproject_path = os.path.join("subs", "subproject1", "f1")
            logging.critical("STARTING assertIn")
            self.assertIn(
                f" ?? {subproject_path}",
                actual_output,
                f"{subproject_path} does not show up in grape status",
            )
            logging.critical("FINISHED assertIn")
        except grape_errors.GrapeGitError as exc:
            output = self.get_output()
            self.fail("\n".join([output, exc.gitCommand]))

    def testProjectWideGrapeCommitWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            f1_path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1_path)
            git.add(f1_path, execution_path=self.subproject)
            first_status = git.status("--porcelain", execution_path=self.subproject)
            self.assertTrue("f1" in first_status)
            self.menu.applyMenuChoice("commit", ["-m", "\"adding f1\""])
            second_status = git.status("--porcelain", execution_path=self.subproject)
            self.assertTrue("f1" not in second_status, "commit didn't remove f1 from status")
        except grape_errors.GrapeGitError as exc:
            output = self.get_output()
            self.fail(("\n".join(output) + exc.gitCommand).split()[-10:])
