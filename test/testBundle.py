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

    def test_bundlecmd_uses_explicit_or_public_branch_tag(self):
        """Test selection of exact and topic-default start tags."""
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
                     patch.object(bundle.git, "shortSHA", return_value="1234567"), \
                     patch.object(bundle.git, "bundle") as create_bundle:
                    result = bundle.bundlecmd(
                        repo=self.repo,
                        args=args,
                        workspace_dir=self.repo,
                    )

                self.assertTrue(result)
                bundle_args = create_bundle.call_args[0][0]
                self.assertIn(f"{expected_tag}..{branch}", bundle_args)


if __name__ == "__main__":
    import unittest
    unittest.main()
