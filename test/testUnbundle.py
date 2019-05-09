import os
from grape.test import testGrape


class TestUnbundle(testGrape.TestGrape):

    def test_unbundle_given_defaults(self):
        """Test 'unbundle' command (smoke test)."""
        os.chdir(self.repo)
        result = self.menu.applyMenuChoice("unbundle")
        self.assertTrue(result, "Failed 'unbundle' command smoke test.")


if __name__ == "__main__":
    import unittest
    unittest.main()
