__author__ = 'robinson96'
import os
import sys




if not ".." in sys.path:
    sys.path.append("..")
import testGrape
from vine import grapeGit as git
from vine import grapeMenu


configStr = "[workspace]\n" \
            "subprojectType = subtree\n" \
            ""

nestedConfigStr = "[workspace]\n" \
                  "subprojectType = nested\n"

class TestNestedSubproject(testGrape.TestGrape):

    @staticmethod
    def writeDefaultConfig(self, filename):
        with open(filename, 'w') as f:
            f.writelines(configStr.split('\n'))

    @staticmethod
    def writeNestedConfig(self, filename):
        with open(filename, 'w') as f:
            f.writelines(nestedConfigStr.split('\n'))

    # Sets up a new nested subproject
    @staticmethod
    def assertCanAddNewSubproject(testGrapeObject):
        git.clone("--mirror %s %s" % (testGrapeObject.repo, testGrapeObject.repos[1]))
        os.chdir(testGrapeObject.repo)
        grapeMenu.menu().applyMenuChoice("addSubproject", ["--name=subproject1", "--prefix=subs/subproject1",
                                                           "--branch=master", "--url=%s" % testGrapeObject.repos[1],
                                                           "--nested", "--noverify"])
        subproject1path = os.path.join(testGrapeObject.repo, "subs/subproject1")
        testGrapeObject.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        os.chdir(subproject1path)
        # check to see that subproject1 is a git repo
        basedir = os.path.split(git.baseDir())[-1]
        subdir = os.path.split(subproject1path)[-1]
        testGrapeObject.assertTrue(basedir == subdir, "subproject1's git repo is %s, not %s" % (basedir, subdir))
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
        grapeMenu.menu().applyMenuChoice("checkout", ["master"])

    def testAddingNewNestedSubproject(self):
        try:
            self.assertCanAddNewSubproject(self)


        except git.GrapeGitError as e:
            self.assertTrue(False, '\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand)
            pass

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
            grapeMenu.menu().applyMenuChoice("checkout", ["newBranch"])
            self.assertTrue(git.currentBranch() == "newBranch", "outer level repo not on newBranch after checkout")
            os.chdir(self.subproject)
            self.assertTrue(git.currentBranch() == "newBranch", "subproject not on newBranch after checkout")

        except git.GrapeGitError as e:
            self.assertTrue(False, ('\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand).split()[-10:])
            pass

    def testDeactivatingAndReactiviatingNestProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            self.assertTrue(os.path.isdir(self.subproject))
            # answer none to whether we want all subprojects, y to deleting it
            self.queueUserInput(["n\n", "y\n"])
            grapeMenu.menu().applyMenuChoice("uv")
            self.assertFalse(os.path.isdir(self.subproject))
            # answer a to whether we want all subprojects
            self.queueUserInput(["a\n"])
            print self.input.buf
            grapeMenu.menu().applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject), '\n'.join(self.output)+'\n'.join(self.error))
            # run grape uv again to make sure it just keeps things the same
            self.queueUserInput(["a\n"])
            grapeMenu.menu().applyMenuChoice("uv")
            self.assertTrue(os.path.isdir(self.subproject))
        except git.GrapeGitError as e:
            self.assertTrue(False, ('\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand).split()[-10:])
            pass

    def testProjectWideGrapeStatusWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject(self)
            f1Path = os.path.join(self.subproject, "f1")
            testGrape.writeFile1(f1Path)
            self.assertTrue(git.isWorkingDirectoryClean(), "subproject1/f1 shows up in git status when it shouldn't")
            grapeMenu.menu().applyMenuChoice("status", ['-v', '-u'])
            self.assertTrue(" ?? subs/subproject1/f1" in '\n'.join(self.output.buflist), "subproject1/f1 does not show up in grape "
                                                                         "status")

        except git.GrapeGitError as e:
            self.assertTrue(False, ('\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand).split()[-10:])
            pass   
        
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
            grapeMenu.menu().applyMenuChoice("commit",["-m", "\"adding f1\""])
            # check that running grape commit from the workspace base directory removes f1 from the status
            os.chdir(self.subproject)
            secondStatus = git.status("--porcelain")
            self.assertTrue("f1" not in secondStatus,"commit didn't remove f1 from status")
            os.chdir(cwd)

        except git.GrapeGitError as e:
            self.assertTrue(False, ('\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand).split()[-10:])
            pass

if __name__ == "__main__":
    import unittest
    unittest.main() 
