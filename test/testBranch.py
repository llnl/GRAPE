import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestBranch(testGrape.TestGrape):
    def testBranch(self):
        grape = Grape()
        ret = grape.options["b"].execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )
