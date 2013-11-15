import os, sys, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
import utility

class TestGrapeGit(testGrape.TestGrape):
    def testDir(self): 
        self.assertTrue(False)

    def testMergeAbort(self): 
        self.assertTrue(False)

    def testMergeIntoCurrent(self):
        self.assertTrue(False)

    def testFetch(self): 
        self.assertTrue(False)

    def testPull(self):
        self.assertTrue(False)

    def testPush(self):
        self.asserTrue(False)

    def testBranch(self): 
        self.asserTrue(False)

    def testShowRemote(self):
        self.assertTrue(False)

    def testCommit(self):
        self.assertTrue(False)

    def testCheckout(self):
        self.assertTrue(False)


    def testRebase(self):
        self.asserTrue(False)


