#!/usr/bin/env python

import sys, unittest, StringIO

if not ".." in sys.path:
    sys.path.append( ".." )
from grape import Grape

class TestGrape(unittest.TestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.stdout = sys.stdout
        sys.stdout = self.output

    def tearDown(self):
        sys.stdout = self.stdout
        self.output.close()

def buildSuite(cls,appendTo = None):
    suite = appendTo
    if suite == None:
        suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(cls))
    return suite

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


class TestBranch(TestGrape):
    def testBranch(self):
        grape = Grape()
        ret = grape.options["b"].execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )

        
def main():
    import testUtility
    testClasses = [TestHelp,TestBranch,testUtility.TestUtility]
    suite = unittest.TestSuite()
    for cls in testClasses:
        suite = buildSuite(cls,suite)


    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main()
