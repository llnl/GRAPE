import logging
from io import StringIO
import os
import shutil
import sys
import tempfile
from unittest.mock import patch
from test import testGrape
from vine import clone
from vine import grapeGit as git


class TestClone(testGrape.TestGrape):

    @patch('vine.utility.userInput')
    def testClone(self, mock_userInput):
        cwd = os.getcwd()
        self.setUpConfig()
        args = [self.repo, self.repos[1], "--recursive"]
        mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
        ret = self.menu.applyMenuChoice("clone", args)
        self.assertTrue(ret)

        # check to make sure we didn't get a usage string dump
        contents = self.get_output()
        self.assertNotIn(contents, "Usage: grape-clone")

        # check to make sure we didn't see a GRAPE WARNING
        self.assertNotIn("WARNING", contents,
                         f"GRAPE ISSUED A WARNING DURING A CLONE\n{contents}")

        # check to make sure the new repo has the old repo as a remote
        self.menu.set_workspace_dir(self.repos[1])
        remote = git.showRemote(execution_path=self.repos[1])
        self.assertIn(self.repo, remote)
        self.assertTrue(ret)
        # grape clone changes the working directory, so reset it
        os.chdir(cwd)

    def testHelpMessage(self):
        cwd = os.getcwd()
        doc_output = StringIO()
        tmp_stdout = sys.stdout
        sys.stdout = doc_output

        args = ["--help"]
        with self.assertRaises(SystemExit):
            ret = self.menu.applyMenuChoice("clone", args)
        # NOTE: Below assertion is testing 'docopt' logic.
        self.assertIn(clone.Clone.__doc__, doc_output.getvalue())
        sys.stdout = tmp_stdout
        doc_output.close()
        # grape clone changes the working directory, so reset it
        os.chdir(cwd)

    @patch('vine.utility.userInput')
    def testClone02(self, mock_userInput):
        cwd = os.getcwd()
        tempDir = tempfile.mkdtemp()
        args = [self.repo, tempDir]
        try:
            mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
            ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            #ToDo: Finish checking contents
            #contents = self.get_output()
            #self.stdout(contents)
        finally:
            self._temp_dir_cleanup(tempDir)
            # grape clone changes the working directory, so reset it
            os.chdir(cwd)

#    @patch('vine.utility.userInput')
#    def testRecursiveCloneWithSubmodule(self, mock_userInput):
    def testRecursiveCloneWithSubmodule(self):
        cwd = os.getcwd()
        self.setUpConfig()
        self.menu.set_workspace_dir(self.repo)

        # make a repo to turn into a submodule
        git.clone(argstr="--mirror", source_repo=self.repo,
                  clone_repo=self.repos[1],
                  execution_path=self.defaultWorkingDirectory)
        # add repo2 as a submodule to repo1
        git.submodule(f"add {self.repos[1]} submodule1",
                      execution_path=self.repo)
        git.commit("-m \"added submodule1\"", execution_path=self.repo)

        #Now clone the repo into a temp dir and make sure the submodule is in the clone
        try:
            tempDir = os.path.realpath(tempfile.mkdtemp())
            args = [self.repo, tempDir, "--recursive"]
#            mock_userInput.side_effect = ["\n", "\n", "\n", "\n", "\n", "\n"]
            with self.queue_user_input(["\n", "\n", "\n", "\n", "\n", "\n"]):
                ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            submodulepath = os.path.join(tempDir, "submodule1")
            self.assertTrue(os.path.exists(submodulepath), "submodule1 does not exist in clone")
        finally:
            self._temp_dir_cleanup(tempDir)
            # grape clone changes the working directory, so reset it
            os.chdir(cwd)

    @patch('vine.utility.userInput')
    def testRecursiveCloneNestedSubproject(self, mock_userInput):
        cwd = os.getcwd()
        # make a repo to turn into a submodule
        git.clone(argstr="--mirror", source_repo=self.repo,
                  clone_repo=self.repos[1],
                  execution_path=self.defaultWorkingDirectory)
        self.menu.set_workspace_dir(self.repo)
        subproject_path = os.path.join('subs', 'subproject1')
        self.menu.applyMenuChoice("addSubproject",
                                  ["--name=subproject1",
                                   f"--prefix={subproject_path}",
                                   "--branch=master",
                                   f"--url={self.repos[1]}",
                                   "--nested",
                                   "--noverify"])
        self.menu.applyMenuChoice("commit", ["-m", "\"added subproject1\""])
        logging.info(git.log("--decorate", execution_path=self.repo))

        #Now clone the repo into a temp dir and make sure the subproject is in the clone
        try:
            tempDir = os.path.realpath(tempfile.mkdtemp())
            args = [self.repo, tempDir, "--recursive", "--allNested"]
            mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
            ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            # ensure we are on master with all nested subprojects
            self.menu.set_workspace_dir(tempDir)
            args = ["master", "--updateView"]
            mock_userInput.side_effect = ["all\n"]
            ret = self.menu.applyMenuChoice("checkout", args)
            self.assertTrue(ret, "vine.checkout master returned failure")
            logging.info(git.log("--decorate", execution_path=tempDir))

            subprojectpath = os.path.join(tempDir, subproject_path)
            self.assertTrue(os.path.exists(subprojectpath), "subproject1 does not exist in clone")
        finally:
            self._temp_dir_cleanup(tempDir)
            # grape clone changes the working directory, so reset it
            os.chdir(cwd)

    def _temp_dir_cleanup(self, tempDir):
        """Skips Windows permissions errors when testing as non-admin user."""
        def skip_rm(*args):
            pass
        shutil.rmtree(tempDir, onerror=skip_rm)
