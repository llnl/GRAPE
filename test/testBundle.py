import os
from grape.test import testGrape


class TestBundle(testGrape.TestGrape):

    def test_bundle_given_defaults(self):
        """Test 'bundle' command (smoke test)."""
        os.chdir(self.repo)
        result = self.menu.applyMenuChoice("bundle")
        self.assertTrue(result, "Failed 'bundle' command smoke test.")


if __name__ == "__main__":
    import unittest
    unittest.main() 
