import os
import sys
import testGrape
if os.path.pardir not in sys.path:
    sys.path.insert(0, os.path.pardir)

class TestBranches(testGrape.TestGrape):
    def testBranches(self):
        os.chdir(self.repo)
        ret = self.menu.applyMenuChoice("b", [])
        self.assertTrue(ret, "vine.branches returned failure.")

        contents = self.get_output()
        self.assertNotEquals(-1, contents.find("master"), "vine.branches could not find the master branch")
