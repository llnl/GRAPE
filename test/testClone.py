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
    def testClone02(self):
        args = {}
        args["<url>"] = "ssh://git@rz-stash.llnl.gov:7999/grp/grape.git"
        tempDir = tempfile.mkdtemp()
        args["<path>"] = tempDir
        try:
            ret = grapeMenu.menu().applyMenuChoice("clone", args)
            self.assertTrue(ret, "vine.clone.execute() returned failure")

            contents = self.output.getvalue()
            self.stdout(contents)
            #ToDo: Finish checking contents
        finally:
            shutil.rmtree(tempDir)
