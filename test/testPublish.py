import os
import shutil
import sys
from itertools import repeat
from unittest.mock import patch
from test import testGrape
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import version
from vine.option import Option


class TestPublish(testGrape.TestGrape):

    def setUpBranchToFFMerge(self):
        self.branch = "testPublish"
        git.checkout(f"-b {self.branch}", execution_path=self.repo)
        testGrape.writeFile2(os.path.join(self.repo, "f2"))
        git.add("f2", execution_path=self.repo)
        git.commit("-m \"added f2\"", execution_path=self.repo)
        self.setUpConfig()
        self._copy_version_file()

    def _copy_version_file(self):
        """Create copy of VERSION file for testing publish operation."""
        version_file = version.get_version_file_path()
        if not version_file:
            self.fail('Publish tests require VERSION file.')

        # Get file name of actual VERSION file
        config = config_parser_global.grapeConfig()
        orig_vers_path = config.get(Option.SECTION_VERSIONING, "file")

        # Make dir for new copy of VERSION file
        new_version_dir = os.path.dirname(orig_vers_path)
        os.makedirs(os.path.join(self.repo, new_version_dir), exist_ok=True)

        # Open/close creates an empty file to copy original into.
        version_copy = os.path.join(self.repo, orig_vers_path)
        open(version_copy, 'a').close()

        shutil.copyfile(version_file, version_copy)
        config.set(Option.SECTION_VERSIONING, "file", version_copy)
        git.add(version_copy, execution_path=self.repo)
        git.commit("-m \"VERSION added\"", execution_path=self.repo)

    def _get_test_version_path(self):
        # Get file name of actual VERSION file
        config = config_parser_global.grapeConfig()
        orig_vers_path = config.get(Option.SECTION_VERSIONING, "file")
        return os.path.join(self.repo, orig_vers_path)

    def setUpDevelopBranch(self):
        git.branch("-f develop master", execution_path=self.repo)

    def assertSuccessfulFastForwardMerge(self, fromBranch="testPublish", toBranch="master"):
        try:
            self.assertEqual(
                git.currentBranch(execution_path=self.repo), toBranch,
                "FF merge did not put us on public branch")
            self.assertEqual(
                git.shortSHA(branchName=toBranch, execution_path=self.repo),
                git.shortSHA(branchName=fromBranch, execution_path=self.repo))
        except grape_errors.GrapeGitError as e:
            self.fail(f"{self.get_output()}\n{e.gitCommand + e.gitOutput}")

    def assertSuccessfulSquashMerge(self, fromBranch="testPublish", toBranch="master"):
        self.assertEqual(git.currentBranch(execution_path=self.repo), toBranch)
        self.assertNotEqual(git.shortSHA(branchName=toBranch, execution_path=self.repo),
                            git.shortSHA(branchName=fromBranch, execution_path=self.repo))
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}", execution_path=self.repo))

    def assertSuccessfulSquashCascadeMerge(self, fromBranch="testPublish", toBranch="master", cascadeDest="develop"):
        currentBranch = git.currentBranch(execution_path=self.repo)
        self.assertEqual(currentBranch, cascadeDest)
        self.assertFalse(git.diff(f"--name-only {toBranch} {fromBranch}", execution_path=self.repo))
        self.assertFalse(git.diff(f"--name-only {toBranch} {cascadeDest}", execution_path=self.repo))
        self.assertTrue(git.branchUpToDateWith(toBranch, cascadeDest, execution_path=self.repo))
        self.assertFalse(git.branchUpToDateWith(toBranch, fromBranch, execution_path=self.repo))

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
            self.menu.set_command_path(self.repo)

            ret = self.menu.applyMenuChoice("publish", args=args)

            self.assertEquals(ret, not assertFail, msg="publish returned " +str(ret))
        except SystemExit as e:
            self.fail(f"{self.get_output()}\n{e.message}")
        #origin has not been set up for these repos yet
        #self.assertNotIn("fatal:", self.output.getvalue())

    def assertGrapePublishFailed(self, args=None):
        self.assertGrapePublishWorked(args=args, assertFail=True)

    @patch('vine.utility.userInput')
    def testFFDefaultPublish(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()

    @patch('vine.utility.userInput')
    def testFFMergePublish(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()

    @patch('vine.utility.userInput')
    def testFFSquashPublish(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--squash"])
        self.assertSuccessfulSquashMerge()

    @patch('vine.utility.userInput')
    def testFFCascadePublish(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.setUpDevelopBranch()
        self.assertGrapePublishWorked(["--squash", "--cascade=develop"])
        self.assertSuccessfulSquashCascadeMerge()

    @patch('vine.utility.userInput')
    def testFFRebasePublish(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--rebase"])
        self.assertSuccessfulFastForwardMerge()

    @patch('vine.utility.userInput')
    def testTopicConfigOption(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        git.checkout("-b someOtherBranch", execution_path=self.repo)
        other_file = os.path.join(self.repo, "someOtherfile")
        testGrape.writeFile1(other_file)
        git.add(other_file, execution_path=self.repo)
        git.commit("-a -m \"someOtherfile\"", execution_path=self.repo)
        self.menu.set_command_path(self.repo)
        self.assertGrapePublishFailed(["--topic=testPublish"])

    @patch('vine.utility.userInput')
    def testCustomBuildStep(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello ,  echo world")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo hello", self.get_output())
        self.assertIn("echo world", self.get_output())
        self.assertIn("PERFORMING CUSTOM BUILD STEP", self.get_output())

    @patch('vine.utility.userInput')
    def testCustomTestStep(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo helloTest", self.get_output())
        self.assertIn("echo worldTest", self.get_output())
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.get_output())

    @patch('vine.utility.userInput')
    def testVersionTickArgumentPassing(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.menu.set_command_path(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertIn("v1.0.1", git.describe(execution_path=self.repo))

    @patch('vine.utility.userInput')
    def testStartStepStopStep(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.menu.set_command_path(self.repo)
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
        self.assertIn("v1.0.1", git.describe(execution_path=self.repo))

    @patch('vine.utility.userInput')
    def testPublishNestedSubprojects(self, mock_userInput):
        mock_userInput.side_effect = ['1.1.1']
        from test import testNestedSubproject
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")
        self.menu.set_command_path(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(
            self, execution_path=self.repo)
        self.assertEqual(
            git.currentBranch(execution_path=self.subproject),
            self.branch)

        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()

        self.assertEqual(
            git.currentBranch(execution_path=self.subproject), "master",
            f"on {git.currentBranch(execution_path=self.subproject)}, expected to be on master")

    @patch('vine.utility.userInput')
    def testPublishFromWithinNestedSubproject(self, mock_userInput):
        from test import testNestedSubproject
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        self.menu.set_command_path(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(
            self, execution_path=self.repo)

        self.menu.set_command_path(self.subproject)
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()

    @patch('vine.utility.userInput')
    def testPublishNewSubmodule(self, mock_userInput):
        from test import testNestedSubproject
        mock_userInput.side_effect = ['1.1.1']
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_PUBLISH, "buildCmds", "echo hello , echo world")
        config.set(Option.SECTION_PUBLISH, "testCmds", "echo helloTest , echo worldTest")

        # create backend for repo2
        repo2_origin = self.repo + "2-origin"
        os.mkdir(repo2_origin)
        git.gitcmd("init --bare", "Setup Failed", execution_path=repo2_origin)
        # clone repo2
        git.gitcmd(f"clone {repo2_origin} {self.repos[1]}",
                   "could not clone test bare repo", execution_path=self.repo)

        # create an initial public branch in repo2
        fname = os.path.join(self.repos[1], "testRepoFile")
        testGrape.writeFile1(fname)
        self.file1 = fname
        git.gitcmd(f"add {fname}", "Add Failed", execution_path=self.repos[1])
        git.gitcmd("commit -m \"initial commit\"", "Commit Failed",
                   execution_path=self.repos[1])
        git.gitcmd("push origin master", "push to master failed",
                   execution_path=self.repos[1])
        git.branch("testPublish", execution_path=self.repos[1])
        git.push("origin testPublish", execution_path=self.repos[1])
        # add repo2 as a submodule to repo1
        git.submodule(f"add {repo2_origin} submodule1",
                      execution_path=self.repo)
        git.commit("-m \"added submodule1\"", execution_path=self.repo)
        # add changes to feature branch
        submodule_path = os.path.join(self.repo, "submodule1")
        git.checkout("testPublish", execution_path=submodule_path)
        f3 = os.path.join(self.repo, "submodule1", "f3")
        testGrape.writeFile3(f3)
        git.add(f3, execution_path=submodule_path)
        git.commit("-m \"added f3\"", execution_path=submodule_path)
        # save the log from the feature branch
        branchlog = git.log(execution_path=submodule_path)
        git.add(submodule_path, execution_path=self.repo)
        git.commit("-m \"updated gitlink\"", execution_path=self.repo)

        self.assertEqual(git.currentBranch(execution_path=self.repo),
                         self.branch)
        # merge feature branch into public branch
        self.assertGrapePublishWorked(["--merge","--recurse","--submodulePublic=master"])
        self.assertSuccessfulFastForwardMerge()

        # check out a clean version of repo2
        checkrepo = os.path.join(self.repo, "repocheck")
        git.gitcmd(f"clone {repo2_origin} {checkrepo}",
                   "could not clone test bare repo", execution_path=self.repo)
        git.checkout("master", execution_path=checkrepo)
        # ensure that master has been updated with the new commits
        mergelog = git.log(execution_path=checkrepo)
        self.assertEqual(branchlog, mergelog)
