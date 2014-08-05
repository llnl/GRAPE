import os
import sys
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu
from vine import grapeGit as git
from vine import grapeConfig


class TestVersion(testGrape.TestGrape):
    def testMinorTick(self):
        os.chdir(self.repo)
        # test initialization of grape managed versioning
        menu = grapeMenu.menu()
        try:
#            self.assertEqual(grapeConfig.grapeConfig().get("versioning", "updateTag").lower(), "true")
            ret = menu.applyMenuChoice("version", ["init","v0.1.0", "--file=.grapeversion"])
            self.assertTrue(ret, "grape version init v0.1.0 returned False\n%s" %
                            self.output.getvalue())
            self.assertEqual(git.describe("--abbrev=0"), "v0.1.0")

            # test to make sure ticking the version works
            ret = menu.applyMenuChoice("version", ["tick", "--minor"])
            self.assertTrue(ret, "grape version tick returned False")
            self.assertEqual(git.describe(), "v0.2.0")
        except SystemExit:
            self.fail("Unexpected SystemExit\n%s" % self.output.getvalue())
        except git.GrapeGitError as e:
            self.fail("Uncaught GrapeGit error: %s" % e.gitOutput)

    def testMajorTick(self):
        os.chdir(self.repo)
        menu = grapeMenu.menu()
        try:

            ret = menu.applyMenuChoice("version", ["init","v0.1.0", "--file=.grapeversion"])
            self.assertTrue(ret, "grape version init v0.1.0 returned False\n%s" %
                            self.output.getvalue())
            self.assertEqual(git.describe("--abbrev=0"), "v0.1.0")

            # test to make sure ticking the version works
            ret = menu.applyMenuChoice("version", ["tick", "--major"])
            self.assertTrue(ret, "grape version tick returned False")
            self.assertEqual(git.describe(), "v1.0.0")

            # test a minor tick with no tag update
            ret = menu.applyMenuChoice("version", ["tick", "--minor", "--notag"])
            self.assertEqual(git.describe("--abbrev=0"), "v1.0.0")

            ret = menu.applyMenuChoice("version", ["tick", "--minor"])
            self.assertEqual(git.describe(), "v1.2.0")

            ret = menu.applyMenuChoice("version", ["tick", "--major"])
            self.assertEqual(git.describe(), "v2.0.0")

            #test overiding default tag behavior
            config = grapeConfig.grapeConfig()
            config.set("versioning", "updateTag", "False")
            ret = menu.applyMenuChoice("version", ["tick", "--slot=3"])
            self.assertEqual(git.describe("--abbrev=0"), "v2.0.0")
            ret = menu.applyMenuChoice("version", ["tick", "--slot=3", "--tag"])
            self.assertEqual(git.describe(), "v2.0.2")

            # test auto extension of version number
            menu.applyMenuChoice("version", ["tick", "--slot=4", "--tag"])
            self.assertEqual(git.describe(), "v2.0.2.1")


        except SystemExit:
            self.fail("Unexpected SystemExit\n%s" % self.output.getvalue())
        except git.GrapeGitError as e:
            self.fail("Uncaught GrapeGitError: %s" % e.gitOutput)