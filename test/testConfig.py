import os
import sys
import testGrape
if os.path.pardir not in sys.path:
    sys.path.insert(0, os.path.pardir)

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        os.chdir(self.repo)

        self.queueUserInput(["\n", "\n", "\n", "\n"])
        ret = self.menu.applyMenuChoice("config")
        contents = self.output.getvalue()
        self.assertTrue(contents)
