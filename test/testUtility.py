import os, sys, unittest
if not ".." in sys.path:
    sys.path.append( ".." )
import utility

class TestUtility(unittest.TestCase):
    def testGitDir(self):
        grapeBaseDir = os.getcwd()
        if not os.path.exists(os.path.join(grapeBaseDir, "grape")):
            grapeBaseDir = os.path.abspath(os.path.join(os.getcwd(), ".."))
        self.assertTrue(os.path.exists(os.path.join(grapeBaseDir, "grape")), "Something went horribly wrong and could not find the base directory of the grape repo")

        self.assertEquals(utility.gitDir(), grapeBaseDir, "Could not determine git directory")

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestUtility))
    return suite