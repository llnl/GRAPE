__author__ = 'robinson96'
import os
import sys

import testGrape


if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeGit as git
from vine import grapeMenu

class TestCheckout(testGrape.TestGrape):
    # sets up an outer repo with two branches. master has file1.
    # addSubmodule has a submodule added.
    # the submodule has two branches, master and addSubmodule
    # master has the file f3, addSubmodule has the file f2.
    def setUpSubmoduleBranch(self):
        git.clone("%s %s" % (self.repo, self.repos[1]))
        os.chdir(self.repo)
        git.checkout("-b addSubmodule")
        git.submodule("add %s submodule" % self.repos[1])
        git.commit("-m \"added submodule\"")

        # put the remote for the submodule into a HEAD-less state so it can accept pushes
        os.chdir(self.repos[1])
        git.checkout("--orphan HEAD")

        # go to the submodule and add a file to it.
        os.chdir(os.path.join(self.repo,"submodule"))
        f2 = os.path.join(self.repo,"submodule","f2")
        testGrape.writeFile2(f2)
        git.checkout("-b addSubmodule")
        git.add(f2)
        git.commit("-m \"added f2\"")

        # add another file on the master branch for the submodule
        git.branch("-f master HEAD")
        git.checkout("master")
        f3 = os.path.join(self.repo, "submodule", "f3")
        testGrape.writeFile3(f3)
        git.add(f3)
        git.commit("f3 -m \"f3\"")

        # update the submodule's remote
        git.push("origin --all")

        # git back to the master branch in the original repository
        os.chdir(self.repo)
        git.checkout("master")

    def switchToMaster(self):
        grapeMenu.menu().applyMenuChoice("checkout", ["master"])

    def switchToAddSubmodule(self):
        grapeMenu.menu().applyMenuChoice("checkout", ["addSubmodule"])

    def assertFile1ExistsInSubmodule(self):
        self.assertTrue(os.path.exists(os.path.join(self.repo, "submodule", self.file1)),
                        "%s does not exist" % self.file1)

    def assertSubmoduleDirectoryDoesNotExist(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo, "submodule")),
                         "submodule exists when it should not")

    def testSwitchingToBranchWithNewSubmodule(self):
        try:
            self.setUpSubmoduleBranch()

            self.input.writelines(["y", "\n", "\n"])
            self.input.seek(0)
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            # switch to master, saying 'y' to delete request
            self.input.writelines(["y"])
            self.input.seek(0)
            self.switchToMaster()
            self.assertSubmoduleDirectoryDoesNotExist()

            # switch to addSubmodule, saying yes to request to have submodule
            self.input.writelines(["y", "\n", "\n"])
            self.input.seek(0)
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            # switch back to master, this time saying don't delete request
            self.input.writelines(["n"])
            self.input.seek(0)
            self.switchToMaster()
            self.assertFile1ExistsInSubmodule()
        except git.GrapeGitError as e:
            self.assertTrue(False, '\n'.join(self.output)+'\n'.join(self.error) + e.gitCommand )
            pass
