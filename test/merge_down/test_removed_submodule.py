import os

import pytest

from test import testGrape
from test.merge_down.base import MergeDownTestBase
from vine import grapeGit as git


pytestmark = pytest.mark.slow


class TestMergeDownRemovedSubmodule(MergeDownTestBase):
    """Regression coverage for merge-down after a submodule is removed."""

    def test_removed_submodule_on_public_branch_during_merge_down(self):
        """A stale submodule must not be merged after the public branch removes it."""
        self.createTestSubmodule(execution_path=self.defaultWorkingDirectory)
        submodule_added_sha = git.SHA(execution_path=self.repo)
        git.push("origin master", execution_path=self.repo)

        git.checkout("-b feature/removed-submodule", execution_path=self.repo)
        submodule_path = os.path.join(self.repo, "submodule1")
        testGrape.writeFile2(os.path.join(submodule_path, "f2"))
        git.add("f2", execution_path=submodule_path)
        git.commit(
            "-m \"updated submodule on feature branch\"",
            execution_path=submodule_path,
        )
        git.checkout("-b feature/removed-submodule", execution_path=submodule_path)
        git.push("origin master", execution_path=submodule_path)
        git.add("submodule1", execution_path=self.repo)
        git.commit("-m \"updated submodule gitlink on feature branch\"", execution_path=self.repo)

        # Create the public-branch removal after the feature branch's change.
        # The local master branch is reset below to leave it stale until grape
        # md updates it from origin.
        git.branch("-f master HEAD", execution_path=self.repo)
        git.checkout("master", execution_path=self.repo)

        git.rm("-f submodule1", execution_path=self.repo)
        git.commit("-m \"removed submodule1\"", execution_path=self.repo)
        git.push("origin master", execution_path=self.repo)

        git.checkout("feature/removed-submodule", execution_path=self.repo)
        git.submodule("update --init", execution_path=self.repo)
        git.checkout("feature/removed-submodule", execution_path=submodule_path)
        git.branch(f"-f master {submodule_added_sha}", execution_path=self.repo)
        self.setUpConfig()

        self.assertEqual(git.SHA("master", execution_path=self.repo), submodule_added_sha)
        self.assertNotEqual(
            git.SHA("origin/master", execution_path=self.repo),
            submodule_added_sha,
        )
        self.assertIn("submodule1", git.getAllSubmodules(execution_path=self.repo))
        self.assertIn(
            "submodule1",
            git.getModifiedSubmodules(
                self.repo,
                "master",
                "feature/removed-submodule",
            ),
        )

        # The public branch still appears to contain the submodule locally at
        # the start of md, while origin/master has removed it. This leaves md
        # with a stale submodule merge candidate after grape up updates master.
        ret = self.menu.applyMenuChoice("md", ["--am", "--recurse"])
        self.assertTrue(ret, "grape md did not complete successfully")
