import os
import sys

import testGrape

if not ".." in sys.path:
    sys.path.append("..")
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

    def assertGrapePublishWorked(self, args=None):
        defaultArgs = ["-m", "publishing testPublish to master", "--noverify"]
        try:
            if args:
                args += defaultArgs
            else:
                args = defaultArgs
            ret = grapeMenu.menu().applyMenuChoice("publish", args=args)
            self.assertTrue(ret, "published returned false")
        except SystemExit as e:
            self.fail("%s\n%s" % (self.output.getvalue(), e.message))

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

    def testTopicConfigOption(self):
        self.setUpBranchToFFMerge()
        git.checkout("-b someOtherBranch")
        testGrape.writeFile1("someOtherfile")
        git.add("someOtherfile")
        git.commit("-a -m \"someOtherfile\"")
        self.assertGrapePublishWorked(["--topic=testPublish"])
        self.assertSuccessfulFastForwardMerge()

    def testCustomBuildStep(self):
        self.setUpBranchToFFMerge()
        config = grapeConfig.grapeConfig()
        config.set("publish", "buildStr", "echo hello ; echo world")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo hello", self.output.getvalue())
        self.assertIn("echo world", self.output.getvalue())