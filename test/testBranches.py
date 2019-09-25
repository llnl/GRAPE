import os
from vine import grapeGit as git
from test import testGrape


class TestBranches(testGrape.TestGrape):

    def testBranches(self):
        contents = git.branch(execution_path=self.repo)
        self.assertIn('master', contents, msg="vine.branches could not find the master branch")
