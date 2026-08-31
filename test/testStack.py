"""Tests for local stacked-branch foundations."""

import os

from vine import config_parser_global
from vine import grapeGit as git
from vine import stack
from vine.option import Option
from test import testGrape


class TestStack(testGrape.TestGrape):
    """Exercise manifest persistence, target resolution, start, and add."""

    def setUp(self):
        self._config_path_function = config_parser_global.get_env_config_path
        config_parser_global.get_env_config_path = lambda: self.defaultWorkingDirectory
        super(TestStack, self).setUp()
        self.setUpConfig()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "topicPrefixMappings", "feature:master ?:master")
        config.set(Option.SECTION_FLOW, "topicDestinationMappings", "none")

    def tearDown(self):
        config_parser_global.get_env_config_path = self._config_path_function
        super(TestStack, self).tearDown()

    def testManifestRoundTripAndTargetResolution(self):
        manifest = stack.StackManifest.create(
            "widgets", "alice", "feature", "master", "master")
        bottom = stack.StackLevel("level-one", "model", "feature/alice/widgets/model")
        bottom.repositories["."] = stack.StackRepository(
            bottom.branch, "master", git.SHA(execution_path=self.repo))
        top = stack.StackLevel("level-two", "api", "feature/alice/widgets/api")
        top.repositories["."] = stack.StackRepository(
            top.branch, bottom.branch, git.SHA(execution_path=self.repo))
        manifest.levels.extend([bottom, top])

        store = stack.StackStore(self.repo)
        with store.locked():
            store.save(manifest)
        loaded = store.find("widgets")

        self.assertEqual(loaded.to_dict(), manifest.to_dict())
        resolver = stack.IntegrationTargetResolver(loaded)
        self.assertEqual(resolver.target(bottom.name), "master")
        self.assertEqual(resolver.target(top.branch), bottom.branch)

    def testStartAndAddCreateARecordedLinearStack(self):
        started = self.menu.applyMenuChoice(
            "stack", ["start", "widgets", "model", "--type=feature",
                      "--start=master", "--user=alice", "--nopush",
                      "--noRecurse"])
        self.assertTrue(started)
        bottom_branch = "feature/alice/widgets/model"
        self.assertEqual(git.currentBranch(execution_path=self.repo), bottom_branch)

        with open(os.path.join(self.repo, "local-notes.txt"), "w") as stream:
            stream.write("untracked notes survive branch creation\n")

        added = self.menu.applyMenuChoice(
            "stack", ["add", "api", "--nopush", "--noRecurse"])
        self.assertTrue(added)
        top_branch = "feature/alice/widgets/api"
        self.assertEqual(git.currentBranch(execution_path=self.repo), top_branch)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "local-notes.txt")))
        self.assertTrue(git.branchUpToDateWith(
            top_branch, bottom_branch, execution_path=self.repo))

        manifest = stack.StackStore(self.repo).find(branch=top_branch)
        self.assertEqual([level.name for level in manifest.levels], ["model", "api"])
        self.assertEqual(
            stack.integration_target_for_branch(top_branch, self.repo),
            bottom_branch)
        self.assertEqual(
            config_parser_global.grapeConfig().getPublicBranchFor(top_branch),
            "master")

    def testStartDryRunDoesNotCreateBranchOrManifest(self):
        result = self.menu.applyMenuChoice(
            "stack", ["start", "widgets", "model", "--type=feature",
                      "--start=master", "--user=alice", "--nopush",
                      "--noRecurse", "--dry-run"])

        self.assertTrue(result)
        self.assertFalse(git.hasBranch(
            "feature/alice/widgets/model", execution_path=self.repo))
        self.assertEqual(stack.StackStore(self.repo).list(), [])
