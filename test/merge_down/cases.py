import os

from vine import grape_errors
from vine import grapeGit as git


class MergeDownBasicCase:
    """Basic top-level merge flows kept together as one broad-run shard."""

    def testNonConflictingMerge(self):
        self.setUpMerge()
        try:
            self.assertNotEqual(
                git.shortSHA(execution_path=self.repo),
                git.shortSHA("master", execution_path=self.repo),
            )
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return True")
            self.assertEqual(
                git.shortSHA(execution_path=self.repo),
                git.shortSHA("master", execution_path=self.repo),
                "merging master into test branch did not fast forward",
            )
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")
        except grape_errors.GrapeGitError as exc:
            self.fail(f"Unhandled GrapeGitError: {exc.gitCommand}\n{exc.gitOutput}")

    def testConflictingMerge(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(
                git.shortSHA(execution_path=self.repo),
                git.shortSHA("master", execution_path=self.repo),
            )
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return false as expected for a conflict")
            self.assertFalse(
                git.isWorkingDirectoryClean(execution_path=self.repo),
                "working directory clean before attempted continution of merge\n"
                f"{self.get_output()}",
            )
            git.checkout("--ours f2", execution_path=self.repo)
            git.add("f2", execution_path=self.repo)

            ret = self.menu.applyMenuChoice("m", ["--continue"])
            self.assertTrue(ret, f"grape m --continue did not return True\n{self.get_output()}")
            self.assertTrue(
                git.isWorkingDirectoryClean(execution_path=self.repo),
                f"grape m --continue did not finish merge\n{self.get_output()}",
            )
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")

    def testConflictingMerge_MD(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(
                git.shortSHA(execution_path=self.repo),
                git.shortSHA("master", execution_path=self.repo),
            )
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return false as expected for a conflict")
            self.assertFalse(
                git.isWorkingDirectoryClean(execution_path=self.repo),
                "working directory clean before attempted continution of merge\n"
                f"{self.get_output()}",
            )
            git.checkout("--ours f2", execution_path=self.repo)
            git.add("f2", execution_path=self.repo)

            ret = self.menu.applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, f"grape md --continue did not return True\n{self.get_output()}")
            self.assertTrue(
                git.isWorkingDirectoryClean(execution_path=self.repo),
                f"grape md --continue did not finish merge\n{self.get_output()}",
            )
        except SystemExit:
            self.fail(f"Unexpected SystemExit: {self.get_output()}")


class MergeDownSubmoduleNonConflictCase:
    """Submodule merges that should complete without conflict resolution."""

    def testNonConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return true for submodule merge.")
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo))
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge", "master", execution_path=self.repo)
            )
            git.submodule("update", execution_path=self.repo)
            submodule1 = os.path.join(self.repo, "submodule1")
            self.assertFalse(
                git.diff("testSubmoduleMerge", execution_path=submodule1),
                "gitlink is not at testSubmoduleMerge tip after merge",
            )
        except grape_errors.GrapeGitError as exc:
            self.fail(f"Uncaught git error executing {exc.gitCommand}:\n{exc.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught System Exit\n{self.get_output()}")

    def testNonConflictingSubmoduleMerge(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertTrue(ret, "grape m did not return true for submodule merge.")
            self.assertTrue(git.isWorkingDirectoryClean(execution_path=self.repo))
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge", "master", execution_path=self.repo)
            )
            git.submodule("update", execution_path=self.repo)
            submodule1 = os.path.join(self.repo, "submodule1")
            self.assertFalse(
                git.diff("testSubmoduleMerge", execution_path=submodule1),
                "gitlink is not at testSubmoduleMerge tip after merge",
            )
        except grape_errors.GrapeGitError as exc:
            self.fail(f"Uncaught git error executing {exc.gitCommand}:\n{exc.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught System Exit\n{self.get_output()}")


