import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, utility

class TestReview(testGrape.TestGrape):
    def testReview(self):
        #ret = grapeMenu.menu().getOption("review").execute()
        ret = False
        contents = self.output.getvalue()
        self.assertTrue( ret )
