import os
from test import testGrape
from vine import grapeGit as git


class TestDeleteBranch(testGrape.TestGrape):

    def test_delete_branch_given_test_branch(self):
        """Delete branch command tested given a test branch."""
#        os.chdir(self.repo)
        test_branch = "test_branch"
        git.branch(test_branch, execution_path=self.repo)

        result = self.menu.applyMenuChoice("db", [test_branch])
        self.assertTrue(result, "Failed 'delete branch' command smoke test.")

        # Asserts test branch was deleted.
        contents = self.get_output()
        expected_output = f'deleting {test_branch} in'
        self.assertIn(expected_output, contents)


if __name__ == "__main__":
    import unittest
    unittest.main()
