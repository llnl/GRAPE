import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
import utility

class TestBranch(TestGrape):
    def testBranch(self):
        grape = Grape()
        ret = grape.options["b"].execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )
