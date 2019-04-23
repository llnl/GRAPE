import os
import shutil
import sys
import tempfile
from grape.test import testGrape
from grape.vine import clone
from grape.vine import grapeGit as git


class TestClone(testGrape.TestGrape):

    def testClone(self):
        self.setUpConfig()
        args = [self.repo, self.repos[1], "--recursive"]
        with self.queue_user_input(["\n", "\n", "\n", "\n"]):
            ret = self.menu.applyMenuChoice("clone", args)
        self.assertTrue(ret)
        
        # check to make sure we didn't get a usage string dump
        contents = self.get_output()
        self.assertNotIn(contents, "Usage: grape-clone")
        
        # check to make sure we didn't see a GRAPE WARNING
        self.assertNotIn("WARNING", contents,
                         "GRAPE ISSUED A WARNING DURING A CLONE\n" + f"{contents}")

        # check to make sure the new repo has the old repo as a remote
        os.chdir(self.repos[1])
        remote = git.showRemote()
        self.assertIn(self.repo, remote)
        self.assertTrue(ret)

    def testHelpMessage(self):
        args = ["--help"]
        with self.assertRaises(SystemExit):
            ret = self.menu.applyMenuChoice("clone", args)
        self.assertIn(clone.Clone.__doc__, self.get_output())

    def testClone02(self):
        tempDir = tempfile.mkdtemp()
        args = [self.repo, tempDir]
        try:
            with self.queue_user_input(["\n", "\n", "\n", "\n"]):
                ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            #ToDo: Finish checking contents
            #contents = self.output.getvalue()
            #self.stdout(contents)
        finally:
            shutil.rmtree(tempDir)

    def testRecursiveCloneWithSubmodule(self):
        # make a repo to turn into a submodule
        git.clone(f"--mirror {self.repo} {self.repos[1]} ")
        # add repo2 as a submodule to repo1
        os.chdir(self.repo)
        git.submodule(f"add {os.path.join(self.repos[1])} submodule1")
        git.commit("-m \"added submodule1\"")

        #Now clone the repo into a temp dir and make sure the submodule is in the clone
        try:
            tempDir = tempfile.mkdtemp()
            args = [self.repo, tempDir, "--recursive"]
            with self.queue_user_input(["\n", "\n", "\n", "\n", "\n", "\n"]):
                ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            submodulepath = os.path.join(tempDir, "submodule1")
            self.assertTrue(os.path.exists(submodulepath), "submodule1 does not exist in clone")
        finally:
            shutil.rmtree(tempDir)


    def testRecursiveCloneNestedSubproject(self):
        # make a repo to turn into a submodule
        git.clone(f"--mirror {self.repo} {self.repos[1]} ")
        os.chdir(self.repo)
        self.menu.applyMenuChoice("addSubproject",
                                  ["--name=subproject1",
                                   "--prefix=subs/subproject1",
                                   "--branch=master",
                                   f"--url={self.repos[1]}",
                                   "--nested",
                                   "--noverify"])
        self.menu.applyMenuChoice("commit", ["-m", "\"added subproject1\""])
        git_log = git.log("--decorate")
        print(git_log)

        #Now clone the repo into a temp dir and make sure the subproject is in the clone
        try:
            tempDir = tempfile.mkdtemp()
            args = [self.repo, tempDir, "--recursive", "--allNested"]
            with self.queue_user_input(["\n", "\n", "\n", "\n"]):
                ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            # ensure we are on master with all nested subprojects
            os.chdir(tempDir)
            args = ["master", "--updateView"]
            with self.queue_user_input(["all\n"]):
                ret = self.menu.applyMenuChoice("checkout", args)
            self.assertTrue(ret, "vine.checkout master returned failure")
            git_log = git.log("--decorate")
            print(git_log)

            subprojectpath = os.path.join(tempDir, "subs/subproject1")
            self.assertTrue(os.path.exists(subprojectpath), "subproject1 does not exist in clone")
        finally:
            shutil.rmtree(tempDir)
