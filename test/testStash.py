import os
import testGrape


class TestStash(testGrape.TestGrape):

    def test_stash_given_empty_repo(self):
        """Stash command smoke test. Exits gracefully given empty repo."""
        os.chdir(self.repo)
        result = self.menu.applyMenuChoice("stash")
        self.assertTrue(result, "Failed 'stash' command smoke test.")

        contents = self.output.getvalue()
        start_index = self.repo.find('/tmp')
        expected_output = '{repo}: No local changes to save'\
                          .format(repo=self.repo[start_index:])
        self.assertIn(expected_output, contents)

if __name__ == "__main__":
    import unittest
    unittest.main() 

