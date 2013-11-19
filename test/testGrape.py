#!/usr/bin/env python

import sys, unittest, StringIO

class TestGrape(unittest.TestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        sys.stdout = self.output

    def tearDown(self):
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        self.output.close()

def buildSuite(cls,appendTo = None):
    suite = appendTo
    if suite == None:
        suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(cls))
    return suite


def main():
    import testBranch, testClone, testConfig, testDev, testHelp
    import testGrapeGit, testReview, testUtility
    testClasses = [testBranch.TestBranch, testClone.TestClone,
                   testConfig.TestConfig, testDev.TestDev,
                   testHelp.TestHelp, testGrapeGit.TestGrapeGit,
                   testReview.TestReview,
                   testUtility.TestUtility]
    suite = unittest.TestSuite()
    for cls in testClasses:
        suite = buildSuite(cls,suite)


    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main()
