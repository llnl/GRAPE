import os

from test import testGrape
from test import testNestedSubproject
from vine import grapeGit as git


class MergeDownTestBase(testGrape.TestGrape):
    """Shared merge-down setup helpers reused across shard files."""

    def setUpMerge(self):
        git.branch("testMerge", execution_path=self.repo)
        f2_path = os.path.join(self.repo, "f2")
        testGrape.writeFile2(f2_path)
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"f2\"", execution_path=self.repo)
        git.checkout("testMerge", execution_path=self.repo)
        self.setUpConfig()
        self.menu.set_workspace_dir(self.repo)

    def setUpConflictingMerge(self):
        self.setUpMerge()
        f2_path = os.path.join(self.repo, "f2")
        testGrape.writeFile3(f2_path)
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"f2\"", execution_path=self.repo)

    def createTestSubmodule(self, *, execution_path):
        git.clone(
            argstr="--mirror",
            source_repo=self.repo,
            clone_repo=self.repos[1],
            execution_path=execution_path,
        )
        git.submodule(f"add {self.repos[1]} submodule1", execution_path=self.repo)
        # The bootstrap repository is a GRAPE workspace, but this repository
        # is being used as a submodule.  Keep the submodule unconfigured so
        # workspace discovery continues to resolve commands to the outer
        # project.  Push the change because later merge-down setup fetches
        # public branches from the submodule's origin.
        submodule_path = os.path.join(self.repo, "submodule1")
        git.rm(".grapeconfig", execution_path=submodule_path)
        git.commit(
            "-m \"removed workspace config from submodule\"",
            execution_path=submodule_path,
        )
        git.push("origin master", execution_path=submodule_path)
        git.commit("-m \"added submodule1\"", execution_path=self.repo)

    def setUpNonConflictingSubmoduleMerge(self):
        self.createTestSubmodule(execution_path=self.defaultWorkingDirectory)
        git.branch("testSubmoduleMerge", execution_path=self.repo)
        submodule1 = os.path.join(self.repo, "submodule1")
        git.checkout("master", execution_path=submodule1)
        f1_path = os.path.join(submodule1, "f1")
        testGrape.writeFile2(f1_path)
        git.add("f1", execution_path=submodule1)
        git.commit("-m \"added f2 as f1\"", execution_path=submodule1)
        git.commit(
            "submodule1 -m \"updated submodule gitlink on master branch\"",
            execution_path=self.repo,
        )

        git.checkout("testSubmoduleMerge", execution_path=self.repo)
        git.submodule("update", execution_path=self.repo)
        git.checkout("-b testSubmoduleMerge", execution_path=submodule1)
        f2_path = os.path.join(submodule1, "f2")
        testGrape.writeFile3(f2_path)
        git.add("f2", execution_path=submodule1)
        git.commit("-m \"added f3 as f2\"", execution_path=submodule1)
        git.commit(
            "-a -m \"updated gitlink on branch testSubmoduleMerge\"",
            execution_path=self.repo,
        )
        self.setUpConfig()
        self.menu.set_workspace_dir(self.repo)

    def setUpConflictingSubmoduleMerge(self):
        self.createTestSubmodule(execution_path=self.defaultWorkingDirectory)
        git.branch("testSubmoduleMerge2", execution_path=self.repo)
        sub_path = os.path.join(self.repo, "submodule1")
        git.branch("testSubmoduleMerge2", execution_path=sub_path)
        git.checkout("master", execution_path=sub_path)
        f1_path = os.path.join(sub_path, "f1")
        testGrape.writeFile2(f1_path)
        git.add("f1", execution_path=sub_path)
        git.commit("-m \"added f2 as f1\"", execution_path=sub_path)
        git.commit(
            "submodule1 -m \"updated submodule gitlink on master branch\"",
            execution_path=self.repo,
        )
        git.checkout("testSubmoduleMerge2", execution_path=self.repo)
        git.submodule("update", execution_path=self.repo)
        git.checkout("testSubmoduleMerge2", execution_path=sub_path)
        testGrape.writeFile3(f1_path)
        git.add("f1", execution_path=sub_path)
        git.commit("-m \"added f3 as f1\"", execution_path=sub_path)
        git.commit(
            "submodule1 -m \"updated submodule gitlink on testSubmoduleMerge branch\"",
            execution_path=self.repo,
        )
        self.setUpConfig()
        self.menu.set_workspace_dir(self.repo)

    def setUpConflictingNestedSubprojectMerge(self):
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(
            self, execution_path=self.defaultWorkingDirectory
        )
        git.checkout("master", execution_path=self.subproject)
        git.branch("testNestedMerge", execution_path=self.subproject)
        f1_path = os.path.join(self.subproject, "f1")
        testGrape.writeFile2(f1_path)
        git.add("f1", execution_path=self.subproject)
        git.commit("-m \"added f2 as f1\"", execution_path=self.subproject)
        git.checkout("testNestedMerge", execution_path=self.subproject)
        testGrape.writeFile3(f1_path)
        git.add("f1", execution_path=self.subproject)
        git.commit("-m \"added f1 as f1\"", execution_path=self.subproject)
