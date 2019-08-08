from vine import vine_subprocess
from test import testGrape


class TestBranches(testGrape.TestGrape):

    def testBranches(self):
        completed_process = vine_subprocess.executeSubProcess('git branch')
        contents = completed_process.stdout.decode()
        self.assertIn('master', contents, msg="vine.branches could not find the master branch")
