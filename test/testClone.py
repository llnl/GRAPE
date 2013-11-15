import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestClone(testGrape.TestGrape):
    def testClone(self):
        grape = Grape()
        ret = grape.options["clone"].execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
