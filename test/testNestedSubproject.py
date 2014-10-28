__author__ = 'robinson96'
import os
import sys

import testGrape


if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeGit as git
from vine import grapeMenu


configStr = "[workspace]\n" \
            "subprojectType = subtree\n" \
            ""

nestedConfigStr = "[workspace]\n" \
                  "subprojectType = nested\n"

class TestNestedSubproject(testGrape.TestGrape):

    def writeDefaultConfig(self, filename):
        with open(filename, 'w') as f:
            f.writelines(configStr.split('\n'))

    def writeNestedConfig(self, filename):
        with open(filename, 'w') as f:
            f.writelines(nestedConfigStr.split('\n'))

    # Sets up
    def assertCanAddNewSubproject(self):
        git.clone("%s %s" % (self.repo, self.repos[1]))
        os.chdir(self.repo)
        grapeMenu.menu().applyMenuChoice("addSubproject", ["--name=subproject1", "--prefix=subproject1",
                                                           "--branch=master", "--url=%s" % self.repos[1],
                                                           "--nested", "--noverify"])
        subproject1path = os.path.join(self.repo, "subproject1")
        self.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        os.chdir(subproject1path)
        # check to see that subproject1 is a git repo
        basedir = os.path.split(git.baseDir())[-1]
        subdir = os.path.split(subproject1path)[-1]
        self.assertTrue(basedir == subdir, "subproject1's git repo is %s, not %s" % (basedir, subdir))
        # check to see that edits that occur in the new subproject are ignored by outer repo
        testGrape.writeFile2(os.path.join(subproject1path, "f2"))
        os.chdir(self.repo)
        # check that grape left the repository in a clean state
        self.assertTrue(git.isWorkingDirectoryClean(), "repo not clean after added subproject1")
        self.subproject = subproject1path

    def switchToMaster(self):
        grapeMenu.menu().applyMenuChoice("checkout", ["master"])

    def testAddingNewNestedSubproject(self):
        try:
            self.assertCanAddNewSubproject()


        except git.GrapeGitError as e:
            self.assertTrue(False, '\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand)
            pass

    def testSwitchingBranchesWithNestedProjects(self):
        try:
            self.assertCanAddNewSubproject()
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

