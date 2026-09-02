import os

from test import testGrape
from vine import config_parser_global
from vine import grapeGit as git
from vine.option import Option


class TestCommit(testGrape.TestGrape):

    def setUp(self):
        super(TestCommit, self).setUp()
        git.clearGitConfigFlags()
        git.addGitConfigFlag("-c protocol.file.allow=always")
        git.addGitConfigFlag("-c init.defaultBranch=master")

    def configure_commit_workspace(self):
        self.setUpConfig()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_WORKSPACE, "manageSubmodules", "True")
        return config

    def add_submodule(self, *, name, prefix):
        self.menu.applyMenuChoice(
            "addSubproject",
            [
                f"--name={name}",
                f"--prefix={prefix}",
                f"--url={self.repo}-origin",
                "--branch=master",
                "--submodule",
                "--noverify",
            ],
        )
        git.commit(f'-m "add {name} submodule"', execution_path=self.repo)
        return os.path.join(self.repo, *prefix.split("/"))

    def testCommitStillHandlesTopLevelOnlyChanges(self):
        self.configure_commit_workspace()

        root_file = os.path.join(self.repo, "root_only.txt")
        with open(root_file, "w", encoding="utf-8") as handle:
            handle.write("root change\n")
        git.add("root_only.txt", execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice("commit", ["-m", "\"root only\""]))
        self.assertFalse(git.status("--porcelain", execution_path=self.repo))

    def testCommitNarrowsToRequestedNestedSubprojectPath(self):
        self.configure_commit_workspace()
        self.assertCanAddNewSubproject(self, execution_path=self.repo)

        nested_file = os.path.join(self.subproject, "f1")
        with open(nested_file, "w", encoding="utf-8") as handle:
            handle.write("nested change\n")
        git.add("f1", execution_path=self.subproject)

        unrelated_root = os.path.join(self.repo, "unrelated.txt")
        with open(unrelated_root, "w", encoding="utf-8") as handle:
            handle.write("workspace change\n")
        git.add("unrelated.txt", execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            self.assertTrue(
                self.menu.applyMenuChoice("commit", ["-m", "\"nested only\"", "subs/subproject1/f1"])
            )
        finally:
            os.chdir(previous_cwd)

        self.assertFalse(git.status("--porcelain", execution_path=self.subproject))
        root_status = git.status("--porcelain", execution_path=self.repo)
        self.assertIn("unrelated.txt", root_status)
        self.assertNotIn("subs/subproject1", root_status)

    def testCommitAncestorPathIncludesSubmoduleGitlinkButNotUnrelatedRootChanges(self):
        self.configure_commit_workspace()
        submodule_path = self.add_submodule(name="care", prefix="tpl/care")

        submodule_file = os.path.join(submodule_path, "testRepoFile")
        with open(submodule_file, "a", encoding="utf-8") as handle:
            handle.write("submodule change\n")
        git.add("testRepoFile", execution_path=submodule_path)

        unrelated_root = os.path.join(self.repo, "unrelated.txt")
        with open(unrelated_root, "w", encoding="utf-8") as handle:
            handle.write("workspace change\n")
        git.add("unrelated.txt", execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            self.assertTrue(self.menu.applyMenuChoice("commit", ["-m", "\"tpl only\"", "tpl"]))
        finally:
            os.chdir(previous_cwd)

        self.assertFalse(git.status("--porcelain", execution_path=submodule_path))
        root_status = git.status("--porcelain", execution_path=self.repo)
        self.assertIn("unrelated.txt", root_status)
        self.assertNotIn("tpl/care", root_status)

    def testCommitResolvesScopedPathsRelativeToSubmoduleCwd(self):
        self.configure_commit_workspace()
        submodule_path = self.add_submodule(name="submodule1", prefix="submodule1")

        submodule_file = os.path.join(submodule_path, "testRepoFile")
        with open(submodule_file, "a", encoding="utf-8") as handle:
            handle.write("cwd scoped change\n")
        git.add("testRepoFile", execution_path=submodule_path)

        unrelated_root = os.path.join(self.repo, "unrelated.txt")
        with open(unrelated_root, "w", encoding="utf-8") as handle:
            handle.write("workspace change\n")
        git.add("unrelated.txt", execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(submodule_path)
        try:
            self.assertTrue(self.menu.applyMenuChoice("commit", ["-m", "\"submodule cwd only\"", "testRepoFile"]))
        finally:
            os.chdir(previous_cwd)

        self.assertFalse(git.status("--porcelain", execution_path=submodule_path))
        root_status = git.status("--porcelain", execution_path=self.repo)
        self.assertIn("unrelated.txt", root_status)
        self.assertNotIn("submodule1", root_status)
