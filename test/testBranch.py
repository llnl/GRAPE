import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu

class TestBranch(testGrape.TestGrape):
    def testBranch(self):
        ret = grapeMenu.menu().get_option("b").execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )
