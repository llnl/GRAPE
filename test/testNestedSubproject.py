__author__ = 'robinson96'
import os
import sys
from unittest.mock import patch
from test import testGrape
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu


class TestNestedSubproject(testGrape.TestGrape):

    # Sets up a new nested subproject
    @staticmethod
    def assertCanAddNewSubproject(testGrapeObject, *, execution_path):
        git.clone(argstr='--mirror', source_repo=testGrapeObject.repo,
                  clone_repo=testGrapeObject.repos[1],
                  execution_path=testGrapeObject.repo)
        subproject_path = os.path.join('subs', 'subproject1')
        testGrapeObject.menu.applyMenuChoice(
            "addSubproject", ["--name=subproject1",
                              f"--prefix={subproject_path}", "--branch=master",
                              f"--url={testGrapeObject.repos[1]}",
                              "--nested", "--noverify"])
        subproject1path = os.path.join(testGrapeObject.repo, subproject_path)
        testGrapeObject.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        # check to see that subproject1 is a git repo
        basedir = os.path.split(git.baseDir(execution_path=subproject1path))[-1]
        subdir = os.path.split(subproject1path)[-1]
        testGrapeObject.assertEqual(basedir, subdir,
                                   f"subproject1's git repo is {basedir}, " +
                                   f"not {subdir}")
        # check to see that edits that occur in the new subproject are ignored by outer repo
        testGrape.writeFile3(os.path.join(subproject1path, "f3"))
        # make sure there is an edit
        testGrapeObject.assertFalse(git.isWorkingDirectoryClean(execution_path=subproject1path),
                                    "subproject1 clean after adding f3")
        # check that grape left the repository in a clean state
        testGrapeObject.assertTrue(git.isWorkingDirectoryClean(execution_path=testGrapeObject.repo),
                                   "repo not clean after added subproject1")
        # check in the edit
        git.add("f3", execution_path=subproject1path)
        git.commit("-m \"added f3\"", execution_path=subproject1path)
        testGrapeObject.assertTrue(git.isWorkingDirectoryClean(execution_path=subproject1path),
                                   "subproject1 not clean")
        testGrapeObject.subproject = subproject1path

    def switchToMaster(self):
        self.menu.applyMenuChoice("checkout", ["master"])

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
    def testDeactivatingAndReactiviatingNestProjects(self, mock_userInput):
        try:
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
            self.menu.applyMenuChoice("status", ['-u'], globalArgs=["-v"])
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
