import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from grape import Grape

class TestReview(testGrape.TestGrape):
    def testReview(self):
        grape = Grape()
        #ret = grape.getOption("review").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
