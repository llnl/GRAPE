import os, sys
import option

class Test(option.Option):
    def __init__(self):
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    def execute(self):
        if not "test" in sys.path:
            sys.path.append("test")
        import testGrape

        good = testGrape.main()
        if not good:
            print "*"*80
            print "*"*80
            print "Hey, a test has failed"
            print "*"*80
            print "*"*80

        return True
