import os
import sys
from test import testGrape
from test import testNestedSubproject
from vine import grape_errors
from vine import grapeGit as git


class TestMD(testGrape.TestGrape):

    # sets up a new change on the master branch one commit ahead of
    # testMerge and checks out testMerge.

    def setUpMerge(self):
        # create a new branch
        git.branch("testMerge", execution_path=self.repo)
        # add f2 to master
        f2Path = os.path.join(self.repo, "f2")
        testGrape.writeFile2(f2Path)
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"f2\"", execution_path=self.repo)
        git.checkout("testMerge", execution_path=self.repo)
        self.setUpConfig()
        # Set command_path after calling setUpConfig()
        self.menu.set_command_path(self.repo)

    def setUpConflictingMerge(self):
        self.setUpMerge()
        # add a conflicting commit
        f2Path = os.path.join(self.repo, "f2")
        testGrape.writeFile3(f2Path)
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"f2\"", execution_path=self.repo)

    def testNonConflictingMerge(self):
        self.setUpMerge()
        # now run grape md, should be a fast forward merge
        try:
            self.assertNotEqual(git.shortSHA(execution_path=self.repo),
                                git.shortSHA("master", execution_path=self.repo))
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return True")
            self.assertEqual(git.shortSHA(execution_path=self.repo),
                             git.shortSHA("master", execution_path=self.repo),
                             "merging master into test branch did not fast forward")
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Unhandled GrapeGitError: {e.gitCommand}\n" +
                      f"{e.gitOutput}")

    def testConflictingMerge(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(git.shortSHA(execution_path=self.repo),
                                git.shortSHA("master", execution_path=self.repo))
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return false as expected for a conflict")

            self.assertFalse(git.isWorkingDirectoryClean(execution_path=self.repo),
                             "working directory clean before attempted " +
                             f"continution of merge\n{self.get_output()}")
            # resolve the conflict
            git.checkout("--ours f2", execution_path=self.repo)
            git.add("f2", execution_path=self.repo)

            ret = self.menu.applyMenuChoice("m", ["--continue"])
            self.assertTrue(ret, "grape m --continue did not return True\n" +
                                 f"{self.get_output()}")
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo),
                            "grape m --continue did not finish merge\n" +
                            f"{self.get_output()}")
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")

    def testConflictingMerge_MD(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(git.shortSHA(execution_path=self.repo),
                                git.shortSHA("master", execution_path=self.repo))
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape m did not return false as expected for a conflict")
            # resolve the conflict

            self.assertFalse(git.isWorkingDirectoryClean(execution_path=self.repo),
                             "working directory clean before attempted " +
                             "continution of merge\n{self.get_output()}")
            git.checkout("--ours f2", execution_path=self.repo)
            git.add("f2", execution_path=self.repo)

            ret = self.menu.applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, "grape md --continue did not return True\n" +
                                 f"{self.get_output()}")
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo),
                            "grape m --continue did not finish merge\n" +
                            f"{self.get_output()}")
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")

    def createTestSubmodule(self, *, execution_path):
        # make a repo to turn into a submodule
        git.clone(argstr='--mirror', source_repo=self.repo,
                  clone_repo=self.repos[1], execution_path=execution_path)
        # add repo2 as a submodule to repo1
        git.submodule(f"add {self.repos[1]} submodule1",
                      execution_path=self.repo)
        git.commit("-m \"added submodule1\"", execution_path=self.repo)


    def setUpNonConflictingSubmoduleMerge(self):
        self.createTestSubmodule(execution_path=self.defaultWorkingDirectory)
        git.branch("testSubmoduleMerge",
                   execution_path=self.repo)
        # create a new commit in submodule1
        submodule1 = os.path.join(self.repo, "submodule1")
        git.checkout("master", execution_path=submodule1)
        f1Path = os.path.join(submodule1, "f1")
        testGrape.writeFile2(f1Path)
        git.add("f1", execution_path=submodule1)
        git.commit("-m \"added f2 as f1\"", execution_path=submodule1)
        # update outer level with new commit
        git.commit("submodule1 -m \"updated submodule gitlink on master branch\"",
                   execution_path=self.repo)

        # setup what should be a notionally-conflict free merge
        # (grape needs to deal with the gitlink conflicts automatically)
        git.checkout("testSubmoduleMerge", execution_path=self.repo)
        git.submodule("update", execution_path=self.repo)
        git.checkout("-b testSubmoduleMerge", execution_path=submodule1)
        f2Path = os.path.join(submodule1, "f2")
        testGrape.writeFile3(f2Path)
        git.add("f2", execution_path=submodule1)
        git.commit("-m \"added f3 as f2\"", execution_path=submodule1)
        git.commit("-a -m \"updated gitlink on branch testSubmoduleMerge\"",
                   execution_path=self.repo)
        self.setUpConfig()
        self.menu.set_command_path(self.repo)

    def setUpConflictingSubmoduleMerge(self):
        self.createTestSubmodule(execution_path=self.defaultWorkingDirectory)
        git.branch("testSubmoduleMerge2",
                   execution_path=self.repo)
        subPath = os.path.join(self.repo, "submodule1")
        git.branch("testSubmoduleMerge2", execution_path=subPath)
        git.checkout("master", execution_path=subPath)
        f1Path = os.path.join(subPath, "f1")
        testGrape.writeFile2(f1Path)
        git.add("f1", execution_path=subPath)
        git.commit("-m \"added f2 as f1\"", execution_path=subPath)
        git.commit("submodule1 -m \"updated submodule gitlink on master branch\"",
                   execution_path=self.repo)
        git.checkout("testSubmoduleMerge2", execution_path=self.repo)
        git.submodule("update", execution_path=self.repo)
        git.checkout("testSubmoduleMerge2", execution_path=subPath)
        testGrape.writeFile3(f1Path)
        git.add("f1", execution_path=subPath)
        git.commit("-m \"added f3 as f1\"", execution_path=subPath)
        git.commit("submodule1 -m \"updated submodule gitlink on testSubmoduleMerge branch\"",
                   execution_path=self.repo)
        self.setUpConfig()
        self.menu.set_command_path(self.repo)

    def testNonConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return true for submodule merge.")

            # the submodule should not be modified
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo))

            # master should be merged into current branch
            self.assertTrue(git.branchUpToDateWith(
                "testSubmoduleMerge", "master", execution_path=self.repo))

            # the gitlink should be at the tip of testSubmoduleMerge
            git.submodule("update", execution_path=self.repo)
            submodule1 = os.path.join(self.repo, "submodule1")
            self.assertFalse(git.diff("testSubmoduleMerge",
                                      execution_path=submodule1),
                             "gitlink is not at testSubmoduleMerge tip after merge")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught git error executing {e.gitCommand}:\n" +
                      f"{e.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught System Exit\n{self.get_output()}")

    def testNonConflictingSubmoduleMerge(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertTrue(ret, "grape m did not return true for submodule merge.")

            # the submodule should not be modified
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo))

            # master should be merged into current branch
            self.assertTrue(git.branchUpToDateWith(
                "testSubmoduleMerge", "master", execution_path=self.repo))

            # the gitlink should be at the tip of testSubmoduleMerge
            git.submodule("update", execution_path=self.repo)
            submodule1 = os.path.join(self.repo, "submodule1")
            self.assertFalse(git.diff("testSubmoduleMerge",
                                      execution_path=submodule1),
                             "gitlink is not at testSubmoduleMerge tip after merge")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught git error executing {e.gitCommand}:\n" +
                      f"{e.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught System Exit\n{self.get_output()}")

    def testConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return False for conflicting merge.")
            # should only have modifications in submodule1, not conflicts
            subPath = os.path.join(self.repo, "submodule1")
            status = git.status("--porcelain", execution_path=subPath)
            self.assertTrue("UU" not in status and "AA" in status,
                            f"unexpected status {status} at toplevel")
            status = git.status("--porcelain", execution_path=subPath)
            self.assertTrue("AA" in status,
                            f"unexpected status {status} in submodule1")

            # resolve the conflict and continue from the submodule's directory
            git.checkout("--ours f1", execution_path=subPath)
            git.add("f1", execution_path=subPath)
            git.commit("-m \"resolved conflict with our f1\"",
                       execution_path=subPath)
            self.setUpConfig()
            self.menu.set_command_path(subPath)
            ret = self.menu.applyMenuChoice("md", ["--continue"])

            # test that we returned successfully
            self.assertTrue(ret, "grape md --continue did not complete " +
                                 "successfully after resolving submodule " +
                                 f"conflict\n{self.get_output()}")

            # test that the submodule master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2",
                                                   "master",
                                                   execution_path=subPath),
                            "grape md --continue did not merge in submodule1`s master branch")

            # test that the outer level master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2",
                                                   "master",
                                                   execution_path=self.repo),
                            "grape md --continue did not merge in the outer level master branch")

            # ensure the gitlink is at the right commit
            git.submodule("update", execution_path=self.repo)
            diff = git.diff("testSubmoduleMerge2", execution_path=subPath)
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught git error executing {e.gitCommand}:\n" +
                      f"{e.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught exit\n{self.get_output()}")

    def testConflictingSubmoduleMerge(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return False for conflicting merge.")
            # should only have modifications in submodule1, not conflicts
            subPath = os.path.join(self.repo, "submodule1")
            status = git.status("--porcelain", execution_path=subPath)
            self.assertTrue("UU" not in status and "AA" in status,
                            f"unexpected status {status} at toplevel")
            subPath = os.path.join(self.repo, "submodule1")
            status = git.status("--porcelain", execution_path=subPath)
            self.assertTrue("AA" in status,
                            f"unexpected status {status} in submodule1")

            # resolve the conflict and continue from the submodule's directory
            git.checkout("--ours f1", execution_path=subPath)
            git.add("f1", execution_path=subPath)
            git.commit("-m \"resolved conflict with our f1\"",
                       execution_path=subPath)
            self.setUpConfig()
            self.menu.set_command_path(subPath)
            ret = self.menu.applyMenuChoice("m", ["--continue"])

            # test that we returned successfully
            self.assertTrue(ret, "grape m --continue did not complete " +
                                 "successfully after resolving submodule " +
                                 f"conflict\n{self.get_output()}")

            # test that the submodule master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2",
                                                   "master",
                                                   execution_path=subPath),
                            "grape m --continue did not merge in submodule1`s master branch")

            # test that the outer level master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2",
                                                   "master",
                                                   execution_path=self.repo),
                            "grape m --continue did not merge in the outer level master branch")

            # ensure the gitlink is at the right commit
            git.submodule("update", execution_path=self.repo)
            diff = git.diff("testSubmoduleMerge2", execution_path=subPath)
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught git error executing {e.gitCommand}:\n" +
                      f"{e.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught exit\n{self.get_output()}")

    def setUpConflictingNestedSubprojectMerge(self):
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(
            self, execution_path=self.defaultWorkingDirectory)

        # set up f1 with conflicting content on master  and testNestedMerge branches.
        git.checkout("master", execution_path=self.subproject)
        git.branch("testNestedMerge", execution_path=self.subproject)
        f1Path = os.path.join(self.subproject, "f1")
        testGrape.writeFile2(f1Path)
        git.add("f1", execution_path=self.subproject)
        git.commit("-m \"added f2 as f1\"", execution_path=self.subproject)
        git.checkout("testNestedMerge", execution_path=self.subproject)
        testGrape.writeFile3(f1Path)
        git.add("f1", execution_path=self.subproject)
        git.commit("-m \"added f1 as f1\"", execution_path=self.subproject)

    def testConflictingNestedSubprojectMerge(self):
        self.setUpConflictingNestedSubprojectMerge()
        git.checkout(" -b testNestedMerge", execution_path=self.repo)

        #make sure we're not up to date with master
        self.assertFalse(git.branchUpToDateWith("testNestedMerge", "master",
                                                execution_path=self.subproject),
                        msg=None)
        # run grape m --am - this helps ensure m is following same code path as md.
        try:
            ret = self.menu.applyMenuChoice("m", ["--am", "master"], globalArgs=["-v"])
        except SystemExit as e:
            self.fail(f"grape m raised exception {e}")
        self.assertFalse(ret, "grape m did not return False for conflicting merge.")
        # git status in outer repo should be clean
        status = git.status("--porcelain", execution_path=self.repo)
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        # git status in subproject should not be clean
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertIn("AA", status, "no conflicts in subproject status \n" +
                                    f"{status} ")

        # resolve the conflict
        git.checkout("--ours f1", execution_path=self.subproject)
        git.add("f1", execution_path=self.subproject)
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")

        # continue the merge
        ret = self.menu.applyMenuChoice("m", ["--continue"])
        self.assertTrue(ret, "m didn't return successfully after conflict resolution")

        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master",
                                               execution_path=self.subproject))
        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master",
                                               execution_path=self.repo))

    def testConflictingNestedSubprojectMerge_MD(self):
        self.setUpConflictingNestedSubprojectMerge()
        git.checkout(" -b testNestedMerge", execution_path=self.repo)

        #make sure we're not up to date with master
        self.assertFalse(git.branchUpToDateWith("testNestedMerge", "master",
                                                execution_path=self.subproject),
                         msg=None)
        # run grape md --am
        try:
            ret = self.menu.applyMenuChoice("md", ["--am", "--public=master"], globalArgs=["-v"])
        except SystemExit as e:
            self.fail(f"grape md raised exception {e}")
        self.assertFalse(ret, "grape md did not return False for conflicting merge.")
        # git status in outer repo should be clean
        status = git.status("--porcelain", execution_path=self.repo)
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        # git status in subproject should not be clean
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertIn("AA", status, "no conflicts in subproject status")

        # resolve the conflict
        git.checkout("--ours f1", execution_path=self.subproject)
        git.add("f1", execution_path=self.subproject)
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")

        # continue the merge
        ret = self.menu.applyMenuChoice("md", ["--continue"])
        self.assertTrue(ret, "md didn't return successfully after conflict resolution")

        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master",
                                               execution_path=self.subproject))
        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master",
                                               execution_path=self.repo))
