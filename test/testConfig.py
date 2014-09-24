import os, sys, StringIO, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, utility

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        os.chdir(self.repo)

        self.input.writelines(["\n", "\n", "\n", "\n"])
        self.input.seek(0)
        ret = grapeMenu.menu().applyMenuChoice("config")
        contents = self.output.getvalue()
        self.assertTrue(contents)
