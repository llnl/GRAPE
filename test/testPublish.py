import os, sys, StringIO, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu
from vine import grapeGit as git
from vine import grapeConfig

class TestPublish(testGrape.TestGrape):

    def setUpBranchToFFMerge(self):
        os.chdir(self.repo)
        git.checkout("-b testPublish")
        testGrape.writeFile2("f2")
        git.add("f2")
        git.commit("-m \"added f2\"")
        self.setUpConfig()

    def assertSuccessfulFastForwardMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertTrue(git.currentBranch() == toBranch, "FF merge did not put us on public branch")
        self.assertTrue(git.shortSHA(toBranch) == git.shortSHA(fromBranch))

    def assertSuccessfulSquashMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertTrue(git.currentBranch() == toBranch)
        self.assertTrue(git.shortSHA(toBranch) != git.shortSHA(fromBranch))
        self.assertFalse(git.diff("--name-only %s %s" % (toBranch, fromBranch)))

    def assertSuccessfulSquashCascadeMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertTrue(git.currentBranch() == fromBranch)
        self.assertTrue(git.shortSHA(toBranch) != git.shortSHA(fromBranch))
        self.assertFalse(git.diff("--name-only %s %s" % (toBranch, fromBranch)))
        self.assertTrue(git.branchUpToDateWith(fromBranch, toBranch))
        self.assertFalse(git.branchUpToDateWith(toBranch, fromBranch))

    def assertGrapePublishWorked(self, args=[]):
        try:
            args += ["-m", "publishing testPublish to master", "--noverify"]
            ret = grapeMenu.menu().applyMenuChoice("publish", args=args)
            self.assertTrue(ret, "published returned false")
        except SystemExit:
            self.fail(self.output.getvalue())

    def testFFDefaultPublish(self):
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()

    def testFFMergePublish(self):
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()

    def testFFSquashPublish(self):
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--squash"])
        self.assertSuccessfulSquashMerge()

    def testFFCascadePublish(self):
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--squash", "--cascade"])
        self.assertSuccessfulSquashCascadeMerge()

    def testFFRebasePublish(self):
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--rebase"])
        self.assertSuccessfulFastForwardMerge()


