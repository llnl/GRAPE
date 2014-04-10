import sys
import testGrape

if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeMenu


class TestReview(testGrape.TestGrape):
    def testReview(self):
        args = ["review", "--test", "-v", "--user=user", "--proj=proj1", "--repo=repo1"]
        ret = grapeMenu.menu().applyMenuChoice("review", args)
        contents = self.output.getvalue()
        self.assertTrue(ret)
        self.assertIn("'id': '1'", contents)
