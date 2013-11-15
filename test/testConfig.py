import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        grape = Grape()
        ret = grape.options["config"].execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
