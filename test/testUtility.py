import unittest
import testGrape
import sys
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility

import os
import shutil


class TestUtility(testGrape.TestGrape):
   def testGetHardLinkFromURL(self):
      os.chdir(self.repo)
      try:
         os.makedirs("hardlinktest/b/c/d/e")
         os.chdir("hardlinktest/b/c")

         #Test existing hard paths
         self.assertTrue(utility.getHardLinkFromURL("/usr/gapps/grape") == "/usr/gapps/grape")
         self.assertTrue(utility.getHardLinkFromURL("ssh://www.grape.com") == "ssh://www.grape.com")
         self.assertTrue(utility.getHardLinkFromURL("http://www.grape.com") == "http://www.grape.com")
         self.assertTrue(utility.getHardLinkFromURL("https://www.grape.com") == "https://www.grape.com")

         #Test some relative paths
         self.assertTrue(utility.getHardLinkFromURL(".").endswith("hardlinktest/b/c"))
         self.assertTrue(utility.getHardLinkFromURL("..").endswith("hardlinktest/b"))
         self.assertTrue(utility.getHardLinkFromURL("../..").endswith("hardlinktest"))
         self.assertTrue(utility.getHardLinkFromURL("../../b").endswith("hardlinktest/b"))
         self.assertTrue(utility.getHardLinkFromURL("../../b/..").endswith("hardlinktest"))
         self.assertTrue(utility.getHardLinkFromURL("../../b/../b").endswith("hardlinktest/b"))
         self.assertTrue(utility.getHardLinkFromURL("../../b/..").endswith("hardlinktest"))
         self.assertTrue(utility.getHardLinkFromURL("d").endswith("hardlinktest/b/c/d"))
         self.assertTrue(utility.getHardLinkFromURL("d/e").endswith("hardlinktest/b/c/d/e"))
      finally:
         os.chdir(self.repo)
         shutil.rmtree("hardlinktest")
