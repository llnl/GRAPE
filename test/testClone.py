import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, utility

class TestClone(testGrape.TestGrape):
    def testClone(self):
        #ret =grapeMenu.menu().getOption("clone").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
