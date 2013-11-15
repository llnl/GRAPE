import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
import utility

class TestHelp(TestGrape):
    def testHelp(self):
        grape = Grape()
        ret = grape.options["help"].execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
        self.assertTrue( "rel)" in contents)
        self.assertTrue( "hot)" in contents)
        self.assertTrue( "minor)" in contents)
        self.assertTrue( "rev)" in contents)
