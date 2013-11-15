import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestDev(testGrape.TestGrape):
    def testDev(self):
        grape = Grape()
        #ret = grape.getOption("dev").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
