__author__ = 'robinson96'
import os
from grape.test import testGrape
from grape.vine import grape_errors
from grape.vine import grapeGit as git


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
        git.push("origin HEAD")

        # put the remote for the submodule into a HEAD-less state so it can accept pushes
        os.chdir(self.repos[1])
        git.checkout("--orphan dummy_branch_name")

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
        self.menu.applyMenuChoice("checkout", ["master"])

    def switchToAddSubmodule(self):
        self.menu.applyMenuChoice("checkout", ["addSubmodule"])

    def assertFile1ExistsInSubmodule(self):
        self.assertTrue(os.path.exists(os.path.join(self.repo, "submodule", self.file1)),
                        "%s does not exist" % self.file1)

    def assertSubmoduleDirectoryDoesNotExist(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo, "submodule")),
                         "submodule exists when it should not")

    def testSwitchingToBranchWithNewSubmodule(self):
        debug = False
        if debug:
            self.switchToStdout()
        try:
            self.setUpSubmoduleBranch()
            
            with self.queue_user_input(["y", "\n", "\n", "\n"]):
                self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            # switch to master, saying 'y' to delete request
            with self.queue_user_input(["y", "\n", "\n", "\n", "\n"]):
                self.switchToMaster()
            self.assertSubmoduleDirectoryDoesNotExist()

            # switch to addSubmodule, saying yes to request to have submodule
            with self.queue_user_input(["y", "\n", "\n", "\n"]):
                self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            # switch back to master, this time saying don't delete request
            with self.queue_user_input(["y", "\n", "\n"]):
                self.switchToMaster()
            self.assertFile1ExistsInSubmodule()
        except grape_errors.GrapeGitError as e:
            self.fail('\n'.join(self.get_output())+'\n'.join(self.error) + e.gitCommand + '\n' + e.gitOutput)
        finally:
            if debug:
                self.switchToHiddenOutput()
