import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        #ret = grapeMenu.menu().getOption("config").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
