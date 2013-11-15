import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility

class TestUtility(testGrape.TestGrape):
    def testNothing(self):
        self.assertTrue(False)