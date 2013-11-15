import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from grape import Grape

class TestBranch(testGrape.TestGrape):
    def testBranch(self):
        grape = Grape()
        ret = grape.getOption("b").execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )
