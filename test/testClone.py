import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestClone(testGrape.TestGrape):
    def testClone(self):
        grape = Grape()
        #ret = grape.getOption("clone").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
