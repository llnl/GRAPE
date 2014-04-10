import os
import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu

class TestBranches(testGrape.TestGrape):
    def testBranches(self):
        menuOption = grapeMenu.menu().applyMenuChoice("b", {})
        self.assertTrue(ret, "vine.branches.execute() returned failure.")

        contents = self.output.getvalue()
        workingDirectory = os.path.abspath(".")
        self.assertNotEquals(-1, contents.find("Working Directory: " + workingDirectory), "vine.branches.execute() did not find the correct working directory")
        self.assertNotEquals(-1, contents.find("* develop"), "vine.branches.execute() could not find the develop branch")
