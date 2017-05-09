import os
import shutil
import sys
import tempfile
import unittest
import testGrape
if not ".." in sys.path:
    sys.path.insert(0, "..")
from vine import grapeMenu, clone, grapeGit as git

class TestClone(testGrape.TestGrape):
    def testClone(self):
        self.setUpConfig()
        self.queueUserInput(['\n', '\n', '\n', '\n'])
        args = [self.repo, self.repos[1], "--recursive"]
        ret =grapeMenu.menu().applyMenuChoice("clone", args)
        self.assertTrue(ret)
        
        # check to make sure we didn't get a usage string dump
        contents = self.output.getvalue()
        self.assertNotIn(contents, "Usage: grape-clone")
        
        # check to make sure we didn't see a GRAPE WARNING
        self.assertNotIn("WARNING", contents, "GRAPE ISSUED A WARNING DURING A CLONE\n%s" % contents)

        # check to make sure the new repo has the old repo as a remote
        os.chdir(self.repos[1])
        remote = git.showRemote()
        self.assertIn(self.repo, remote)
        self.assertTrue(ret)

    def testHelpMessage(self):
        args = ["--help"]
        with self.assertRaises(SystemExit):
            ret = grapeMenu.menu().applyMenuChoice("clone", args)
        self.assertIn(clone.Clone.__doc__, self.output.getvalue())

    def testClone02(self):
        tempDir = tempfile.mkdtemp()
        args = [self.repo, tempDir]
        try:
            self.queueUserInput(["\n", "\n", "\n", "\n"])
            ret = grapeMenu.menu().applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            #ToDo: Finish checking contents
            #contents = self.output.getvalue()
            #self.stdout(contents)
        finally:
            shutil.rmtree(tempDir)

    def testRecursiveCloneWithSubmodule(self):
        # make a repo to turn into a submodule
        git.clone("--mirror %s %s " % (self.repo, self.repos[1]))
        # add repo2 as a submodule to repo1
        os.chdir(self.repo)
        git.submodule("add %s %s" % (os.path.join(self.repos[1]), "submodule1"))
        git.commit("-m \"added submodule1\"")

        #Now clone the repo into a temp dir and make sure the submodule is in the clone
        try:
            tempDir = tempfile.mkdtemp()
            args = [self.repo, tempDir, "--recursive"]
            self.queueUserInput(["\n", "\n", "\n", "\n","\n","\n"])
            ret = grapeMenu.menu().applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            submodulepath = os.path.join(tempDir, "submodule1")
            self.assertTrue(os.path.exists(submodulepath), "submodule1 does not exist in clone")
        finally:
            shutil.rmtree(tempDir)


    def testRecursiveCloneNestedSubproject(self):
        # make a repo to turn into a submodule
        git.clone("--mirror %s %s " % (self.repo, self.repos[1]))
        os.chdir(self.repo)
        grapeMenu.menu().applyMenuChoice("addSubproject", ["--name=subproject1", "--prefix=subs/subproject1",
                                                           "--branch=master", "--url=%s" % self.repos[1],
                                                           "--nested", "--noverify"])
        grapeMenu.menu().applyMenuChoice("commit",["-m", "\"added subproject1\""])

        #Now clone the repo into a temp dir and make sure the subproject is in the clone
        try:
            tempDir = tempfile.mkdtemp()
            self.queueUserInput(["\n", "\n", "\n", "\n"])
            args = [self.repo, tempDir, "--recursive", "--allNested"]
            ret = grapeMenu.menu().applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone returned failure")

            subprojectpath = os.path.join(tempDir, "subs/subproject1")
            self.assertTrue(os.path.exists(subprojectpath), "subproject1 does not exist in clone")
        finally:
            shutil.rmtree(tempDir)


