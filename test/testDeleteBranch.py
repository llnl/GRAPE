import os
from test import testGrape
from vine import grapeGit as git


class TestDeleteBranch(testGrape.TestGrape):

    def test_delete_branch_given_test_branch(self):
        """Delete branch command tested given a test branch."""
        test_branch = "test_branch"
        git.branch(test_branch, execution_path=self.repo)

        result = self.menu.applyMenuChoice("db", [test_branch])
        self.assertTrue(result, "Failed 'delete branch' command smoke test.")

        # Asserts local test branch was deleted.
        contents = self.get_output()
        expected_output = f'deleting {test_branch} in'
        self.assertIn(expected_output, contents)

        # Assert remote branch not found.
        expected_output = f'remote branch origin/{test_branch} not found in'
        self.assertIn(expected_output, contents)


    def test_delete_local_branch_given_test_branch(self):
        """Delete local only branch command tested given a test branch."""
        test_branch = "test_branch_local"
        git.branch(test_branch, execution_path=self.repo)

        result = self.menu.applyMenuChoice("db", [test_branch, "--local-only"])
        self.assertTrue(result, "Failed 'delete branch' command smoke test.")

        # Asserts test branch was deleted.
        contents = self.get_output()
        expected_output = f'deleting {test_branch} in'
        self.assertIn(expected_output, contents)

        # Asserts did not try to delete remote test branch.
        expected_output = f'deleting origin/{test_branch} in'
        self.assertNotIn(expected_output, contents)


    def test_delete_remote_branch_given_test_branch(self):
        """Delete remote only branch command tested given a test branch."""
        test_branch = "test_branch_remote"
        # Remote branch will not be created

        result = self.menu.applyMenuChoice("db", [test_branch, "--remote-only"])
        self.assertTrue(result, "Failed 'delete branch' command smoke test.")

        # Asserts attempted to delete remote test branch.
        contents = self.get_output()
        expected_output = f'deleting origin/{test_branch} in'
        self.assertIn(expected_output, contents)

        # Asserts did not try to delete local test branch.
        expected_output = f'deleting {test_branch} in'
        self.assertNotIn(expected_output, contents)


if __name__ == "__main__":
    import unittest
    unittest.main()
