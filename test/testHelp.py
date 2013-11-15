import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from grape import Grape

class TestHelp(testGrape.TestGrape):
    def testHelp(self):
        grape = Grape()
        ret = grape.getOption("help").execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
        self.assertTrue( "rel:" in contents)
        self.assertTrue( "hot:" in contents)
        self.assertTrue( "minor:" in contents)
        self.assertTrue( "rev:" in contents)
