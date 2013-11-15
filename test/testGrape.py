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


def main():
    import testUtility, testBranch,testHelp,testGrapeGit
    testClasses = [testHelp.TestHelp,testBranch.TestBranch,testUtility.TestUtility,
                   testGrapeGit.TestGrapeGit]
    suite = unittest.TestSuite()
    for cls in testClasses:
        suite = buildSuite(cls,suite)


    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main()
