import os
import sys
from grape.test import testGrape
from grape.vine import config_parser_global
from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine.option import Option


class TestPublish(testGrape.TestGrape):

    def setUpBranchToFFMerge(self):
        os.chdir(self.repo)
        self.branch = "testPublish"
        git.checkout(f"-b {self.branch}")
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
        except grape_errors.GrapeGitError as e:
            self.fail(f"{self.get_output()}\n{e.gitCommand + e.gitOutput}")

    def assertSuccessfulSquashMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertTrue(git.currentBranch() == toBranch)
        self.assertTrue(git.shortSHA(toBranch) != git.shortSHA(fromBranch))
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}"))

    def assertSuccessfulSquashCascadeMerge(self, fromBranch="testPublish", toBranch="master", cascadeDest="develop"):
        currentBranch = git.currentBranch()
        self.assertTrue(currentBranch == cascadeDest)
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}"))
        self.assertFalse(git.diff(f"--name-only {toBranch} {cascadeDest}"))
        self.assertTrue(git.branchUpToDateWith(toBranch, cascadeDest))
        self.assertFalse(git.branchUpToDateWith(toBranch, fromBranch))

    def assertGrapePublishWorked(self, args=None, assertFail=False):
        config = config_parser_global.grapeConfig()
        config.ensureSection("project")
        config.set(Option.SECTION_PROJECT, "name", "proj1")

        defaultArgs = ["-m", "publishing testPublish to master", "--noverify", '-R', '--test', '-R', '--repo=repo1',
                       '-R', '--user=user', "--noReview", "--noUpdateLog", "--noPushSubtrees"]
        try:
            if args:
                args += defaultArgs
            else:
                args = defaultArgs
            with self.queue_user_input(["1.1.1"]):
                ret = self.menu.applyMenuChoice("publish", args=args)

            self.assertEquals(ret, not assertFail, msg="publish returned " +str(ret))
        except SystemExit as e:
            self.fail(f"{self.get_output()}\n{e.message}")
        #origin has not been set up for these repos yet
        #self.assertNotIn("fatal:", self.output.getvalue())

    def assertGrapePublishFailed(self, args=None):
        self.assertGrapePublishWorked(args=args, assertFail=True)

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
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello ,  echo world")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("hello", self.get_output())
        self.assertIn("world", self.get_output())
        self.assertIn("PERFORMING CUSTOM BUILD STEP", self.get_output())

    def testCustomTestStep(self):
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("helloTest", self.get_output())
        self.assertIn("worldTest", self.get_output())
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.get_output())

    def testVersionTickArgumentPassing(self):
        self.setUpBranchToFFMerge()
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertIn("v1.0.1", git.describe())

    def testStartStepStopStep(self):
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--startAt=tickVersion", "--stopAt=updateLog", "--tickVersion=True",
                                       "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertGrapePublishWorked(["--startAt=test", "--stopAt=deleteTopic", "--tickVersion=True",
                                       "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        # check test occurred
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.get_output())
        # check that build never occurred
        self.assertNotIn("PERFORMING CUSTOM BUILD STEP", self.get_output())
        # check that we tagged a new version
        self.assertIn("v1.0.1", git.describe())

    def testPublishNestedSubprojects(self):
        from grape.test import testNestedSubproject
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self)
        os.chdir(self.subproject)
        self.assertTrue(git.currentBranch() == self.branch)

        os.chdir(self.repo)
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()

        os.chdir(self.subproject)
        self.assertTrue(git.currentBranch() == "master",
                        f"on {git.currentBranch()}, expected to be on master")

    def testPublishFromWithinNestedSubproject(self):
        from grape.test import testNestedSubproject
        self.setUpBranchToFFMerge()
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self)

        os.chdir(self.subproject)
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()

    def testPublishNewSubmodule(self):
        from grape.test import testNestedSubproject
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")

        # create backend for repo2
        repo2_origin = self.repo + "2-origin"
        os.mkdir(repo2_origin)
        with git.cd(repo2_origin):
            git.gitcmd("init --bare", "Setup Failed")
        # clone repo2
        git.gitcmd(f"clone {repo2_origin} {self.repos[1]}",
                   "could not clone test bare repo")
        os.chdir(self.repos[1])
        # create an initial public branch in repo2
        fname = os.path.join(self.repos[1], "testRepoFile")
        testGrape.writeFile1(fname)
        self.file1 = fname
        git.gitcmd(f"add {fname}", "Add Failed")
        git.gitcmd("commit -m \"initial commit\"", "Commit Failed")
        git.gitcmd("push origin master", "push to master failed")
        git.branch("testPublish")
        git.push("origin testPublish")
        # add repo2 as a submodule to repo1
        os.chdir(self.repo)
        git.submodule(f"add {repo2_origin} submodule1")
        git.commit("-m \"added submodule1\"")
        os.chdir(os.path.join(self.repo, "submodule1"))
        # add changes to feature branch
        git.checkout("testPublish")
        f3 = os.path.join(self.repo, "submodule1", "f3")
        testGrape.writeFile3(f3)
        git.add(f3)
        git.commit("-m \"added f3\"")
        # save the log from the feature branch
        branchlog = git.log()
        os.chdir(self.repo)
        git.add(os.path.join(self.repo, "submodule1"))
        git.commit("-m \"updated gitlink\"")

        self.assertTrue(git.currentBranch() == self.branch)
        # merge feature branch into public branch
        self.assertGrapePublishWorked(["--merge","--recurse","--submodulePublic=master"])
        self.assertSuccessfulFastForwardMerge()

        # check out a clean version of repo2
        checkrepo = "repocheck"
        git.gitcmd(f"clone {repo2_origin} {checkrepo}",
                   "could not clone test bare repo")
        os.chdir(checkrepo)
        git.checkout("master")
        # ensure that master has been updated with the new commits
        mergelog = git.log()
        self.assertTrue(branchlog == mergelog)
