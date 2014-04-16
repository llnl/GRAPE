import os, sys, StringIO, unittest
import testGrape
if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeGit as git
from vine import grapeMenu
from vine import grapeConfig

class TestMD(testGrape.TestGrape):
    def setUpConfig(self):
        grapeMenu._resetMenu()
        grapeMenu.menu()
        config = grapeConfig.grapeConfig()
        config.set("flow", "publicBranches", "master")
        config.set("flow", "topicPrefixMappings", "?:master")

    # sets up a new change on the master branch one commit ahead of
    # testMerge and checks out testMerge.
    def setUpMerge(self):
        os.chdir(self.repo)
        # create a new branch
        git.branch("testMerge")
        # add f2 to master
        testGrape.writeFile2("f2")
        git.add("f2")
        git.commit("-m \"f2\"")
        git.checkout("testMerge")
        self.setUpConfig()

    def setUpConflictingMerge(self):
        self.setUpMerge()
        # add a conflicting commit
        testGrape.writeFile3("f2")
        git.add("f2")
        git.commit("-m \"f2\"")




    def testNonConflictingMerge(self):
        self.setUpMerge()
        # now run grape md, should be a fast forward merge
        try:
            self.assertNotEqual(git.shortSHA(), git.shortSHA("master"))
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return True")
            contents = self.output.getvalue()
            self.assertEqual(git.shortSHA(), git.shortSHA("master"), "merging master into test branch did not fast"
                                                                    "forward")
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())
        except git.GrapeGitError as e:
            self.fail("Unhandled GrapeGitError: %s\n%s" % (e.gitCommand, e.gitOutput))

    def testConflictingMerge(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(git.shortSHA(), git.shortSHA("master"))
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return false as expected for a conflict")
            # resolve the conflict
            git.checkout("--ours f2")
            git.add("f2")
            self.assertFalse(git.isWorkingDirectoryClean(), "working directory clean before attempted continution of "
                                                            "merge\n %s" %self.output.getvalue())
            git.status("--porcelain")
            ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, "grape md --continue did not return True\n%s" % self.output.getvalue())
            self.assertTrue(git.isWorkingDirectoryClean(), "grape md --continue did not finish merge\n%s" %
                                                           self.output.getvalue())
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())



    def createTestSubmodule(self):
        # make a repo to turn into a submodule
        git.clone("%s %s " % (self.repo,self.repos[1]))
        # add repo2 as a submodule to repo1
        os.chdir(self.repo)
        git.submodule("add %s %s" % (os.path.join(self.repos[1]), "submodule1"))
        git.commit("-m \"added submodule1\"")

    def setUpNonConflictingSubmoduleMerge(self):
        os.chdir(self.defaultWorkingDirectory)
        self.createTestSubmodule()
        git.branch("testSubmoduleMerge")
        # create a new commit in submodule1
        os.chdir(os.path.join(self.repo, "submodule1"))
        git.checkout("master")
        testGrape.writeFile2("f1")
        git.add("f1")
        git.commit("-m \"added f2 as f1\"")
        # update outer level with new commit
        os.chdir(self.repo)
        git.commit("submodule1 -m \"updated submodule gitlink on master branch\"")

        # setup what should be a notionally-conflict free merge
        # (grape needs to deal with the gitlink conflicts automatically)
        git.checkout("testSubmoduleMerge")
        git.submodule("update")
        os.chdir(os.path.join(self.repo, "submodule1"))
        git.checkout("-b testSubmoduleMerge")
        testGrape.writeFile3("f2")
        git.add("f2")
        git.commit("-m \"added f3 as f2\"")
        os.chdir(self.repo)
        git.commit("-a -m \"updated gitlink on branch testSubmoduleMerge\"")
        self.setUpConfig()

    def setUpConflictingSubmoduleMerge(self):
        os.chdir(self.defaultWorkingDirectory)
        self.createTestSubmodule()
        git.branch("testSubmoduleMerge2")
        subPath = os.path.join(self.repo,"submodule1")
        os.chdir(subPath)
        git.branch("testSubmoduleMerge2")
        git.checkout("master")
        testGrape.writeFile2("f1")
        git.add("f1")
        git.commit("-m \"added f2 as f1\"")
        os.chdir(self.repo)
        git.commit("submodule1 -m \"updated submodule gitlink on master branch\"")
        git.checkout("testSubmoduleMerge2")
        git.submodule("update")
        os.chdir(subPath)
        git.checkout("testSubmoduleMerge2")
        testGrape.writeFile3("f1")
        git.add("f1")
        git.commit("-m \"added f3 as f1\"")
        os.chdir(self.repo)
        git.commit("submodule1 -m \"updated submodule gitlink on testSubmoduleMerge branch\"")
        self.setUpConfig()


    def testNonConflictingSubmoduleMerge(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return true for submodule merge.")
            # the submodule should not be modified
            self.assertTrue(git.isWorkingDirectoryClean())

        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))

    def testConflictingSubmoduleMerge(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return False for conflicting merge.")
            # should only have modifications in submodule1, not conflicts
            status = git.status("--porcelain")
            self.assertTrue("UU" not in status and "M" in status, "unexpected status %s at toplevel" % status)
            os.chdir(os.path.join(self.repo, "submodule1"))
            status = git.status("--porcelain")
            self.assertTrue("AA" in status, "unexpected status %s in submodule1" %status)
            git.checkout("--ours f1")
            git.add("f1")
            git.commit("-m \"resolved conflict with our f1\"")
            ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, "grape md --continue did not complete successfully after resolving submodule conflict")
        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))


