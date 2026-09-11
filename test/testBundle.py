import os
from unittest.mock import patch

from test import testGrape
from vine import bundle
from vine import config_parser_global
from vine.option import Option


class TestBundle(testGrape.TestGrape):

    def test_bundle_given_defaults(self):
        """Test 'bundle' command (smoke test)."""
        result = self.menu.applyMenuChoice("bundle")
        self.assertTrue(result, "Failed 'bundle' command smoke test.")

    @patch("vine.bundle.multi_repo_cmd_launcher.MultiRepoCommandLauncher")
    @patch("vine.bundle.git.describe", return_value="v1.0")
    @patch("vine.bundle.git.fetch")
    def test_bundle_resolves_topic_branch_and_accepts_explicit_tag(
            self, _fetch, _describe, launcher_cls):
        """Test topic-to-public mapping and the explicit start-tag option."""
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "publicBranches", "master develop")
        config.set(
            Option.SECTION_FLOW,
            "topicPrefixMappings",
            "feature:develop bugfix:develop hotfix:master ?:develop",
        )

        result = self.menu.applyMenuChoice(
            "bundle",
            [
                "--noRecurse",
                "--branches=feature/user/example bugfix/user/example hotfix/user/example",
            ],
        )

        self.assertTrue(result)
        launch_args = launcher_cls.call_args[1]["globalArgs"]
        self.assertIsNone(launch_args["tag"])
        self.assertEqual(
            {
                "feature/user/example": "develop",
                "bugfix/user/example": "develop",
                "hotfix/user/example": "master",
            },
            launch_args["branchToPublicBranchMap"],
        )

        launcher_cls.reset_mock()
        result = self.menu.applyMenuChoice(
            "bundle",
            [
                "--noRecurse",
                "--branches=unmapped/user/example",
                "--tag=explicit-start",
            ],
        )

        self.assertTrue(result)
        launch_args = launcher_cls.call_args[1]["globalArgs"]
        self.assertEqual("explicit-start", launch_args["tag"])
        self.assertEqual({}, launch_args["branchToPublicBranchMap"])

    def test_bundlecmd_uses_explicit_tag_or_topic_common_ancestor(self):
        """Test selection of exact and topic common-ancestor start points."""
        branch = "feature/user/example"
        cases = (
            (None, "patched/develop"),
            ("explicit-start", "explicit-start"),
        )

        for explicit_tag, expected_tag in cases:
            with self.subTest(explicit_tag=explicit_tag):
                args = {
                    "branchList": [branch],
                    "tags": {branch: "v*"},
                    "prefix": "patched",
                    "tag": explicit_tag,
                    "branchToPublicBranchMap": (
                        {} if explicit_tag else {branch: "develop"}
                    ),
                    "describePattern": "v*",
                    "submoduleReverseBranchMap": None,
                    "nestedSubprojectBranchToTagMap": None,
                    "--outfile": "test.bundle",
                }
                remote_ref = f"remotes/origin/{branch}"
                with patch.object(bundle.git, "allBranches", return_value=[remote_ref]), \
                     patch.object(bundle.git, "safeForceBranchToOriginRef", return_value=True), \
                     patch.object(bundle.git, "describe", side_effect=["old", "new"]), \
                     patch.object(bundle.git, "mergeBase", return_value="common-ancestor"), \
                     patch.object(bundle.git, "shortSHA", return_value="1234567"), \
                     patch.object(bundle.git, "bundle") as create_bundle:
                    result = bundle.bundlecmd(
                        repo=self.repo,
                        args=args,
                        workspace_dir=self.repo,
                    )

                self.assertTrue(result)
                bundle_args = create_bundle.call_args[0][0]
                expected_start = (
                    "common-ancestor" if explicit_tag is None else expected_tag
                )
                self.assertIn(f"{expected_start}..{branch}", bundle_args)

    def test_bundlecmd_uses_public_tag_for_public_branches(self):
        """Public branches should continue to use the tag as the range start."""
        branch = "develop"
        args = {
            "branchList": [branch],
            "tags": {branch: "v*"},
            "prefix": "patched",
            "tag": None,
            "branchToPublicBranchMap": {branch: branch},
            "describePattern": "v*",
            "submoduleReverseBranchMap": None,
            "nestedSubprojectBranchToTagMap": None,
            "--outfile": "test.bundle",
        }
        remote_ref = f"remotes/origin/{branch}"
        with patch.object(bundle.git, "allBranches", return_value=[remote_ref]), \
             patch.object(bundle.git, "safeForceBranchToOriginRef", return_value=True), \
             patch.object(bundle.git, "describe", side_effect=["old", "new"]), \
             patch.object(bundle.git, "shortSHA", return_value="1234567"), \
             patch.object(bundle.git, "mergeBase") as merge_base, \
             patch.object(bundle.git, "bundle") as create_bundle:
            result = bundle.bundlecmd(
                repo=self.repo,
                args=args,
                workspace_dir=self.repo,
            )

        self.assertTrue(result)
        self.assertIn("patched/develop..develop", create_bundle.call_args[0][0])
        merge_base.assert_not_called()

    @patch("vine.bundle.config_parser_workspace.GrapeConfigParserWorkspace")
    @patch("vine.bundle.multi_repo_cmd_launcher.MultiRepoCommandLauncher")
    @patch("vine.bundle.git.describe", return_value="v1.0")
    @patch("vine.bundle.git.fetch")
    def test_bundle_selects_submodule_branches(
            self, _fetch, _describe, launcher_cls, workspace_config_cls):
        """Topic branches should become the default recursive branch list."""
        topic_branch = "feature/user/example"
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "publicBranches", "master develop")
        config.set(
            Option.SECTION_FLOW,
            "topicPrefixMappings",
            "feature:develop ?:develop",
        )
        config.set(Option.SECTION_PATCH, "submoduleBranches", "ale3d")
        workspace_config_cls.return_value.getMapping.return_value = {
            "master": "master",
            "develop": "ale3d",
        }

        result = self.menu.applyMenuChoice(
            "bundle",
            [f"--branches={topic_branch}"],
        )

        self.assertTrue(result)
        self.assertEqual(2, launcher_cls.call_count)
        submodule_launch_args = launcher_cls.call_args_list[1].kwargs["globalArgs"]
        self.assertEqual([topic_branch], submodule_launch_args["branchList"])
        self.assertEqual(
            {topic_branch: "ale3d"},
            submodule_launch_args["branchToPublicBranchMap"],
        )

        launcher_cls.reset_mock()
        result = self.menu.applyMenuChoice(
            "bundle",
            ["--branches=develop"],
        )

        self.assertTrue(result)
        submodule_launch_args = launcher_cls.call_args_list[1].kwargs["globalArgs"]
        self.assertEqual(["ale3d"], submodule_launch_args["branchList"])

        launcher_cls.reset_mock()
        result = self.menu.applyMenuChoice(
            "bundle",
            [f"--branches={topic_branch}", "--submoduleBranches=ale3d"],
        )

        self.assertTrue(result)
        submodule_launch_args = launcher_cls.call_args_list[1].kwargs["globalArgs"]
        self.assertEqual(["ale3d"], submodule_launch_args["branchList"])


if __name__ == "__main__":
    import unittest
    unittest.main()
