import sys
import testGrape
import os

if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeMenu


class TestReview(testGrape.TestGrape):
    def testReview(self):
        os.chdir(self.repo)
        args = ["review", "--test", "-v", "--user=user", "--proj=proj1", "--repo=repo1"]
        try:
            ret = grapeMenu.menu().applyMenuChoice("review", args)
        except SystemExit:
            self.fail("grape-review failed with output %s" % self.output.getvalue())
        contents = self.output.getvalue()
        self.assertTrue(ret)
        self.assertIn("'id': '1'", contents)
