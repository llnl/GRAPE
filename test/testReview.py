import os
import sys
from test import testGrape


class TestReview(testGrape.TestGrape):

    def testReview(self):
        args = ["review", "--test", "--user=user", "--proj=proj1", "--repo=repo1"]
        try:
            ret = self.menu.applyMenuChoice("review", args, globalArgs=["-v"])
        except SystemExit:
            self.fail(f"grape-review failed with output {self.get_output()}")
        self.assertTrue(ret)
