import os
from test import testGrape


class TestConfig(testGrape.TestGrape):

    def testConfig(self):
        os.chdir(self.repo)

        with self.queue_user_input(["\n", "\n", "\n", "\n"]):
            self.menu.applyMenuChoice("config")
        contents = self.get_output()
        self.assertTrue(contents)
