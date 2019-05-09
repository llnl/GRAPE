import os
from grape.test import testGrape


class TestBranches(testGrape.TestGrape):
    def testBranches(self):
        os.chdir(self.repo)
        ret = self.menu.applyMenuChoice("b", [])
        self.assertTrue(ret, "vine.branches returned failure.")

        contents = self.get_output()
        self.assertNotEquals(-1, contents.find("master"), "vine.branches could not find the master branch")