class MergeDownSubmoduleConflictCase:
    """Submodule merges that require resolving an inner-repo conflict."""

    def testConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return False for conflicting merge.")
            sub_path = os.path.join(self.repo, "submodule1")
            status = git.status("--porcelain", execution_path=sub_path)
            self.assertTrue("UU" not in status and "AA" in status, f"unexpected status {status} at toplevel")
            status = git.status("--porcelain", execution_path=sub_path)
            self.assertTrue("AA" in status, f"unexpected status {status} in submodule1")

            git.checkout("--ours f1", execution_path=sub_path)
            git.add("f1", execution_path=sub_path)
            git.commit("-m \"resolved conflict with our f1\"", execution_path=sub_path)
            self.setUpConfig()
            self.menu.set_workspace_dir(sub_path)
            ret = self.menu.applyMenuChoice("md", ["--continue"])
            self.assertTrue(
                ret,
                "grape md --continue did not complete successfully after resolving "
                f"submodule conflict\n{self.get_output()}",
            )
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge2", "master", execution_path=sub_path),
                "grape md --continue did not merge in submodule1`s master branch",
            )
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge2", "master", execution_path=self.repo),
                "grape md --continue did not merge in the outer level master branch",
            )
            git.submodule("update", execution_path=self.repo)
            diff = git.diff("testSubmoduleMerge2", execution_path=sub_path)
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")
        except grape_errors.GrapeGitError as exc:
            self.fail(f"Uncaught git error executing {exc.gitCommand}:\n{exc.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught exit\n{self.get_output()}")

    def testConflictingSubmoduleMerge(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            ret = self.menu.applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return False for conflicting merge.")
            sub_path = os.path.join(self.repo, "submodule1")
            status = git.status("--porcelain", execution_path=sub_path)
            self.assertTrue("UU" not in status and "AA" in status, f"unexpected status {status} at toplevel")
            status = git.status("--porcelain", execution_path=sub_path)
            self.assertTrue("AA" in status, f"unexpected status {status} in submodule1")

            git.checkout("--ours f1", execution_path=sub_path)
            git.add("f1", execution_path=sub_path)
            git.commit("-m \"resolved conflict with our f1\"", execution_path=sub_path)
            self.setUpConfig()
            self.menu.set_workspace_dir(sub_path)
            ret = self.menu.applyMenuChoice("m", ["--continue"])
            self.assertTrue(
                ret,
                "grape m --continue did not complete successfully after resolving "
                f"submodule conflict\n{self.get_output()}",
            )
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge2", "master", execution_path=sub_path),
                "grape m --continue did not merge in submodule1`s master branch",
            )
            self.assertTrue(
                git.branchUpToDateWith("testSubmoduleMerge2", "master", execution_path=self.repo),
                "grape m --continue did not merge in the outer level master branch",
            )
            git.submodule("update", execution_path=self.repo)
            diff = git.diff("testSubmoduleMerge2", execution_path=sub_path)
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")
        except grape_errors.GrapeGitError as exc:
            self.fail(f"Uncaught git error executing {exc.gitCommand}:\n{exc.gitOutput}")
        except SystemExit:
            self.fail(f"Uncaught exit\n{self.get_output()}")


class MergeDownNestedSubprojectConflictCase:
    """Nested-subproject conflict flows kept in one shard because setup is heavy."""

    def testConflictingNestedSubprojectMerge(self):
        self.setUpConflictingNestedSubprojectMerge()
        git.checkout(" -b testNestedMerge", execution_path=self.repo)
        self.assertFalse(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.subproject),
            msg=None,
        )
        try:
            ret = self.menu.applyMenuChoice("m", ["--am", "master"])
        except SystemExit as exc:
            self.fail(f"grape m raised exception {exc}")
        self.assertFalse(ret, "grape m did not return False for conflicting merge.")
        status = git.status("--porcelain", execution_path=self.repo)
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertIn("AA", status, f"no conflicts in subproject status \n{status} ")

        git.checkout("--ours f1", execution_path=self.subproject)
        git.add("f1", execution_path=self.subproject)
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")

        ret = self.menu.applyMenuChoice("m", ["--continue"])
        self.assertTrue(ret, "m didn't return successfully after conflict resolution")
        self.assertTrue(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.subproject)
        )
        self.assertTrue(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.repo)
        )

    def testConflictingNestedSubprojectMerge_MD(self):
        self.setUpConflictingNestedSubprojectMerge()
        git.checkout(" -b testNestedMerge", execution_path=self.repo)
        self.assertFalse(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.subproject),
            msg=None,
        )
        try:
            ret = self.menu.applyMenuChoice("md", ["--am", "--public=master"])
        except SystemExit as exc:
            self.fail(f"grape md raised exception {exc}")
        self.assertFalse(ret, "grape md did not return False for conflicting merge.")
        status = git.status("--porcelain", execution_path=self.repo)
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertIn("AA", status, "no conflicts in subproject status")

        git.checkout("--ours f1", execution_path=self.subproject)
        git.add("f1", execution_path=self.subproject)
        status = git.status("--porcelain", execution_path=self.subproject)
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")

        ret = self.menu.applyMenuChoice("md", ["--continue"])
        self.assertTrue(ret, "md didn't return successfully after conflict resolution")
        self.assertTrue(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.subproject)
        )
        self.assertTrue(
            git.branchUpToDateWith("testNestedMerge", "master", execution_path=self.repo)
        )
