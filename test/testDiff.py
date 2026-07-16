import os
from unittest.mock import patch

from test import testGrape
from vine import config_parser_global
from vine import grapeGit as git
from vine.option import Option


class TestDiff(testGrape.TestGrape):

    def configure_diff_workspace(self):
        """Configure a workspace layout suitable for `grape diff` tests.

        Returns:
            ConfigParser: The mutable GRAPE config used by the test workspace.
        """
        self.setUpConfig()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "publicBranches", "master develop")
        config.set(Option.SECTION_FLOW, "topicPrefixMappings", "feature:develop ?:develop")
        config.set(Option.SECTION_WORKSPACE, "manageSubmodules", "True")
        config.set(Option.SECTION_WORKSPACE, "submoduleTopicPrefixMappings", "feature:foo_dev ?:foo_dev")
        config.set(Option.SECTION_WORKSPACE, "submodulepublicmappings", "master:foo_master develop:foo_dev ?:foo_dev")
        return config

    def testDiffAggregatesMappedSubmoduleBranches(self):
        """Verify one-ref diffs honor submodule public-branch mappings."""
        self.configure_diff_workspace()

        git.branch("foo_master master", execution_path=self.repo)
        git.branch("foo_dev develop", execution_path=self.repo)
        git.push("origin foo_master foo_dev", execution_path=self.repo)

        self.menu.applyMenuChoice(
            "addSubproject",
            [
                "--name=submodule1",
                "--prefix=submodule1",
                f"--url={self.repo}-origin",
                "--branch=foo_master",
                "--submodule",
                "--noverify",
            ],
        )
        git.commit('-m "add submodule"', execution_path=self.repo)
        git.push("origin master", execution_path=self.repo)
        git.checkout("-B develop master", execution_path=self.repo)
        git.push("--force origin develop", execution_path=self.repo)

        git.checkout("-b feature/test/demo develop", execution_path=self.repo)
        with open(self.file1, "a", encoding="utf-8") as handle:
            handle.write("outer feature change\n")
        git.add("testRepoFile", execution_path=self.repo)
        git.commit('-m "outer feature change"', execution_path=self.repo)

        submodule_path = os.path.join(self.repo, "submodule1")
        submodule_file = os.path.join(submodule_path, "testRepoFile")
        git.checkout("-b feature/test/demo origin/foo_dev", execution_path=submodule_path)
        with open(submodule_file, "a", encoding="utf-8") as handle:
            handle.write("submodule feature change\n")
        git.add("testRepoFile", execution_path=submodule_path)
        git.commit('-m "submodule feature change"', execution_path=submodule_path)

        git.add("submodule1", execution_path=self.repo)
        git.commit('-m "update gitlink"', execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice("diff", ["develop"]))

        output = self.get_output()
        self.assertIn("[workspace] develop", output)
        self.assertIn("outer feature change", output)
        self.assertIn("[submodule1]", output)
        self.assertIn("foo_dev", output)
        self.assertIn("submodule feature change", output)

    def testDiffDefaultsToWorktreeVsIndex(self):
        """Verify no-ref diffs only show worktree changes by default."""
        self.configure_diff_workspace()

        tracked_path = os.path.join(self.repo, "tracked.txt")
        staged_only_path = os.path.join(self.repo, "staged_only.txt")

        with open(tracked_path, "w", encoding="utf-8") as handle:
            handle.write("base\n")
        git.add("tracked.txt", execution_path=self.repo)
        git.commit('-m "add tracked file"', execution_path=self.repo)

        with open(tracked_path, "a", encoding="utf-8") as handle:
            handle.write("staged\n")
        git.add("tracked.txt", execution_path=self.repo)

        with open(tracked_path, "a", encoding="utf-8") as handle:
            handle.write("unstaged\n")

        with open(staged_only_path, "w", encoding="utf-8") as handle:
            handle.write("staged\n")
        git.add("staged_only.txt", execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice("diff"))

        output = self.get_output()
        rendered_diff = output[output.index("[workspace] <worktree>"):]
        self.assertIn("[workspace] <worktree>", output)
        self.assertIn("tracked.txt", rendered_diff)
        self.assertIn("+unstaged", rendered_diff)
        self.assertNotIn("staged_only.txt", rendered_diff)

    def testDiffCachedDefaultsToIndexVsHead(self):
        """Verify `--cached` shows staged changes without unstaged worktree edits."""
        self.configure_diff_workspace()

        tracked_path = os.path.join(self.repo, "tracked.txt")
        staged_only_path = os.path.join(self.repo, "staged_only.txt")

        with open(tracked_path, "w", encoding="utf-8") as handle:
            handle.write("base\n")
        git.add("tracked.txt", execution_path=self.repo)
        git.commit('-m "add tracked file"', execution_path=self.repo)

        with open(tracked_path, "a", encoding="utf-8") as handle:
            handle.write("staged\n")
        git.add("tracked.txt", execution_path=self.repo)

        with open(tracked_path, "a", encoding="utf-8") as handle:
            handle.write("unstaged\n")

        with open(staged_only_path, "w", encoding="utf-8") as handle:
            handle.write("staged only\n")
        git.add("staged_only.txt", execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice("diff", ["--cached"]))

        output = self.get_output()
        rendered_diff = output[output.index("[workspace] --cached"):]
        self.assertIn("[workspace] --cached", output)
        self.assertIn("tracked.txt", rendered_diff)
        self.assertIn("staged_only.txt", rendered_diff)
        self.assertIn("+staged", rendered_diff)
        self.assertNotIn("+unstaged", rendered_diff)

    def testDiffCachedWithRefComparesIndexAgainstRef(self):
        """Verify `--cached <ref>` compares staged changes against the requested ref."""
        self.configure_diff_workspace()

        git.checkout("-B develop master", execution_path=self.repo)
        git.checkout("-b feature/test/cached develop", execution_path=self.repo)

        with open(self.file1, "a", encoding="utf-8") as handle:
            handle.write("cached branch change\n")
        git.add("testRepoFile", execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice("diff", ["--cached", "develop"]))

        output = self.get_output()
        rendered_diff = output[output.index("[workspace] --cached develop"):]
        self.assertIn("[workspace] --cached develop", output)
        self.assertIn("cached branch change", rendered_diff)

    def testDiffNameOnlyBetweenTwoBranchesDefaultsToRawDiff(self):
        """Verify two-ref diffs default to raw name-only comparisons."""
        self.configure_diff_workspace()

        git.checkout("-B develop master", execution_path=self.repo)
        git.checkout("-b feature/test/one develop", execution_path=self.repo)
        with open(os.path.join(self.repo, "branch1.txt"), "w", encoding="utf-8") as handle:
            handle.write("branch one\n")
        git.add("branch1.txt", execution_path=self.repo)
        git.commit('-m "branch one change"', execution_path=self.repo)

        git.checkout("develop", execution_path=self.repo)
        git.checkout("-b feature/test/two develop", execution_path=self.repo)
        with open(os.path.join(self.repo, "branch2.txt"), "w", encoding="utf-8") as handle:
            handle.write("branch two\n")
        git.add("branch2.txt", execution_path=self.repo)
        git.commit('-m "branch two change"', execution_path=self.repo)

        self.assertTrue(
            self.menu.applyMenuChoice(
                "diff",
                ["--name-only", "feature/test/one", "feature/test/two"],
            )
        )

        output = self.get_output()
        self.assertIn("[workspace] feature/test/one feature/test/two", output)
        self.assertIn("branch1.txt", output)
        self.assertIn("branch2.txt", output)

    def testDiffNarrowsToRequestedWorkspacePath(self):
        """Verify `-- <path>` limits diffs to the requested workspace-relative path."""
        self.configure_diff_workspace()

        git.checkout("-B develop master", execution_path=self.repo)
        git.checkout("-b feature/test/path develop", execution_path=self.repo)

        with open(self.file1, "a", encoding="utf-8") as handle:
            handle.write("tracked path change\n")
        extra_path = os.path.join(self.repo, "other.txt")
        with open(extra_path, "w", encoding="utf-8") as handle:
            handle.write("other change\n")
        git.add("testRepoFile other.txt", execution_path=self.repo)
        git.commit('-m "path filtered change"', execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            self.assertTrue(self.menu.applyMenuChoice("diff", ["develop", "--", "testRepoFile"]))
        finally:
            os.chdir(previous_cwd)

        output = self.get_output()
        rendered_diff = output[output.index("[workspace] develop -- testRepoFile"):]
        self.assertIn("[workspace] develop -- testRepoFile", output)
        self.assertIn("testRepoFile", rendered_diff)
        self.assertNotIn("other.txt", rendered_diff)

    def testDiffResolvesPathspecsRelativeToSubmoduleCwd(self):
        """Verify file scope from a submodule CWD maps to submodule-local pathspecs."""
        self.configure_diff_workspace()

        git.branch("foo_master master", execution_path=self.repo)
        git.branch("foo_dev develop", execution_path=self.repo)
        git.push("origin foo_master foo_dev", execution_path=self.repo)

        self.menu.applyMenuChoice(
            "addSubproject",
            [
                "--name=submodule1",
                "--prefix=submodule1",
                f"--url={self.repo}-origin",
                "--branch=foo_master",
                "--submodule",
                "--noverify",
            ],
        )
        git.commit('-m "add submodule"', execution_path=self.repo)
        git.push("origin master", execution_path=self.repo)
        git.checkout("-B develop master", execution_path=self.repo)
        git.push("--force origin develop", execution_path=self.repo)

        git.checkout("-b feature/test/demo develop", execution_path=self.repo)
        with open(self.file1, "a", encoding="utf-8") as handle:
            handle.write("outer feature change\n")
        git.add("testRepoFile", execution_path=self.repo)
        git.commit('-m "outer feature change"', execution_path=self.repo)

        submodule_path = os.path.join(self.repo, "submodule1")
        submodule_file = os.path.join(submodule_path, "testRepoFile")
        git.checkout("-b feature/test/demo origin/foo_dev", execution_path=submodule_path)
        with open(submodule_file, "a", encoding="utf-8") as handle:
            handle.write("submodule feature change\n")
        git.add("testRepoFile", execution_path=submodule_path)
        git.commit('-m "submodule feature change"', execution_path=submodule_path)

        git.add("submodule1", execution_path=self.repo)
        git.commit('-m "update gitlink"', execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(submodule_path)
        try:
            self.assertTrue(self.menu.applyMenuChoice("diff", ["develop", "--", "testRepoFile"]))
        finally:
            os.chdir(previous_cwd)

        output = self.get_output()
        self.assertIn("[submodule1] origin/foo_dev -- testRepoFile", output)
        self.assertIn("submodule feature change", output)
        self.assertNotIn("[workspace] develop -- submodule1/testRepoFile", output)

    def testDiffAncestorPathIncludesSubmoduleGitlinkAndRepoDiff(self):
        """Verify ancestor directory scopes include both gitlink and submodule diffs."""
        self.configure_diff_workspace()

        git.branch("foo_master master", execution_path=self.repo)
        git.branch("foo_dev develop", execution_path=self.repo)
        git.push("origin foo_master foo_dev", execution_path=self.repo)

        self.menu.applyMenuChoice(
            "addSubproject",
            [
                "--name=care",
                "--prefix=tpl/care",
                f"--url={self.repo}-origin",
                "--branch=foo_master",
                "--submodule",
                "--noverify",
            ],
        )
        git.commit('-m "add nested submodule"', execution_path=self.repo)
        git.push("origin master", execution_path=self.repo)
        git.checkout("-B develop master", execution_path=self.repo)
        git.push("--force origin develop", execution_path=self.repo)

        git.checkout("-b feature/test/ancestor develop", execution_path=self.repo)
        submodule_path = os.path.join(self.repo, "tpl", "care")
        submodule_file = os.path.join(submodule_path, "testRepoFile")
        git.checkout("-b feature/test/ancestor origin/foo_dev", execution_path=submodule_path)
        with open(submodule_file, "a", encoding="utf-8") as handle:
            handle.write("ancestor scoped submodule change\n")
        git.add("testRepoFile", execution_path=submodule_path)
        git.commit('-m "submodule change under ancestor path"', execution_path=submodule_path)

        git.add("tpl/care", execution_path=self.repo)
        git.commit('-m "update nested submodule gitlink"', execution_path=self.repo)

        previous_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            self.assertTrue(self.menu.applyMenuChoice("diff", ["develop", "--", "tpl"]))
        finally:
            os.chdir(previous_cwd)

        output = self.get_output()
        self.assertIn("[workspace] develop -- tpl", output)
        self.assertIn("tpl/care", output)
        self.assertIn("[tpl/care] origin/foo_dev -- .", output)
        self.assertIn("ancestor scoped submodule change", output)

    def testDiffUsesPagerWhenAvailable(self):
        """Verify interactive diff output is routed through the pager helper."""
        self.configure_diff_workspace()

        git.checkout("-B develop master", execution_path=self.repo)
        git.checkout("-b feature/test/paged develop", execution_path=self.repo)
        with open(self.file1, "a", encoding="utf-8") as handle:
            handle.write("paged change\n")
        git.add("testRepoFile", execution_path=self.repo)
        git.commit('-m "paged change"', execution_path=self.repo)

        with patch("vine.diff._page_output_if_tty", return_value=True) as mock_page:
            self.assertTrue(self.menu.applyMenuChoice("diff", ["develop"]))

        mock_page.assert_called_once()
        rendered_output, pager_workspace = mock_page.call_args.args
        self.assertEqual(pager_workspace, self.repo)
        self.assertIn("[workspace] develop", rendered_output)
        self.assertIn("paged change", rendered_output)
