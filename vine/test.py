import option

class Test(option.Option):
    def __init__(self):
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    def execute(self):
        if not ".." in sys.path:
            sys.path.append( ".." )
        from test import GrapeTest
        good = GrapeTest.main()
        if not good:
            print "*"*80
            print "*"*80
            print "Hey, a test has failed"
            print "*"*80
            print "*"*80

        return True
