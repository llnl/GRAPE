import os
import sys

import option
import utility


class Test(option.Option):
    """
    grape test
    Runs grape's unit tests.    
    Usage: grape-test [--debug] [<suite>]...


    Arguments:
    <suite>  The name of the suite to test. The default is all.
             Enter listSuites as the suite name to list available suites. 


    """
    def __init__(self):
        super(Test, self).__init__()
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    def execute(self, args):
        testDir = os.path.join(utility.grapeDir(), "test")
        if not testDir in sys.path:
            sys.path.append(testDir)
        import testGrape
        good = testGrape.main(args["<suite>"], debug = args["--debug"])
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
