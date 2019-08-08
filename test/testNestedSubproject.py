__author__ = 'robinson96'
import os
import sys
from test import testGrape
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu


class TestNestedSubproject(testGrape.TestGrape):

    # Sets up a new nested subproject
    @staticmethod
    def assertCanAddNewSubproject(testGrapeObject):
        git.clone(f"--mirror {testGrapeObject.repo} " +
                  f"{testGrapeObject.repos[1]}")
        os.chdir(testGrapeObject.repo)
        subproject_path = os.path.join('subs', 'subproject1')
        grapeMenu.menu().applyMenuChoice(
            "addSubproject", ["--name=subproject1",
                              f"--prefix={subproject_path}",
                              "--branch=master",
                              f"--url={testGrapeObject.repos[1]}",
                              "--nested", "--noverify"])
        subproject1path = os.path.join(testGrapeObject.repo, subproject_path)
        testGrapeObject.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        os.chdir(subproject1path)
        # check to see that subproject1 is a git repo
        basedir = os.path.split(git.baseDir())[-1]
        subdir = os.path.split(subproject1path)[-1]
        testGrapeObject.assertTrue(basedir == subdir,
                                   f"subproject1's git repo is {basedir}, " +
                                   f"not {subdir}")
        # check to see that edits that occur in the new subproject are ignored by outer repo
        testGrape.writeFile3(os.path.join(subproject1path, "f3"))
        # make sure there is an edit
        testGrapeObject.assertFalse(git.isWorkingDirectoryClean(), "subproject1 clean after adding f3")
        os.chdir(testGrapeObject.repo)
        # check that grape left the repository in a clean state
        testGrapeObject.assertTrue(git.isWorkingDirectoryClean(), "repo not clean after added subproject1")
        # check in the edit
        os.chdir(subproject1path)
        git.add("f3")
        git.commit("-m \"added f3\"")
        testGrapeObject.assertTrue(git.isWorkingDirectoryClean(), "subproject1 not clean")
        os.chdir(testGrapeObject.repo)
        testGrapeObject.subproject = subproject1path

    def switchToMaster(self):
        self.menu.applyMenuChoice("checkout", ["master"])

    def testAddingNewNestedSubproject(self):
        try:
            self.assertCanAddNewSubproject(self)
        except grape_errors.GrapeGitError as e:
            self.fail(self.get_output() + e.gitCommand)

    def testSwitchingBranchesWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            # create the branches using git
            os.chdir(self.repo)
            git.branch("newBranch")
            os.chdir(self.subproject)
            git.branch("newBranch")
            # try switching to the branches using grape
            os.chdir(self.repo)
            self.menu.applyMenuChoice("checkout", ["newBranch"])
            self.assertTrue(git.currentBranch() == "newBranch", "outer level repo not on newBranch after checkout")
            os.chdir(self.subproject)
            self.assertTrue(git.currentBranch() == "newBranch", "subproject not on newBranch after checkout")
        except grape_errors.GrapeGitError as e:
            self.fail(self.get_output() + e.gitCommand.split()[-10:])

    def testDeactivatingAndReactiviatingNestProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            self.assertTrue(os.path.isdir(self.subproject))
            # answer none to whether we want all subprojects, y to deleting it
            with self.queue_user_input(["n\n", "y\n"]):
                self.menu.applyMenuChoice("uv")
            self.assertFalse(os.path.isdir(self.subproject))
            # answer a to whether we want all subprojects
            with self.queue_user_input(["a\n"]):
                self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject), '\n'.join(self.get_output()))
            # run grape uv again to make sure it just keeps things the same
            with self.queue_user_input(["a\n"]):
                self.menu.applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject))
        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail(('\n'.join(output) + e.gitCommand).split()[-10:])

    def testProjectWideGrapeStatusWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            f1Path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1Path)
            self.assertTrue(git.isWorkingDirectoryClean(),
                            f"{os.path.join('subproject1', 'f1')} shows up " +
                            "in git status when it shouldn't")
            self.menu.applyMenuChoice("status", ['-u'], globalArgs=["-v"])
            actual_output = self.get_output()
            subproject_path = os.path.join('subs', 'subproject1', 'f1')
            self.assertIn(f" ?? {subproject_path}", actual_output,
                          f"{subproject_path} does not show up in grape status")

        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail(('\n'.join(output)+'\n'.join(self.error) + e.gitCommand).split()[-10:])

    def testProjectWideGrapeCommitWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            f1Path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1Path)
            cwd = os.getcwd()
            os.chdir(self.subproject)
            git.add(f1Path)
            # check that git sees the file
            firstStatus = git.status("--porcelain")
            self.assertTrue("f1" in firstStatus)
            os.chdir(cwd)
            self.menu.applyMenuChoice("commit",["-m", "\"adding f1\""])
            # check that running grape commit from the workspace base directory removes f1 from the status
            os.chdir(self.subproject)
            secondStatus = git.status("--porcelain")
            self.assertTrue("f1" not in secondStatus,"commit didn't remove f1 from status")
            os.chdir(cwd)
        except grape_errors.GrapeGitError as e:
            output = self.get_output()
            self.fail(('\n'.join(output) + e.gitCommand).split()[-10:])


if __name__ == "__main__":
    import unittest
    unittest.main()
