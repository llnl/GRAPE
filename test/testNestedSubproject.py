__author__ = 'robinson96'
import os
import sys
import tempfile
from unittest.mock import patch
from test import testGrape
from vine import config_parser_base
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu
from vine.option import Option


class TestNestedSubproject(testGrape.TestGrape):

    # Sets up a second nested subproject referring to the first
    @staticmethod
    def assertCanAddSecondSubproject(testGrapeObject, *, execution_path):
        subproject_path = os.path.join('subs', 'subproject2')
        testGrapeObject.menu.applyMenuChoice(
            "addSubproject", ["--name=subproject2",
                              f"--prefix={subproject_path}", "--branch=master",
                              f"--url={testGrapeObject.repos[1]}",
                              "--nested", "--noverify"])
        subproject2path = os.path.join(testGrapeObject.repo, subproject_path)
        testGrapeObject.assertTrue(os.path.exists(subproject2path), "subproject2 does not exist")
        # check to see that subproject2 is a git repo
        basedir = os.path.split(git.baseDir(execution_path=subproject2path))[-1]
        subdir = os.path.split(subproject2path)[-1]
        testGrapeObject.assertEqual(basedir, subdir,
                                   f"subproject2's git repo is {basedir}, " +
                                   f"not {subdir}")
        testGrapeObject.subproject2 = subproject2path

    # Remove first nested subproject
    @staticmethod
    def assertCanRemoveFirstSubproject(testGrapeObject, *, execution_path):
        # There is currently no elegant way of doing this
        grapeConfig = config_parser_base.GrapeConfigParserBase(execution_path)
        allSubprojects = grapeConfig.getAllNestedSubprojects()
        # Edit the grapeconfig
        testGrapeObject.assertTrue("subproject1" in allSubprojects,"subproject1 not in grapeconfig")
        allSubprojects.remove("subproject1")
        grapeConfig.set(Option.SECTION_NESTED_PROJECTS, "names", " ".join(allSubprojects))
        grapeConfig.remove_section("nested-subproject1")
        with open(os.path.join(execution_path, ".grapeconfig"), 'w') as f:
           grapeConfig.write(f)
        git.add(".grapeconfig", execution_path=execution_path)
        git.commit("-m \"removed subproject1\"", execution_path=execution_path)

    def switchToMaster(self):
        self.menu.applyMenuChoice("checkout", ["master"])

    def resetMenu(self, workspace_dir):
        grapeMenu._resetMenu()
        self.menu = grapeMenu.menu(workspace_dir)

    def testAddingNewNestedSubproject(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
        except grape_errors.GrapeGitError as e:
            self.fail(self.get_output() + e.gitCommand)

    def testSwitchingBranchesWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            # create the branches using git
            git.branch("newBranch", execution_path=self.repo)
            git.branch("newBranch", execution_path=self.subproject)
            # try switching to the branches using grape
            self.menu.applyMenuChoice("checkout", ["newBranch"])
            self.assertEqual(git.currentBranch(execution_path=self.repo), "newBranch",
                            "outer level repo not on newBranch after checkout")
            self.assertEqual(git.currentBranch(execution_path=self.subproject), "newBranch",
                            "subproject not on newBranch after checkout")
        except grape_errors.GrapeGitError as e:
            self.fail(self.get_output() + e.gitCommand.split()[-10:])

    @patch('vine.utility.userInput')
    def testDeactivatingAndReactivatingNestProjects(self, mock_userInput):
        try:
            # Set up main workspace and add a new subproject
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            self.assertTrue(os.path.isdir(self.subproject))
            # answer none to whether we want all subprojects, y to deleting it
            mock_userInput.side_effect = ["n\n", "y\n"]
            self.menu.applyMenuChoice("uv")
            self.assertFalse(os.path.isdir(self.subproject))
            # answer a to whether we want all subprojects
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject), '\n'.join(self.get_output()))
            # run grape uv again to make sure it just keeps things the same
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject))

            # Set up a second workspace
            second_space = os.path.join(self.defaultWorkingDirectory, "client2")
            args = [self.repo, second_space]
            # this clones develop which has no nested subprojects
            mock_userInput.side_effect = ["\n", "y\n", "a\n", "\n", "\n"]
            ret = self.menu.applyMenuChoice("clone", args)

            # We have to reset the menu everytime we change workspaces
            self.resetMenu(second_space)

            # checkout master which has nested subprojects
            mock_userInput.side_effect = ["y", "\n", "\n"]
            ret = self.menu.applyMenuChoice("checkout", ["master"])
            self.assertTrue(ret, "vine.clone returned failure")
            # run grape uv to get the nested subprojects
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv")

            ## Go back to the main workspace and modify the subprojects
            self.resetMenu(self.repo)
            self.assertCanAddSecondSubproject(self, execution_path=self.repo)
            self.assertCanRemoveFirstSubproject(self, execution_path=self.repo)

            ## Try uv on the second workspace
            # deactivate all nested subprojects
            self.resetMenu(second_space)
            mock_userInput.side_effect = ["n\n"]
            self.menu.applyMenuChoice("uv", ["-f"])
            # update workspace
            git.pull("origin master", execution_path=second_space)
            # activate all nested subprojects
            # reset the menu here to reread the grapeconfig
            self.resetMenu(second_space)
            mock_userInput.side_effect = ["a\n"]
            self.menu.applyMenuChoice("uv", ["-f"])
            # ensure that changes from the main client are picked up
            self.assertFalse(os.path.isdir(os.path.join(second_space, "subs", "subproject1")), "subproject1 should not be present")
            self.assertTrue(os.path.isdir(os.path.join(second_space, "subs", "subproject2")), "subproject2 should be present")
        
        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail(('\n'.join(output) + e.gitCommand).split()[-10:])

    def testProjectWideGrapeStatusWithNestedProjects(self):
        import logging
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            f1Path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1Path)
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo),
                            f"{os.path.join('subproject1', 'f1')} shows up " +
                            "in git status when it shouldn't")
            logging.critical("STARTING applyMenuChoice")
            self.menu.applyMenuChoice("status", ['-u'])
            logging.critical("FINISHED applyMenuChoice")
            actual_output = self.get_output()
            subproject_path = os.path.join('subs', 'subproject1', 'f1')
            logging.critical("STARTING assertIn")
            self.assertIn(f" ?? {subproject_path}", actual_output,
                          f"{subproject_path} does not show up in grape status")
            logging.critical("FINISHED assertIn")
        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail('\n'.join([output, e.gitCommand]))

    def testProjectWideGrapeCommitWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self, execution_path=self.repo)
            f1Path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1Path)
            cwd = os.getcwd()
            git.add(f1Path, execution_path=self.subproject)
            # check that git sees the file
            firstStatus = git.status("--porcelain",
                                     execution_path=self.subproject)
            self.assertTrue("f1" in firstStatus)
            self.menu.applyMenuChoice("commit", ["-m", "\"adding f1\""])
            # check that running grape commit from the workspace base directory removes f1 from the status
            secondStatus = git.status("--porcelain",
                                      execution_path=self.subproject)
            self.assertTrue("f1" not in secondStatus,"commit didn't remove f1 from status")
        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail(('\n'.join(output) + e.gitCommand).split()[-10:])


if __name__ == "__main__":
    import unittest
    unittest.main()
