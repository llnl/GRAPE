import os
import sys
import testGrape
if not ".." in sys.path:
    sys.path.insert(0, "..")
from vine import grapeMenu

class TestBranches(testGrape.TestGrape):
    def testBranches(self):
        os.chdir(self.repo)
        ret = grapeMenu.menu().applyMenuChoice("b", [])
        self.assertTrue(ret, "vine.branches returned failure.")

        contents = self.output.getvalue()
        self.assertNotEquals(-1, contents.find("master"), "vine.branches could not find the master branch")
