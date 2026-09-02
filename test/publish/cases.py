import os
from unittest.mock import patch

from test import testGrape
from vine import config_parser_global
from vine import grapeGit as git


class PublishFFDefaultCase:

    @patch("vine.utility.userInput")
    def testFFDefaultPublish(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()


class PublishFFMergeCase:

    @patch("vine.utility.userInput")
    def testFFMergePublish(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()


class PublishFFSquashCase:

    @patch("vine.utility.userInput")
    def testFFSquashPublish(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--squash"])
        self.assertSuccessfulSquashMerge()


class PublishFFCascadeCase:

    @patch("vine.utility.userInput")
    def testFFCascadePublish(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.setUpDevelopBranch()
        self.assertGrapePublishWorked(["--squash", "--cascade=develop"])
        self.assertSuccessfulSquashCascadeMerge()


class PublishFFRebaseCase:

    @patch("vine.utility.userInput")
    def testFFRebasePublish(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.assertGrapePublishWorked(["--rebase"])
        self.assertSuccessfulFastForwardMerge()


class PublishTopicConfigCase:

    @patch("vine.utility.userInput")
    def testTopicConfigOption(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        git.checkout("-b someOtherBranch", execution_path=self.repo)
        other_file = os.path.join(self.repo, "someOtherfile")
        testGrape.writeFile1(other_file)
        git.add(other_file, execution_path=self.repo)
        git.commit("-a -m \"someOtherfile\"", execution_path=self.repo)
        self.assertGrapePublishFailed(["--topic=testPublish"])


class PublishCustomBuildCase:

    @patch("vine.utility.userInput")
    def testCustomBuildStep(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set("publish", "buildCmds", "echo hello ,  echo world")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo hello", self.get_output())
        self.assertIn("echo world", self.get_output())
        self.assertIn("PERFORMING CUSTOM BUILD STEP", self.get_output())


class PublishCustomTestCase:

    @patch("vine.utility.userInput")
    def testCustomTestStep(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()
        self.assertIn("echo helloTest", self.get_output())
        self.assertIn("echo worldTest", self.get_output())
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.get_output())


class PublishVersionTickCase:

    @patch("vine.utility.userInput")
    def testVersionTickArgumentPassing(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(["--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"])
        self.assertIn("v1.0.1", git.describe(execution_path=self.repo))


class PublishStartStopCase:

    @patch("vine.utility.userInput")
    def testStartStepStopStep(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set("publish", "buildCmds", "echo hello , echo world")
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")
        self.menu.set_workspace_dir(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        self.assertGrapePublishWorked(
            ["--startAt=tickVersion", "--stopAt=updateLog", "--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"]
        )
        self.assertGrapePublishWorked(
            ["--startAt=test", "--stopAt=deleteTopic", "--tickVersion=True", "-T", "--slot=3", "-T", "--file=VERSION.txt"]
        )
        self.assertIn("PERFORMING CUSTOM TEST STEP", self.get_output())
        self.assertNotIn("PERFORMING CUSTOM BUILD STEP", self.get_output())
        self.assertIn("v1.0.1", git.describe(execution_path=self.repo))


class PublishNestedSubprojectsCase:

    @patch("vine.utility.userInput")
    def testPublishNestedSubprojects(self, mock_userInput):
        from test import testNestedSubproject

        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set("publish", "buildCmds", "echo hello , echo world")
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")
        self.menu.set_workspace_dir(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self, execution_path=self.repo, branch="testPublish")
        self.assertEqual(git.currentBranch(execution_path=self.subproject), self.branch)
        self.assertGrapePublishWorked(["--merge"])
        self.assertSuccessfulFastForwardMerge()
        self.assertEqual(
            git.currentBranch(execution_path=self.subproject),
            "master",
            f"on {git.currentBranch(execution_path=self.subproject)}, expected to be on master",
        )


class PublishFromNestedSubprojectCase:

    @patch("vine.utility.userInput")
    def testPublishFromWithinNestedSubproject(self, mock_userInput):
        from test import testNestedSubproject

        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        self.menu.set_workspace_dir(self.repo)
        self.menu.applyMenuChoice("version", ["init", "v1.0.0", "--file=VERSION.txt", "--tag"])
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self, execution_path=self.repo, branch="testPublish")
        self.menu.set_workspace_dir(self.subproject)
        self.assertGrapePublishWorked()
        self.assertSuccessfulFastForwardMerge()


class PublishNewSubmoduleCase:

    @patch("vine.utility.userInput")
    def testPublishNewSubmodule(self, mock_userInput):
        mock_userInput.side_effect = ["1.1.1"]
        self.setUpBranchToFFMerge()
        config = config_parser_global.grapeConfig()
        config.set("publish", "buildCmds", "echo hello , echo world")
        config.set("publish", "testCmds", "echo helloTest , echo worldTest")

        repo2_origin = self.repo + "2-origin"
        os.mkdir(repo2_origin)
        git.gitcmd("init --bare", "Setup Failed", execution_path=repo2_origin)
        git.gitcmd(f"clone {repo2_origin} {self.repos[1]}", "could not clone test bare repo", execution_path=self.repo)

        fname = os.path.join(self.repos[1], "testRepoFile")
        testGrape.writeFile1(fname)
        self.file1 = fname
        git.gitcmd(f"add {fname}", "Add Failed", execution_path=self.repos[1])
        git.gitcmd("commit -m \"initial commit\"", "Commit Failed", execution_path=self.repos[1])
        git.gitcmd("push origin master", "push to master failed", execution_path=self.repos[1])
        git.branch("testPublish", execution_path=self.repos[1])
        git.push("origin testPublish", execution_path=self.repos[1])
        git.submodule(f"add {repo2_origin} submodule1", execution_path=self.repo)
        git.commit("-m \"added submodule1\"", execution_path=self.repo)

        submodule_path = os.path.join(self.repo, "submodule1")
        git.checkout("testPublish", execution_path=submodule_path)
        f3 = os.path.join(self.repo, "submodule1", "f3")
        testGrape.writeFile3(f3)
        git.add(f3, execution_path=submodule_path)
        git.commit("-m \"added f3\"", execution_path=submodule_path)
        branchlog = git.log(execution_path=submodule_path)
        git.add(submodule_path, execution_path=self.repo)
        git.commit("-m \"updated gitlink\"", execution_path=self.repo)

        self.assertEqual(git.currentBranch(execution_path=self.repo), self.branch)
        self.assertGrapePublishWorked(["--merge", "--recurse", "--submodulePublic=master"])
        self.assertSuccessfulFastForwardMerge()

        checkrepo = os.path.join(self.repo, "repocheck")
        git.gitcmd(f"clone {repo2_origin} {checkrepo}", "could not clone test bare repo", execution_path=self.repo)
        git.checkout("master", execution_path=checkrepo)
        mergelog = git.log(execution_path=checkrepo)
        self.assertEqual(branchlog, mergelog)
