import os

from test import testGrape
from vine import config_parser_global
from vine import grapeGit as git
from vine.option import Option


class TestDiff(testGrape.TestGrape):

    def configure_diff_workspace(self):
        self.setUpConfig()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "publicBranches", "master develop")
        config.set(Option.SECTION_FLOW, "topicPrefixMappings", "feature:develop ?:develop")
        config.set(Option.SECTION_WORKSPACE, "manageSubmodules", "True")
        config.set(Option.SECTION_WORKSPACE, "submoduleTopicPrefixMappings", "feature:foo_dev ?:foo_dev")
        config.set(Option.SECTION_WORKSPACE, "submodulepublicmappings", "master:foo_master develop:foo_dev ?:foo_dev")
        return config

    def testDiffAggregatesMappedSubmoduleBranches(self):
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
        self.assertIn("[workspace] develop...feature/test/demo", output)
        self.assertIn("outer feature change", output)
        self.assertIn("[submodule1]", output)
        self.assertIn("foo_dev...feature/test/demo", output)
        self.assertIn("submodule feature change", output)

    def testDiffRawNameOnlyBetweenTwoBranches(self):
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
                ["--rawDiff", "--name-only", "feature/test/one", "feature/test/two"],
            )
        )

        output = self.get_output()
        self.assertIn("[workspace] feature/test/one feature/test/two", output)
        self.assertIn("branch1.txt", output)
        self.assertIn("branch2.txt", output)
