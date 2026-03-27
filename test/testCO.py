__author__ = 'robinson96'
import os
import tempfile
from unittest.mock import patch
from test import testGrape
from vine import checkout
from vine import grape_errors
from vine import grapeGit as git


class TestCheckout(testGrape.TestGrape):
    # sets up an outer repo with two branches. master has file1.
    # addSubmodule has a submodule added.
    # the submodule has two branches, master and addSubmodule
    # master has the file f3, addSubmodule has the file f2.
    def setUpSubmoduleBranch(self):
        git.clone(source_repo=self.repo, clone_repo=self.repos[1],
                  execution_path=self.defaultWorkingDirectory)
        git.checkout("-b addSubmodule", execution_path=self.repo)
        git.submodule(f"add {self.repos[1]} submodule", execution_path=self.repo)
        git.commit("-m \"added submodule\"", execution_path=self.repo)
        git.push("origin HEAD", execution_path=self.repo)

        # put the remote for the submodule into a HEAD-less state so it can accept pushes
        git.checkout("--orphan dummy_branch_name", execution_path=self.repos[1])

        # go to the submodule and add a file to it.
        f2 = os.path.join(self.repo, "submodule", "f2")
        testGrape.writeFile2(f2)

        execution_path = os.path.join(self.repo, "submodule")
        git.checkout("-b addSubmodule", execution_path=execution_path)
        git.add(f2, execution_path=execution_path)
        git.commit("-m \"added f2\"", execution_path=execution_path)

        # add another file on the master branch for the submodule
        git.branch("-f master HEAD", execution_path=execution_path)
        git.checkout("master", execution_path=execution_path)
        f3 = os.path.join(self.repo, "submodule", "f3")
        testGrape.writeFile3(f3)
        git.add(f3, execution_path=execution_path)
        git.commit("f3 -m \"f3\"", execution_path=execution_path)

        # update the submodule's remote
        git.push("origin --all", execution_path=execution_path)

        # git back to the master branch in the original repository
        git.checkout("master", execution_path=self.repo)

    def switchToMaster(self):
        self.menu.applyMenuChoice("checkout", ["master"])

    def switchToAddSubmodule(self):
        self.menu.applyMenuChoice("checkout", ["addSubmodule"])

    def assertFile1ExistsInSubmodule(self):
        self.assertTrue(os.path.exists(os.path.join(self.repo, "submodule", self.file1)),
                        "%s does not exist" % self.file1)

    def assertSubmoduleDirectoryDoesNotExist(self):
        self.assertFalse(os.path.exists(os.path.join(self.repo, "submodule")),
                         "submodule exists when it should not")

    @patch('vine.utility.userInput')
    def testSwitchingToBranchWithNewSubmodule(self, mock_userInput):
        try:
            self.setUpSubmoduleBranch()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n"]
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n", "\n"]
            # switch to master, saying 'y' to delete request
            self.switchToMaster()
            self.assertSubmoduleDirectoryDoesNotExist()

            mock_userInput.side_effect = ["y", "\n", "\n", "\n"]
            # switch to addSubmodule, saying yes to request to have submodule
            self.switchToAddSubmodule()
            self.assertFile1ExistsInSubmodule()

            mock_userInput.side_effect = ["y", "\n", "\n"]
            # switch back to master, this time saying don't delete request
            self.switchToMaster()
            self.assertFile1ExistsInSubmodule()
        except grape_errors.GrapeGitError as e:
            self.fail('\n'.join(self.get_output()) + e.gitCommand + '\n' + e.gitOutput)

    @patch("vine.checkout.shouldParallelizeSubmoduleCleanup")
    @patch("vine.checkout.multi_repo_cmd_launcher.MultiRepoCommandLauncher")
    def testParallelCleanSubmodulesUsesLauncher(self, mock_launcher_cls,
                                                mock_should_parallelize):
        args = {"--updateView": True, "--noUpdateView": False}
        active_submodules = ["sub1"]
        submodules = ["sub1", "sub2", "sub3"]

        mock_should_parallelize.side_effect = [True, False, True]
        mock_launcher = mock_launcher_cls.return_value
        mock_launcher.launchFromWorkspaceDir.return_value = [True, False]

        failed, serial = checkout.parallelCleanSubmodules(
            submodules, args, True, active_submodules,
            workspace_dir=self.repo)

        mock_launcher_cls.assert_called_once_with(
            checkout.launcherCleanSubmodule,
            listOfRepoBranchArgTuples=[
                ("sub1", "",
                 {"checkoutArgs": args,
                  "veryclean": True,
                  "activeSubmodules": active_submodules}),
                ("sub3", "",
                 {"checkoutArgs": args,
                  "veryclean": True,
                  "activeSubmodules": active_submodules}),
            ],
            workspace_dir=self.repo)
        mock_launcher.launchFromWorkspaceDir.assert_called_once_with(
            noPause=True)
        self.assertEqual(failed, ["sub3"])
        self.assertEqual(serial, ["sub2"])

    @patch("vine.checkout.git.show")
    @patch("vine.checkout.git.diff")
    def testParseGitModulesDiffOutputDetectsMovedSubmodule(self, mock_diff,
                                                           mock_show):
        mock_diff.side_effect = [
            ".gitmodules",
            "R100\told/sub\tnew/sub",
        ]
        mock_show.side_effect = [
            '[submodule "lib"]\n\tpath = old/sub\n\turl = ssh://repo/lib.git\n',
            '[submodule "lib"]\n\tpath = new/sub\n\turl = ssh://repo/lib.git\n',
        ]

        added = []
        removed = []
        changed = []
        moved = {}

        checkout.parseGitModulesDiffOutput(
            "HEAD", "branch", added, removed, changed, moved,
            workspace_dir=self.repo)

        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(changed, [])
        self.assertEqual(moved, {"old/sub": "new/sub"})

    @patch("vine.checkout.git.show")
    @patch("vine.checkout.git.diff")
    def testParseGitModulesDiffOutputDetectsMovedSubmoduleWhenNameChanges(
            self, mock_diff, mock_show):
        mock_diff.side_effect = [
            ".gitmodules",
            "",
        ]
        mock_show.side_effect = [
            '[submodule "imports/lib"]\n\tpath = old/sub\n\turl = ssh://repo/lib.git\n',
            '[submodule "tpl/lib"]\n\tpath = new/sub\n\turl = ssh://repo/lib.git\n',
        ]

        added = []
        removed = []
        changed = []
        moved = {}

        checkout.parseGitModulesDiffOutput(
            "HEAD", "branch", added, removed, changed, moved,
            workspace_dir=self.repo)

        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(changed, [])
        self.assertEqual(moved, {"old/sub": "new/sub"})

    @patch("vine.checkout.git.show")
    @patch("vine.checkout.git.diff")
    def testParseGitModulesDiffOutputHandlesMissingGitmodules(self, mock_diff,
                                                              mock_show):
        mock_diff.return_value = ".gitmodules"
        mock_show.side_effect = ["", None]

        added = []
        removed = []
        changed = []

        checkout.parseGitModulesDiffOutput(
            "HEAD", "master", added, removed, changed,
            workspace_dir=self.repo)

        self.assertEqual(added, [])
        self.assertEqual(removed, [])
        self.assertEqual(changed, [])

    @patch("vine.checkout.git.fetch")
    @patch("vine.checkout.git.diff")
    def testParseGitModulesDiffOutputFetchesRemoteQualifiedBranch(self,
                                                                  mock_diff,
                                                                  mock_fetch):
        mock_diff.side_effect = [
            grape_errors.GrapeGitError(
                "bad revision", 128, "fatal: bad revision 'origin/newBranch'",
                "git diff"),
            "",
        ]

        added = []
        removed = []
        changed = []

        checkout.parseGitModulesDiffOutput(
            "HEAD", "origin/newBranch", added, removed, changed,
            workspace_dir=self.repo)

        mock_fetch.assert_called_once_with("origin", "newBranch",
                                           execution_path=self.repo)

    @patch("vine.checkout.git.submodule")
    @patch("vine.checkout.git.config")
    @patch("vine.checkout.git.gitDir")
    @patch("vine.checkout.git.isWorkingDirectoryClean")
    def testMoveSubmoduleRewritesGitMetadata(self, mock_is_clean,
                                             mock_gitdir, mock_config,
                                             mock_submodule):
        mock_is_clean.return_value = True

        workspace = tempfile.mkdtemp(dir=self.defaultWorkingDirectory)
        old_sub = os.path.join(workspace, "old", "sub")
        new_sub = os.path.join(workspace, "new", "sub")
        old_module_dir = os.path.join(workspace, ".git", "modules", "old", "sub")
        new_module_dir = os.path.join(workspace, ".git", "modules", "new", "sub")
        mock_gitdir.return_value = old_module_dir
        os.makedirs(old_module_dir)
        os.makedirs(old_sub)

        old_gitfile = os.path.join(old_sub, ".git")
        with open(old_gitfile, "w") as gitfile:
            gitfile.write("gitdir: ../../.git/modules/old/sub\n")
        with open(os.path.join(old_module_dir, "config"), "w") as config_file:
            config_file.write("[core]\n")

        moved = checkout.moveSubmodule("old/sub", "new/sub",
                                       workspace_dir=workspace)

        self.assertTrue(moved)
        self.assertFalse(os.path.exists(old_sub))
        self.assertTrue(os.path.exists(new_sub))
        self.assertFalse(os.path.exists(old_module_dir))
        self.assertTrue(os.path.exists(new_module_dir))
        with open(os.path.join(new_sub, ".git")) as gitfile:
            self.assertEqual(gitfile.read(),
                             "gitdir: ../../.git/modules/new/sub\n")
        mock_config.assert_called_once_with(
            f"--file {os.path.join(workspace, '.git', 'modules', 'new', 'sub', 'config')} core.worktree",
            "../../../../new/sub", execution_path=workspace)
        mock_submodule.assert_any_call("init -- new/sub",
                                       execution_path=workspace)
        mock_submodule.assert_any_call("sync -- new/sub",
                                       execution_path=workspace)

    @patch("vine.checkout.git.submodule")
    @patch("vine.checkout.git.config")
    @patch("vine.checkout.git.gitDir")
    @patch("vine.checkout.git.isWorkingDirectoryClean")
    def testMoveSubmoduleReplacesEmptyDestination(self, mock_is_clean,
                                                  mock_gitdir, mock_config,
                                                  mock_submodule):
        mock_is_clean.return_value = True

        workspace = tempfile.mkdtemp(dir=self.defaultWorkingDirectory)
        old_sub = os.path.join(workspace, "old", "sub")
        new_sub = os.path.join(workspace, "new", "sub")
        old_module_dir = os.path.join(workspace, ".git", "modules", "old", "sub")
        new_module_dir = os.path.join(workspace, ".git", "modules", "new", "sub")
        mock_gitdir.return_value = old_module_dir
        os.makedirs(old_module_dir)
        os.makedirs(old_sub)
        os.makedirs(new_sub)

        with open(os.path.join(old_sub, ".git"), "w") as gitfile:
            gitfile.write("gitdir: ../../.git/modules/old/sub\n")
        with open(os.path.join(old_module_dir, "config"), "w") as config_file:
            config_file.write("[core]\n")
        with open(os.path.join(old_sub, "tracked.txt"), "w") as subfile:
            subfile.write("contents\n")

        moved = checkout.moveSubmodule("old/sub", "new/sub",
                                       workspace_dir=workspace)

        self.assertTrue(moved)
        self.assertFalse(os.path.exists(old_sub))
        self.assertTrue(os.path.exists(os.path.join(new_sub, "tracked.txt")))
        self.assertFalse(os.path.exists(old_module_dir))
        self.assertTrue(os.path.exists(new_module_dir))
        mock_config.assert_called_once()
        mock_submodule.assert_any_call("init -- new/sub",
                                       execution_path=workspace)
        mock_submodule.assert_any_call("sync -- new/sub",
                                       execution_path=workspace)

    @patch("vine.checkout.git.submodule")
    @patch("vine.checkout.git.config")
    @patch("vine.checkout.git.gitDir")
    @patch("vine.checkout.git.isWorkingDirectoryClean")
    def testMoveSubmoduleReplacesStaleDestinationGitdir(self, mock_is_clean,
                                                        mock_gitdir,
                                                        mock_config,
                                                        mock_submodule):
        mock_is_clean.return_value = True

        workspace = tempfile.mkdtemp(dir=self.defaultWorkingDirectory)
        old_sub = os.path.join(workspace, "old", "sub")
        new_sub = os.path.join(workspace, "new", "sub")
        old_module_dir = os.path.join(workspace, ".git", "modules", "old", "sub")
        new_module_dir = os.path.join(workspace, ".git", "modules", "new", "sub")
        mock_gitdir.return_value = old_module_dir
        os.makedirs(old_module_dir)
        os.makedirs(new_module_dir)
        os.makedirs(old_sub)

        with open(os.path.join(old_sub, ".git"), "w") as gitfile:
            gitfile.write("gitdir: ../../.git/modules/old/sub\n")
        with open(os.path.join(old_module_dir, "config"), "w") as config_file:
            config_file.write("[core]\n")
        with open(os.path.join(old_sub, "tracked.txt"), "w") as subfile:
            subfile.write("contents\n")
        with open(os.path.join(new_module_dir, "stale"), "w") as stale_file:
            stale_file.write("stale\n")

        moved = checkout.moveSubmodule("old/sub", "new/sub",
                                       workspace_dir=workspace)

        self.assertTrue(moved)
        self.assertFalse(os.path.exists(old_sub))
        self.assertFalse(os.path.exists(old_module_dir))
        self.assertTrue(os.path.exists(os.path.join(new_sub, "tracked.txt")))
        self.assertFalse(os.path.exists(os.path.join(new_module_dir, "stale")))
        mock_config.assert_called_once()
        mock_submodule.assert_any_call("init -- new/sub",
                                       execution_path=workspace)
        mock_submodule.assert_any_call("sync -- new/sub",
                                       execution_path=workspace)
