import os, sys, StringIO, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeGit as git
from vine import grapeMenu
from vine import grapeConfig

class TestMD(testGrape.TestGrape):

    # sets up a new change on the master branch one commit ahead of
    # testMerge and checks out testMerge.
    def setUpMerge(self):
        os.chdir(self.repo)
        # create a new branch
        git.branch("testMerge")
        # add f2 to master
        testGrape.writeFile2("f2")
        git.add("f2")
        git.commit("-m \"f2\"")
        git.checkout("testMerge")
        config = grapeConfig.grapeConfig()
        config.set("flow", "publicBranches", "master")
        config.set("flow", "topicPrefixMappings", "?:master")

    def setUpConflictingMerge(self):
        self.setUpMerge()
        # add a conflicting commit
        testGrape.writeFile3("f2")
        git.add("f2")
        git.commit("-m \"f2\"")

    def testNonConflictingMerge(self):
        self.setUpMerge()
        # now run grape md, should be a fast forward merge
        try:
            self.assertNotEqual(git.shortSHA(), git.shortSHA("master"))
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return True")
            contents = self.output.getvalue()
            self.assertEqual(git.shortSHA(), git.shortSHA("master"), "merging master into test branch did not fast"
                                                                    "forward")
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())
        except git.GrapeGitError as e:
            self.fail("Unhandled GrapeGitError: %s\n%s" % (e.gitCommand, e.gitOutput))

    def testConflictingMerge(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(git.shortSHA(), git.shortSHA("master"))
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return false as expected for a conflict")
            # resolve the conflict
            git.checkout("--ours f2")
            git.add("f2")
            self.assertFalse(git.isWorkingDirectoryClean(), "working directory clean before attempted continution of "
                                                            "merge\n %s" %self.output.getvalue())
            git.status("--porcelain")
            ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, "grape md --continue did not return True\n%s" % self.output.getvalue())
            self.assertTrue(git.isWorkingDirectoryClean(), "grape md --continue did not finish merge\n%s" % self.output.getvalue())
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())

