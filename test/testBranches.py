import os
from vine import grapeGit as git
from test import testGrape


class TestBranches(testGrape.TestGrape):

    def testBranches(self):
        os.chdir(self.repo)
        contents = git.branch()
        self.assertIn('master', contents, msg="vine.branches could not find the master branch")
