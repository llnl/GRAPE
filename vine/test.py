import option

class Test(option.Option):
    key = "test"
    section = " OTHER "

    def Description(self):
        return "Test Grape."

    def Execute(self):
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
