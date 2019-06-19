import os
import sys
import testGrape
if os.path.pardir not in sys.path:
    sys.path.insert(0, os.path.pardir)

class TestConfig(testGrape.TestGrape):
    def testConfig(self):
        os.chdir(self.repo)

        with self.queue_user_input(["\n", "\n", "\n", "\n"]):
            self.menu.applyMenuChoice("config")
        contents = self.get_output()
        self.assertTrue(contents)
