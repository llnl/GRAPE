import os
import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu

class TestBranches(testGrape.TestGrape):
    def testBranches(self):
        os.chdir(self.repo)
        ret = grapeMenu.menu().applyMenuChoice("b", [])
        self.assertTrue(ret, "vine.branches returned failure.")

        contents = self.output.getvalue()
        workingDirectory = os.path.abspath(".")
        self.assertNotEquals(-1, contents.find("Working Directory: " + workingDirectory), "vine.branches did not find the correct working directory")
        self.assertNotEquals(-1, contents.find("master"), "vine.branches could not find the master branch")
