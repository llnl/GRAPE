import os

from test import testGrape
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine.option import Option


class PublishTestBase(testGrape.TestGrape):
    """Shared helpers for publish-focused test classes."""

    def setUpBranchToFFMerge(self):
        self.branch = "testPublish"
        git.checkout(f"-b {self.branch}", execution_path=self.repo)
        testGrape.writeFile2(os.path.join(self.repo, "f2"))
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"added f2\"", execution_path=self.repo)
        self.setUpConfig()
        self._init_version_file()

    def _init_version_file(self):
        """Create copy of VERSION file for testing publish operation."""
        config = config_parser_global.grapeConfig()
        orig_vers_path = config.get(Option.SECTION_VERSIONING, "file")
        new_version_dir = os.path.dirname(orig_vers_path)
        os.makedirs(os.path.join(self.repo, new_version_dir), exist_ok=True)

        version_copy = os.path.join(self.repo, orig_vers_path)
        with open(version_copy, "a") as handle:
            handle.writelines(["VERSION_ID = v0.0.0"])

        config.set(Option.SECTION_VERSIONING, "file", version_copy)
        git.add(version_copy, execution_path=self.repo)
        git.commit("-m \"VERSION added\"", execution_path=self.repo)

    def setUpDevelopBranch(self):
        git.branch("-f develop master", execution_path=self.repo)

    def assertSuccessfulFastForwardMerge(self, fromBranch="testPublish", toBranch="master"):
        try:
            self.assertEqual(
                git.currentBranch(execution_path=self.repo),
                toBranch,
                "FF merge did not put us on public branch",
            )
            self.assertEqual(
                git.shortSHA(branchName=toBranch, execution_path=self.repo),
                git.shortSHA(branchName=fromBranch, execution_path=self.repo),
            )
        except grape_errors.GrapeGitError as exc:
            self.fail(f"{self.get_output()}\n{exc.gitCommand + exc.gitOutput}")

    def assertSuccessfulSquashMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertEqual(git.currentBranch(execution_path=self.repo), toBranch)
        self.assertNotEqual(
            git.shortSHA(branchName=toBranch, execution_path=self.repo),
            git.shortSHA(branchName=fromBranch, execution_path=self.repo),
        )
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}", execution_path=self.repo))

    def assertSuccessfulSquashCascadeMerge(
        self,
        fromBranch="testPublish",
        toBranch="master",
        cascadeDest="develop",
    ):
        current_branch = git.currentBranch(execution_path=self.repo)
        self.assertEqual(current_branch, cascadeDest)
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}", execution_path=self.repo))
        self.assertFalse(git.diff(f"--name-only {toBranch} {cascadeDest}", execution_path=self.repo))
        self.assertTrue(git.branchUpToDateWith(toBranch, cascadeDest, execution_path=self.repo))
        self.assertFalse(git.branchUpToDateWith(toBranch, fromBranch, execution_path=self.repo))

    def assertGrapePublishWorked(self, args=None, assertFail=False):
        config = config_parser_global.grapeConfig()
        config.ensureSection("project")
        config.set(Option.SECTION_PROJECT, "name", "proj1")

        default_args = [
            "-m",
            "publishing testPublish to master",
            "--noverify",
            "-R",
            "--test",
            "-R",
            "--repo=repo1",
            "-R",
            "--user=user",
            "--noReview",
            "--noUpdateLog",
            "--quiet",
        ]
        try:
            args = (args or []) + default_args
            self.menu.set_workspace_dir(self.repo)
            ret = self.menu.applyMenuChoice("publish", args=args)
            self.assertEqual(ret, not assertFail, msg="publish returned " + str(ret))
        except SystemExit as exc:
            self.fail(f"{self.get_output()}\n{exc.message}")

    def assertGrapePublishFailed(self, args=None):
        self.assertGrapePublishWorked(args=args, assertFail=True)
