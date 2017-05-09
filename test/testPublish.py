import os
import sys

import testGrape

if not ".." in sys.path:
    sys.path.insert(0, "..")
from vine import grapeMenu
from vine import grapeGit as git
from vine import grapeConfig


class TestPublish(testGrape.TestGrape):

    def setUpBranchToFFMerge(self):
        os.chdir(self.repo)
        self.branch = "testPublish"
        git.checkout("-b %s" % self.branch)
        testGrape.writeFile2("f2")
        git.add("f2")
        git.commit("-m \"added f2\"")
        self.setUpConfig()
        

    def setUpDevelopBranch(self):
        os.chdir(self.repo)
        git.branch("-f develop master")

    def assertSuccessfulFastForwardMerge(self, fromBranch="testPublish", toBranch="master"):
        try:
            self.assertTrue(git.currentBranch() == toBranch, "FF merge did not put us on public branch")
            self.assertTrue(git.shortSHA(toBranch) == git.shortSHA(fromBranch))
        except git.GrapeGitError as e:
            self.fail("%s\n%s" % (self.output.getvalue(), e.gitCommand+e.gitOutput))

    def assertSuccessfulSquashMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertTrue(git.currentBranch() == toBranch)
        self.assertTrue(git.shortSHA(toBranch) != git.shortSHA(fromBranch))
        self.assertFalse(git.diff("--name-only %s %s" % (toBranch, fromBranch)))

    def assertSuccessfulSquashCascadeMerge(self, fromBranch="testPublish", toBranch="master", cascadeDest="develop"):
        currentBranch = git.currentBranch()
        self.assertTrue(currentBranch == cascadeDest)
        self.assertFalse(git.diff("--name-only %s %s" % (toBranch, fromBranch)))
        self.assertFalse(git.diff("--name-only %s %s" % (toBranch, cascadeDest)))
        self.assertTrue(git.branchUpToDateWith(toBranch, cascadeDest))
        self.assertFalse(git.branchUpToDateWith(toBranch, fromBranch))

    def assertGrapePublishWorked(self, args=None, assertFail=False):
        self.queueUserInput(["1.1.1"])
        config = grapeConfig.grapeConfig()
        config.ensureSection("project")
        config.set("project", "name", "proj1")

        defaultArgs = ["-m", "publishing testPublish to master", "--noverify", '-R', '--test', '-R', '--repo=repo1',
                       '-R', '--user=user', "--noReview", "--noUpdateLog", "--noPushSubtrees"]
        try:
            if args:
                args += defaultArgs
            else:
                args = defaultArgs
            ret = grapeMenu.menu().applyMenuChoice("publish", args=args)
          
            self.assertEquals(ret, not assertFail, msg="publish returned " +str(ret))
        except SystemExit as e:
            self.fail("%s\n%s" % (self.output.getvalue(), e.message))
        #origin has not been set up for these repos yet
        #self.assertNotIn("fatal:", self.output.getvalue())
    
    def assertGrapePublishFailed(self, args=None):
        self.assertGrapePublishWorked( args=args, assertFail=True)

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
        self.setUpDevelopBranch()
        self.assertGrapePublishWorked(["--squash", "--cascade=develop"])
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
        self.assertGrapePublishFailed(["--topic=testPublish"])

    def testCustomBuildStep(self):
        self.setUpBranchToFFMerge()
        config = grapeConfig.grapeConfig()
        config.set("publish", "buildCmds", "echo hello ,  echo world")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo hello", self.output.getvalue())
        self.assertIn("echo world", self.output.getvalue())
        self.assertIn("PERFORMING CUSTOM BUILD STEP", self.output.getvalue())

    def testCustomTestStep(self):
        self.setUpBranchToFFMerge()
        config = grapeConfig.grapeConfig()
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo helloTest", self.output.getvalue())
        self.assertIn("echo worldTest", self.output.getvalue())
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.output.getvalue())

    def testVersionTickArgumentPassing(self):
        self.setUpBranchToFFMerge()
        grapeMenu.menu().applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertIn("v1.0.1", git.describe())

    def testStartStepStopStep(self):
        self.setUpBranchToFFMerge()
        config = grapeConfig.grapeConfig()
        config.set("publish", "buildCmds", "echo hello , echo world")
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")
        grapeMenu.menu().applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--startAt=tickVersion", "--stopAt=updateLog", "--tickVersion=True",
                                       "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertGrapePublishWorked(["--startAt=test", "--stopAt=deleteTopic", "--tickVersion=True",
                                       "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        # check test occurred
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.output.getvalue())
        # check that build never occurred
        self.assertNotIn("PERFORMING CUSTOM BUILD STEP", self.output.getvalue())
        # check that we tagged a new version
        self.assertIn("v1.0.1", git.describe())
        
    def testPublishNestedSubprojects(self):
        import testNestedSubproject
        self.setUpBranchToFFMerge()
        config = grapeConfig.grapeConfig()
        config.set("publish", "buildCmds", "echo hello , echo world")
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")        
        grapeMenu.menu().applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])        
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self)
        os.chdir(self.subproject)
        self.assertTrue(git.currentBranch() == self.branch)

        os.chdir(self.repo)
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()
        
        os.chdir(self.subproject)
        self.assertTrue(git.currentBranch() == "master", "on %s, expected to be on master" % git.currentBranch())
        
    def testPublishFromWithinNestedSubproject(self):
        import testNestedSubproject
        self.setUpBranchToFFMerge()
        grapeMenu.menu().applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])        
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self)
 
        os.chdir(self.subproject)
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
