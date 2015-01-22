import os, sys, StringIO, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, utility, grapeGit as git, grapeConfig

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        os.chdir(self.repo)

        self.queueUserInput(["\n", "\n", "\n", "\n"])
        ret = grapeMenu.menu().applyMenuChoice("config")
        contents = self.output.getvalue()
        self.assertTrue(contents)
