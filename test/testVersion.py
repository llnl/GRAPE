import os
import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu
from vine import grapeGit as git


class TestVersion(testGrape.TestGrape):
    def testMinorTick(self):
        os.chdir(self.repo)
        # test initialization of grape managed versioning
        menu = grapeMenu.menu()
        ret = menu.applyMenuChoice("version", ["init","v0.1.0"])
        self.assertTrue(ret, "grape version init v0.1.0 returned False\n%s" %
                        self.output.getvalue())
        self.assertEqual(git.describe("--abbrev=0"), "v0.1.0")

        # test to make sure ticking the version works
        ret = menu.applyMenuChoice("version", ["tick"])
        self.assertTrue(ret, "grape version tick returned False")
        self.assertEqual(git.describe(), "v0.2")