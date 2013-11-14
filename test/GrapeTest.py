
import sys
sys.path.append( ".." )

import unittest
import grape
import StringIO


class Test_help(unittest.TestCase):
    def setUp(self):
        self.output = StringIO.StringIO()
        self.stdout = sys.stdout
        sys.stdout = self.output

    def tearDown(self):
        sys.stdout = self.stdout
        self.output.close()

    def test_command1(self):
        ret = grape.options["help"].Execute()
        contents = self.output.getvalue()
        self.assertFalse( ret )
        self.assertTrue( "rel)" in contents)
        self.assertTrue( "hot)" in contents)
        self.assertTrue( "minor)" in contents)
        self.assertTrue( "rev)" in contents)

    def test_fail(self):
        self.assertFalse( True )
        
def main():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_help))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    main()
