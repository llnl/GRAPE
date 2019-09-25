import os
import shutil
import sys
from test.testGrape import *
from vine import grape_errors
from vine import grapeGit as git


class TestGrapeGit(TestGrape):

    def testAdd(self):
        try:
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repo)
            statusStr = git.status(execution_path=self.repo)
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

        self.assertTrue("new file:   f1" in statusStr)

    def testCommit(self):
        try:
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            commitStr = "testCommit: added f1"
            git.add("f1", execution_path=self.repo)
            git.commit(f"f1 -m \"{commitStr}\"", execution_path=self.repo)
            log = git.log(execution_path=self.repo)
            self.assertTrue(commitStr in log)
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testCheckout(self):
        try:
            git.checkout("-b testCheckout/tmpBranch", execution_path=self.repo)
            self.assertEqual(git.currentBranch(execution_path=self.repo),
                             "testCheckout/tmpBranch",
                             "checkout of new branch failed")
            git.checkout("master", execution_path=self.repo)
            self.assertEqual(git.currentBranch(execution_path=self.repo),
                             "master", "switching to master did not work")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testMerge(self):
        # First, test to see if a merge that should work does.
        try:
            #add a file on the master branch.
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repo)
            commitStr = "testMerge: added f1"
            git.commit(f" -m \"{commitStr}\"", execution_path=self.repo)
            # edit it on branch testMerge/tmp1
            git.checkout("-b testMerge/tmp1", execution_path=self.repo)
            writeFile2(f1name)
            git.commit("-a -m \"edited f1\"", execution_path=self.repo)
            # perform same editon master
            git.checkout("master", execution_path=self.repo)
            writeFile2(f1name)
            git.commit("-a -m \"edited f1 on master\"",
                       execution_path=self.repo)
            # switch back to tmp, merge changes from master down
            git.checkout("testMerge/tmp1", execution_path=self.repo)
            output = git.merge(
                "master -m \"merged identical change from master\"",
                execution_path=self.repo)
            log = git.log(execution_path=self.repo)
            self.assertTrue("identical change from master" in log)
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

        # Second, test that a merge that should result in a conflict throws an appropriate GrapeGitError exception.
        try:
            git.checkout("master", execution_path=self.repo)
            f2name = os.path.join(self.repo,"f2")
            writeFile3(f2name)
            git.add(f2name, execution_path=self.repo)
            git.commit("-m \"added f2\"", execution_path=self.repo)
            git.checkout("testMerge/tmp1", execution_path=self.repo)
            writeFile2(f2name)
            git.add(f2name, execution_path=self.repo)
            git.commit("-m \"added f2 in tmp branch\"",
                       execution_path=self.repo)
            git.merge("master -m \"merged master branch into testmerge/tmp1\"",
                      execution_path=self.repo)
            self.fail("Merge did not throw grapeGitError for conflict")
        except grape_errors.GrapeGitError as error:
            status = git.status(execution_path=self.repo)
            self.assertTrue("conflict" in status,
                            f"'conflict' not in status message {status}")

    def testMergeAbort(self):
        try:
            git.branch("testMergeAbort/tmp1 HEAD", execution_path=self.repo)
            #add a file on the master branch.
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repo)
            commitStr = "testMergeAbort: added f1"
            git.commit(f" -m \"{commitStr}\"", execution_path=self.repo)
            # also add it on the tmp branch
            git.checkout("testMergeAbort/tmp1", execution_path=self.repo)
            writeFile2(f1name)
            git.add("f1", execution_path=self.repo)
            git.commit(" -m \"testMergeAbort/tmp1 : added f1\"",
                       execution_path=self.repo)
            # a merge should generate a conflict
            git.merge("master -m \"merging from master\"",
                      execution_path=self.repo)
            self.fail("conflict did not throw exception")
        except:
            status = git.status(execution_path=self.repo)
            self.assertTrue("conflict" in status,
                            f"'conflict' not in status message {status} ")
            git.mergeAbort(execution_path=self.repo)
            status = git.status(execution_path=self.repo)
            self.assertFalse("conflict" in status, "conflict not removed by aborting merge")

    def testFetch(self):
        try:
            git.clone(source_repo=self.repo, clone_repo=self.repos[1],
                      execution_path=self.repo)
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repo)
            commitStr = "testFetch: added f1"
            git.commit(f" -m \"{commitStr}\"", execution_path=self.repo)
            log = git.log("--all", execution_path=self.repos[1])
            self.assertFalse(commitStr in log, "commit message in log before it should be")
            git.fetch("origin", execution_path=self.repos[1])
            log = git.log("--all", execution_path=self.repos[1])
            self.assertTrue(commitStr in log, "commit message not in log --all after fetch")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testPull(self):
        try:
            git.clone(source_repo=self.repo, clone_repo=self.repos[1],
                      execution_path=self.repo)
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repo)
            commitStr = "testPull: added f1"
            git.commit(f" -m \"{commitStr}\"", execution_path=self.repo)
            log = git.log("--all", execution_path=self.repos[1])
            self.assertFalse(commitStr in log, "commit message in log before it should be")
            git.pull("origin master", execution_path=self.repos[1])
            log = git.log(execution_path=self.repos[1])
            self.assertTrue(commitStr in log, "commit message not in log after pull")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testPush(self):
        try:
            f2name = os.path.join(self.repo, "f2")
            writeFile2(f2name)
            git.add(f2name, execution_path=self.repo)
            git.commit(" -m \"initial commit for testPush\"",
                       execution_path=self.repo)
            git.clone(source_repo=self.repo, clone_repo=self.repos[1],
                      execution_path=self.repo)
            git.checkout("-b testPush/tmpBranchToAllowPushesToMaster",
                         execution_path=self.repo)
            f1name = os.path.join(self.repos[1], "f1")
            writeFile1(f1name)
            git.add("f1", execution_path=self.repos[1])
            commitStr = "testPush: added f1"
            git.commit(f" -m \"{commitStr}\"", execution_path=self.repos[1])
            log = git.log("--all", execution_path=self.repo)
            self.assertFalse(commitStr in log,"commit message in log before it should be")
            pushOutput = git.push("origin master", execution_path=self.repos[1])
            git.checkout("master", execution_path=self.repo)
            log = git.log(execution_path=self.repo)
            self.assertTrue(commitStr in log, "commit message not in log after push")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testBranch(self):
        try:
            git.branch(argstr="testBranch/newBranch HEAD", execution_path=self.repo)
            branches = git.branch(execution_path=self.repo)
            self.assertTrue("testBranch/newBranch" in branches,
                            f"new branch not in returned string {branches} ")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testCloneAndShowRemote(self):
        localSource = self.repo
        localClone = self.repos[1]
        try:
            self.assertTrue(git.clone(source_repo=localSource,
                                      clone_repo=localClone,
                                      execution_path=self.repo))
            fetchLine = f"Fetch URL: {localSource}"
            showRemoteOutput = git.showRemote(execution_path=localClone)
            self.assertTrue(fetchLine in showRemoteOutput,
                            f"could not find {fetchLine} in output")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testRebase(self):
        try:
            f1name = os.path.join(self.repo, "f1")
            writeFile1(f1name)
            git.add(f1name, execution_path=self.repo)
            git.commit("-m \"initial commit\"", execution_path=self.repo)
            git.branch("testRebase/branchToRebase HEAD",
                       execution_path=self.repo)
            # while still on master add another commit.
            writeFile2(f1name)
            git.add(f1name, execution_path=self.repo)
            git.commit("-m \"edited f1\"", execution_path=self.repo)
            # switch to new branch, add a new file, commit, rebase onto master.
            git.checkout("testRebase/branchToRebase", execution_path=self.repo)
            f2name = os.path.join(self.repo,"f2")
            writeFile2(f2name)
            git.add(f2name, execution_path=self.repo)
            git.commit("-m \"added f2\" ", execution_path=self.repo)
            self.assertFalse(
                git.branchUpToDateWith("testRebase/branchToRebase", "master",
                                       execution_path=self.repo),
                "attempting rebase in situation where rebase will not do anything.")
            try:
                git.rebase("master", execution_path=self.repo)
                self.assertTrue(
                    git.branchUpToDateWith("testRebase/branchToRebase",
                                           "master", execution_path=self.repo),
                    "rebase did not bring current branch up to date with master")
            except grape_errors.GrapeGitError as error:
                self.fail("rebase that should not have generated a conflict failed")
        except grape_errors.GrapeGitError as error:
            self.handleGitError(error)

    def testParseSubprojectRemoteURL(self):
        try:
            hardlink_root = os.path.join(self.repo, 'hardlinktest')
            root_b = os.path.join(hardlink_root, 'b')
            root_b_c = os.path.join(root_b, 'c')
            root_b_c_d = os.path.join(root_b_c, 'd')
            root_b_c_d_e = os.path.join(root_b_c, 'd', 'e')
            os.makedirs(root_b_c_d_e)

            #Set the remote origin url to the cwd for testing purposes
            git.config(f"--add remote.origin.url {root_b_c}",
                       execution_path=root_b_c)

            #Test existing hard paths
            urls = ["/usr/gapps/grape",
                    "ssh://www.grape.com",
                    "https://www.grape.com"]
            for url in urls:
                self.assertEqual(url, git.parseSubprojectRemoteURL(url, execution_path=root_b_c))

            #Test some relative paths
            two_dirs_up = os.path.join(os.path.pardir, os.path.pardir)
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.curdir, execution_path=root_b_c).endswith(root_b_c))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.pardir, execution_path=root_b_c).endswith(root_b))
            self.assertTrue(git.parseSubprojectRemoteURL(two_dirs_up, execution_path=root_b_c).endswith(hardlink_root))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.join(two_dirs_up, 'b'), execution_path=root_b_c).endswith(root_b))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.join(two_dirs_up, 'b', os.path.pardir), execution_path=root_b_c).endswith(hardlink_root))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.join(two_dirs_up, 'b', os.path.pardir, 'b'), execution_path=root_b_c).endswith(root_b))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.join(two_dirs_up, 'b', os.path.pardir), execution_path=root_b_c).endswith(hardlink_root))
            self.assertTrue(git.parseSubprojectRemoteURL("d", execution_path=root_b_c).endswith(root_b_c_d))
            self.assertTrue(git.parseSubprojectRemoteURL(os.path.join('d', 'e'), execution_path=root_b_c).endswith(root_b_c_d_e))
        finally:
            test_root_dir = os.path.join(self.repo, hardlink_root)
            shutil.rmtree(test_root_dir)

    def handleGitError(self, error):
        self.fail(f"When executing\n{error.gitCommand}\n" +
                  f"Error {error.code} caught: {error.msg}\n" +
                  f"{error.gitOutput} ")
