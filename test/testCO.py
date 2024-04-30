__author__ = 'robinson96'
import os
from unittest.mock import patch
from test import testGrape
from vine import grape_errors
from vine import grapeGit as git


class TestCheckout(testGrape.TestGrape):
    # sets up an outer repo with two branches. master has file1.
    # addSubmodule has a submodule added.
    # the submodule has two branches, master and addSubmodule
    # master has the file f3, addSubmodule has the file f2.
    def setUpSubmoduleBranch(self):
        git.clone(source_repo=self.repo, clone_repo=self.repos[1],
                  execution_path=self.defaultWorkingDirectory)
        git.checkout("-b addSubmodule", execution_path=self.repo)
        git.submodule(f"add {self.repos[1]} submodule", execution_path=self.repo)
        git.commit("-m \"added submodule\"", execution_path=self.repo)
        git.push("origin HEAD", execution_path=self.repo)

        # put the remote for the submodule into a HEAD-less state so it can accept pushes
        git.checkout("--orphan dummy_branch_name", execution_path=self.repos[1])

        # go to the submodule and add a file to it.
        f2 = os.path.join(self.repo, "submodule", "f2")
        testGrape.writeFile2(f2)

        execution_path = os.path.join(self.repo, "submodule")
        git.checkout("-b addSubmodule", execution_path=execution_path)
        git.add(f2, execution_path=execution_path)
        git.commit("-m \"added f2\"", execution_path=execution_path)

        # add another file on the master branch for the submodule
        git.branch("-f master HEAD", execution_path=execution_path)
        git.checkout("master", execution_path=execution_path)
        f3 = os.path.join(self.repo, "submodule", "f3")
        testGrape.writeFile3(f3)
        git.add(f3, execution_path=execution_path)
        git.commit("f3 -m \"f3\"", execution_path=execution_path)

        # update the submodule's remote
        git.push("origin --all", execution_path=execution_path)

        # git back to the master branch in the original repository
        git.checkout("master", execution_path=self.repo)

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

    @patch('vine.utility.userInput')
    def testSwitchingToBranchWithNewSubmodule(self, mock_userInput):
        try:
            self.setUpSubmoduleBranch()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n"]
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n", "\n"]
            # switch to master, saying 'y' to delete request
            self.switchToMaster()
            self.assertSubmoduleDirectoryDoesNotExist()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n"]
            # switch to addSubmodule, saying yes to request to have submodule
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            mock_userInput.side_effect = ["y", "\n", "\n"]
            # switch back to master, this time saying don't delete request
            self.switchToMaster()
            self.assertFile1ExistsInSubmodule()
        except grape_errors.GrapeGitError as e:
            self.fail('\n'.join(self.get_output()) + e.gitCommand + '\n' + e.gitOutput)
