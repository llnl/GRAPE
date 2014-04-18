import os
import sys

import option
import utility


class Test(option.Option):
    def __init__(self):
        super(Test, self).__init__()
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    def execute(self, args):
        testDir = os.path.join(utility.grapeDir(), "test")
        if not testDir in sys.path:
            print "appending %s to path" % testDir
            sys.path.append(testDir)
        import testGrape

        good = testGrape.main()
        if not good:
            print "*"*80
            print "*"*80
            print "Hey, a test has failed"
            print "*"*80
            print "*"*80
            exit(1)
        return True

    def setDefaultConfig(self, config):
        pass
