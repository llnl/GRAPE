import os
import sys
import testGrape


class TestReview(testGrape.TestGrape):
    def testReview(self):
        os.chdir(self.repo)
        args = ["review", "--test", "--user=user", "--proj=proj1", "--repo=repo1"]
        try:
            ret = self.menu.applyMenuChoice("review", args, globalArgs=["-v"])
        except SystemExit:
            self.fail("grape-review failed with output %s" % self.get_output())
        contents = self.get_output()
        self.assertTrue(ret)
