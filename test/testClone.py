import os
import shutil
import sys
import tempfile
import unittest
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import grapeMenu, utility

class TestClone(testGrape.TestGrape):
    def testClone(self):
        args = {}
        args["<url>"] = "ssh://git@rz-stash.llnl.gov:7999/grp/grape.git"
        tempDir = tempfile.mkdtemp()
        args["<path>"] = tempDir
        try:
            menuOption = grapeMenu.menu().get_option("clone")
            self.assertIsNotNone(menuOption, "grapeMenu returned None for 'clone' option")

            ret = menuOption.execute(args)
            self.assertTrue(ret, "vine.clone.execute() returned failure")

            contents = self.output.getvalue()
            self.stdout(contents)
        finally:
            shutil.rmtree(tempDir)
