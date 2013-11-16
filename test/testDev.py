import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility

class TestDev(testGrape.TestGrape):
    def testDev(self):
        #ret = grapeMenu.menu().getOption("dev").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
