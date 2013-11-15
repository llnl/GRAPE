#!/usr/bin/env python

import sys, unittest, StringIO
import testUtility

if not ".." in sys.path:
    sys.path.append( ".." )
from grape import Grape

class Test_help(unittest.TestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.stdout = sys.stdout
        sys.stdout = self.output

    def tearDown(self):
        sys.stdout = self.stdout
        self.output.close()

    def test_command1(self):
        grape = Grape()
        ret = grape.options["help"].execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
        self.assertTrue( "rel)" in contents)
        self.assertTrue( "hot)" in contents)
        self.assertTrue( "minor)" in contents)
        self.assertTrue( "rev)" in contents)


class Test_branch(unittest.TestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.stdout = sys.stdout
        sys.stdout = self.output

    def tearDown(self):
        sys.stdout = self.stdout
        self.output.close()

    def test_command1(self):
        grape = Grape()
        ret = grape.options["b"].execute()
        contents = self.output.getvalue()
        self.assertTrue( ret )

        
def main():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(Test_help))
    suite.addTest(unittest.makeSuite(Test_branch))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main()
