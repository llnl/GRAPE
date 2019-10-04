import os
from test import testGrape


class TestResolveConflicts(testGrape.TestGrape):

    def test_resolve_conflicts_given_empty_repo(self):
        """Resolve command smoke test. Exits gracefully given empty repo."""
        result = self.menu.applyMenuChoice("resolve")
        self.assertTrue(result, "Failed 'resolve' command smoke test.")


if __name__ == "__main__":
    import unittest
    unittest.main()
