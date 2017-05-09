import unittest
import testGrape
import sys
if not ".." in sys.path:
    sys.path.insert(0, "..")
from vine import utility
from vine import grapeGit as git

import os
import shutil


class TestUtility(testGrape.TestGrape):
   def testParseSubprojectRemoteURL(self):
      os.chdir(self.repo)
      try:
         os.makedirs("hardlinktest/b/c/d/e")
         os.chdir("hardlinktest/b/c")

         #Set the remote origin url to the cwd for testing purposes
         git.config("--add remote.origin.url %s" % os.getcwd())

         #Test existing hard paths
         self.assertTrue(utility.parseSubprojectRemoteURL("/usr/gapps/grape") == "/usr/gapps/grape")
         self.assertTrue(utility.parseSubprojectRemoteURL("ssh://www.grape.com") == "ssh://www.grape.com")
         self.assertTrue(utility.parseSubprojectRemoteURL("https://www.grape.com") == "https://www.grape.com")

         #Test some relative paths
         self.assertTrue(utility.parseSubprojectRemoteURL(".").endswith("hardlinktest/b/c"))
         self.assertTrue(utility.parseSubprojectRemoteURL("..").endswith("hardlinktest/b"))
         self.assertTrue(utility.parseSubprojectRemoteURL("../..").endswith("hardlinktest"))
         self.assertTrue(utility.parseSubprojectRemoteURL("../../b").endswith("hardlinktest/b"))
         self.assertTrue(utility.parseSubprojectRemoteURL("../../b/..").endswith("hardlinktest"))
         self.assertTrue(utility.parseSubprojectRemoteURL("../../b/../b").endswith("hardlinktest/b"))
         self.assertTrue(utility.parseSubprojectRemoteURL("../../b/..").endswith("hardlinktest"))
         self.assertTrue(utility.parseSubprojectRemoteURL("d").endswith("hardlinktest/b/c/d"))
         self.assertTrue(utility.parseSubprojectRemoteURL("d/e").endswith("hardlinktest/b/c/d/e"))
      finally:
         os.chdir(self.repo)
         shutil.rmtree("hardlinktest")
