import os
import shutil
import sys
import tempfile
import unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, clone, grapeGit as git

class TestClone(testGrape.TestGrape):
    def testClone(self):
        self.queueUserInput(['\n', '\n', '\n', '\n'])
        args = [self.repo, self.repos[1], "--recursive"]
        ret =grapeMenu.menu().applyMenuChoice("clone", args)
        self.assertTrue(ret)
        # check to make sure we didn't get a usage string dump
        contents = self.output.getvalue()
        self.assertNotIn(contents, "Usage: grape-clone")

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

