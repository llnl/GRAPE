"""Tests for local stacked-branch foundations."""

import os
from unittest import mock

from vine import config_parser_global
from vine import grapeGit as git
from vine import mergeDown
from vine import stack
from vine import stack_review
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

    def _createCommittedTwoLevelStack(self):
        """Create two non-empty levels and return their branch names."""
        self.assertTrue(self.menu.applyMenuChoice(
            "stack", ["start", "widgets", "model", "--type=feature",
                      "--start=master", "--user=alice", "--nopush",
                      "--noRecurse"]))
        bottom = "feature/alice/widgets/model"
        bottom_file = os.path.join(self.repo, "bottom.txt")
        with open(bottom_file, "w") as stream:
            stream.write("bottom\n")
        git.add("bottom.txt", execution_path=self.repo)
        git.commit('-m "bottom change"', execution_path=self.repo)

        self.assertTrue(self.menu.applyMenuChoice(
            "stack", ["add", "api", "--nopush", "--noRecurse"]))
        top = "feature/alice/widgets/api"
        top_file = os.path.join(self.repo, "top.txt")
        with open(top_file, "w") as stream:
            stream.write("top\n")
        git.add("top.txt", execution_path=self.repo)
        git.commit('-m "top change"', execution_path=self.repo)
        return bottom, top

    def testSyncRebasesDescendantAfterParentChanges(self):
        """A changed lower level is replayed through every descendant."""
        bottom, top = self._createCommittedTwoLevelStack()
        old_top = git.SHA(top, execution_path=self.repo)
        git.checkout(bottom, execution_path=self.repo)
        with open(os.path.join(self.repo, "later.txt"), "w") as stream:
            stream.write("later parent edit\n")
        git.add("later.txt", execution_path=self.repo)
        git.commit('-m "later parent change"', execution_path=self.repo)

        result = self.menu.applyMenuChoice(
            "stack", ["sync", "--from=model", "--rebase", "--noFetch"])

        self.assertTrue(result)
        self.assertEqual(top, git.currentBranch(execution_path=self.repo))
        self.assertTrue(git.branchUpToDateWith(
            top, bottom, execution_path=self.repo))
        self.assertNotEqual(old_top, git.SHA(top, execution_path=self.repo))
        manifest = stack.StackStore(self.repo).find("widgets")
        self.assertEqual(
            git.SHA(top, execution_path=self.repo),
            manifest.level(top).repositories["."].tip)

    def testSyncMergeIncorporatesChangedParent(self):
        """Merge strategy preserves the child and merges the latest parent."""
        bottom, top = self._createCommittedTwoLevelStack()
        git.checkout(bottom, execution_path=self.repo)
        with open(os.path.join(self.repo, "merge-parent.txt"), "w") as stream:
            stream.write("merge parent edit\n")
        git.add("merge-parent.txt", execution_path=self.repo)
        git.commit('-m "merge parent change"', execution_path=self.repo)

        result = self.menu.applyMenuChoice(
            "stack", ["sync", "--from=model", "--merge", "--noFetch"])

        self.assertTrue(result)
        self.assertTrue(git.branchUpToDateWith(
            top, bottom, execution_path=self.repo))
        self.assertEqual(
            2, int(git.gitcmd(
                "rev-list --parents -n 1 HEAD", "inspect merge",
                execution_path=self.repo).count(" ")))

    def testSyncRejectsUnexpectedRemoteMovement(self):
        """Recorded leases stop synchronization after a remote branch moves."""
        self.assertTrue(self.menu.applyMenuChoice(
            "stack", ["start", "widgets", "model", "--type=feature",
                      "--start=master", "--user=alice", "--noRecurse"]))
        bottom = "feature/alice/widgets/model"
        with open(os.path.join(self.repo, "remote-move.txt"), "w") as stream:
            stream.write("local parent commit\n")
        git.add("remote-move.txt", execution_path=self.repo)
        git.commit('-m "local parent commit"', execution_path=self.repo)
        self.assertTrue(self.menu.applyMenuChoice(
            "stack", ["add", "api", "--noRecurse"]))
        git.gitcmd(
            f"update-ref refs/remotes/origin/{bottom} {bottom}",
            "move remote tracking ref", execution_path=self.repo)

        result = self.menu.applyMenuChoice(
            "stack", ["sync", "--from=model", "--rebase", "--noFetch"])

        self.assertFalse(result)
        self.assertIn("moved", self.get_output())

    def testStackReviewPlansBottomToTopWithStructuredMetadata(self):
        """Review orchestration uses immediate targets and stable metadata."""
        bottom, top = self._createCommittedTwoLevelStack()
        manifest = stack.StackStore(self.repo).find("widgets")
        reviewer = stack_review.StackReviewer(self.repo, manifest)

        with mock.patch(
                "vine.stack_review.grapeMenu.menu") as menu_factory:
            apply_choice = menu_factory.return_value.applyMenuChoice
            apply_choice.return_value = True
            self.assertTrue(reviewer.run(no_local=True, no_recurse=True))

        calls = apply_choice.call_args_list
        self.assertEqual(2, len(calls))
        self.assertIn(f"--source={bottom}", calls[0].args[1])
        self.assertIn("--target=master", calls[0].args[1])
        self.assertIn(f"--source={top}", calls[1].args[1])
        self.assertIn(f"--target={bottom}", calls[1].args[1])
        self.assertIn("--draft", calls[1].args[1])

    def testMergeDownDefaultsToStackIntegrationTarget(self):
        """``grape md`` uses the immediate parent unless --public is explicit."""
        bottom, top = self._createCommittedTwoLevelStack()

        self.assertEqual(top, git.currentBranch(execution_path=self.repo))
        self.assertEqual(
            bottom,
            mergeDown.MergeDown.lookupPublicBranch(execution_path=self.repo))

    def testAdoptRecordsExistingLinearBranchesWithoutRewriting(self):
        """Adoption validates a branch chain and preserves every tip."""
        bottom = "feature/alice/widgets/model"
        top = "feature/alice/widgets/api"
        git.checkout(f"-b {bottom} master", execution_path=self.repo)
        with open(os.path.join(self.repo, "model.txt"), "w") as stream:
            stream.write("model\n")
        git.add("model.txt", execution_path=self.repo)
        git.commit('-m "model"', execution_path=self.repo)
        bottom_tip = git.SHA(execution_path=self.repo)
        git.checkout(f"-b {top}", execution_path=self.repo)
        with open(os.path.join(self.repo, "api.txt"), "w") as stream:
            stream.write("api\n")
        git.add("api.txt", execution_path=self.repo)
        git.commit('-m "api"', execution_path=self.repo)
        top_tip = git.SHA(execution_path=self.repo)

        result = self.menu.applyMenuChoice(
            "stack", ["adopt", "widgets", bottom, top,
                      "--target=master", "--user=alice", "--noRecurse"])

        self.assertTrue(result)
        manifest = stack.StackStore(self.repo).find("widgets")
        self.assertEqual([bottom, top], [level.branch for level in manifest.levels])
        self.assertEqual(bottom_tip, git.SHA(bottom, execution_path=self.repo))
        self.assertEqual(top_tip, git.SHA(top, execution_path=self.repo))
        self.assertEqual(bottom, stack.IntegrationTargetResolver(
            manifest).target(top))

    def testAdoptRejectsBranchesThatAreNotLinear(self):
        """Adoption does not silently record a divergent branch chain."""
        bottom = "feature/alice/widgets/model"
        top = "feature/alice/widgets/api"
        git.checkout(f"-b {bottom} master", execution_path=self.repo)
        with open(os.path.join(self.repo, "only-bottom.txt"), "w") as stream:
            stream.write("bottom only\n")
        git.add("only-bottom.txt", execution_path=self.repo)
        git.commit('-m "bottom only"', execution_path=self.repo)
        git.branch(f"{top} develop", execution_path=self.repo)

        result = self.menu.applyMenuChoice(
            "stack", ["adopt", "widgets", bottom, top,
                      "--target=master", "--user=alice", "--noRecurse"])

        self.assertFalse(result)
        self.assertEqual([], stack.StackStore(self.repo).list())
