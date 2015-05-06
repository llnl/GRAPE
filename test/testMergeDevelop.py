import os
import sys
import testGrape
import unittest.case
if not ".." in sys.path:
    sys.path.append("..")
from vine import grapeGit as git
from vine import grapeMenu
from vine import grapeConfig
import testNestedSubproject

class TestMD(testGrape.TestGrape):

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
            ret = grapeMenu.menu().applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return false as expected for a conflict")
            # resolve the conflict
            git.checkout("--ours f2")
            git.add("f2")
            self.assertFalse(git.isWorkingDirectoryClean(), "working directory clean before attempted continution of "
                                                            "merge\n %s" % self.output.getvalue())
            git.status("--porcelain")
            ret = grapeMenu.menu().applyMenuChoice("m", ["--continue"])
            self.assertTrue(ret, "grape m --continue did not return True\n%s" % self.output.getvalue())
            self.assertTrue(git.isWorkingDirectoryClean(), "grape m --continue did not finish merge\n%s" %
                                                           self.output.getvalue())
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())

    def testConflictingMerge_MD(self):
        self.setUpConflictingMerge()
        try:
            self.assertNotEqual(git.shortSHA(), git.shortSHA("master"))
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape m did not return false as expected for a conflict")
            # resolve the conflict
            git.checkout("--ours f2")
            git.add("f2")
            self.assertFalse(git.isWorkingDirectoryClean(), "working directory clean before attempted continution of "
                                                            "merge\n %s" % self.output.getvalue())
            git.status("--porcelain")
            ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])
            self.assertTrue(ret, "grape md --continue did not return True\n%s" % self.output.getvalue())
            self.assertTrue(git.isWorkingDirectoryClean(), "grape m --continue did not finish merge\n%s" %
                                                           self.output.getvalue())
        except SystemExit:
            self.fail("Unexpected SystemExit: %s" % self.output.getvalue())

    def createTestSubmodule(self):
        # make a repo to turn into a submodule
        git.clone("--mirror %s %s " % (self.repo, self.repos[1]))
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
        subPath = os.path.join(self.repo, "submodule1")
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
        



    def testNonConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertTrue(ret, "grape md did not return true for submodule merge.")

            # the submodule should not be modified
            self.assertTrue(git.isWorkingDirectoryClean())

            # master should be merged into current branch
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge", "master"))

            # the gitlink should be at the tip of testSubmoduleMerge
            git.submodule("update")
            os.chdir(os.path.join(self.repo, "submodule1"))
            self.assertFalse(git.diff("testSubmoduleMerge"), "gitlink is not at testSubmoduleMerge tip after merge")

        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))
        except SystemExit:
            self.fail("Uncaught System Exit\n%s" % self.output.getvalue())

    def testNonConflictingSubmoduleMerge(self):
        try:
            self.setUpNonConflictingSubmoduleMerge()
            ret = grapeMenu.menu().applyMenuChoice("m", ["master", "--am"])
            self.assertTrue(ret, "grape m did not return true for submodule merge.")

            # the submodule should not be modified
            self.assertTrue(git.isWorkingDirectoryClean())

            # master should be merged into current branch
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge", "master"))

            # the gitlink should be at the tip of testSubmoduleMerge
            git.submodule("update")
            os.chdir(os.path.join(self.repo, "submodule1"))
            self.assertFalse(git.diff("testSubmoduleMerge"), "gitlink is not at testSubmoduleMerge tip after merge")

        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))
        except SystemExit:
            self.fail("Uncaught System Exit\n%s" % self.output.getvalue())
            
    def testConflictingSubmoduleMerge_MD(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            subPath = os.path.join(self.repo, "submodule1")
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am"])
            self.assertFalse(ret, "grape md did not return False for conflicting merge.")
            # should only have modifications in submodule1, not conflicts
            status = git.status("--porcelain")
            self.assertTrue("UU" not in status and "AA" in status, "unexpected status %s at toplevel" % status)
            os.chdir(subPath)
            status = git.status("--porcelain")
            self.assertTrue("AA" in status, "unexpected status %s in submodule1" % status)

            # resolve the conflict and continue from the submodule's directory
            git.checkout("--ours f1")
            git.add("f1")
            git.commit("-m \"resolved conflict with our f1\"")
            self.setUpConfig()
            ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])

            # test that we returned successfully
            self.assertTrue(ret, "grape md --continue did not complete successfully after resolving submodule conflict"
                                 "\n %s" % self.output.getvalue())

            # test that the submodule master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2", "master"),
                            "grape md --continue did not merge in submodule1`s master branch")

            # test that the outer level master was merged in
            os.chdir(self.repo)
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2", "master"),
                            "grape md --continue did not merge in the outer level master branch")

            # ensure the gitlink is at the right commit
            git.submodule("update")
            os.chdir(subPath)
            diff = git.diff("testSubmoduleMerge2")
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")

        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))
        except SystemExit:
            self.fail("Uncaught exit\n%s" % self.output.getvalue())

    def testConflictingSubmoduleMerge(self):
        try:
            self.setUpConflictingSubmoduleMerge()
            subPath = os.path.join(self.repo, "submodule1")
            ret = grapeMenu.menu().applyMenuChoice("m", ["master", "--am"])
            self.assertFalse(ret, "grape m did not return False for conflicting merge.")
            # should only have modifications in submodule1, not conflicts
            status = git.status("--porcelain")
            self.assertTrue("UU" not in status and "AA" in status, "unexpected status %s at toplevel" % status)
            os.chdir(subPath)
            status = git.status("--porcelain")
            self.assertTrue("AA" in status, "unexpected status %s in submodule1" % status)

            # resolve the conflict and continue from the submodule's directory
            git.checkout("--ours f1")
            git.add("f1")
            git.commit("-m \"resolved conflict with our f1\"")
            self.setUpConfig()
            ret = grapeMenu.menu().applyMenuChoice("m", ["--continue"])

            # test that we returned successfully
            self.assertTrue(ret, "grape m --continue did not complete successfully after resolving submodule conflict"
                                 "\n %s" % self.output.getvalue())

            # test that the submodule master was merged in
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2", "master"),
                            "grape m --continue did not merge in submodule1`s master branch")

            # test that the outer level master was merged in
            os.chdir(self.repo)
            self.assertTrue(git.branchUpToDateWith("testSubmoduleMerge2", "master"),
                            "grape m --continue did not merge in the outer level master branch")

            # ensure the gitlink is at the right commit
            git.submodule("update")
            os.chdir(subPath)
            diff = git.diff("testSubmoduleMerge2")
            self.assertFalse(diff, "checked in gitlink is not at tip of testSubmoduleMerge2")

        except git.GrapeGitError as e:
            self.fail("Uncaught git error executing %s: \n%s" % (e.gitCommand, e.gitOutput))
        except SystemExit:
            self.fail("Uncaught exit\n%s" % self.output.getvalue())

    def setUpConflictingNestedSubprojectMerge(self):
        os.chdir(self.defaultWorkingDirectory)
        testNestedSubproject.TestNestedSubproject.assertCanAddNewSubproject(self)
        os.chdir(self.subproject)
        
        # set up f1 with conflicting content on master  and testNestedMerge branches. 
        git.checkout("master")
        git.branch("testNestedMerge")
        testGrape.writeFile2("f1")
        git.add("f1")
        git.commit("-m \"added f2 as f1\"")
        git.checkout("testNestedMerge")
        testGrape.writeFile3("f1")
        git.add("f1")
        git.commit("-m \"added f1 as f1\"")
        
        os.chdir(self.repo)
        
    def testConflictingNestedSubprojectMerge(self):
        self.setUpConflictingNestedSubprojectMerge()
        os.chdir(self.repo)
        git.checkout(" -b testNestedMerge")
        
        #make sure we're not up to date with master
        os.chdir(self.subproject)
        self.assertFalse(git.branchUpToDateWith("testNestedMerge", "master"), msg=None)
        os.chdir(self.repo)
        # run grape m --am - this helps ensure m is following same code path as md. 
        try:
            ret = grapeMenu.menu().applyMenuChoice("m", ["--am", "master"], globalArgs=["-v"])
        except SystemExit as e: 
            self.assertTrue(False, "grape m raised exception %s" % e)
        self.assertFalse(ret, "grape m did not return False for conflicting merge.")
        # git status in outer repo should be clean
        status = git.status("--porcelain")
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        # git status in subproject should not be clean
        os.chdir(self.subproject)
        status = git.status("--porcelain")
        self.assertIn("AA", status, "no conflicts in subproject status \n%s " % status)
        
        # resolve the conflict
        git.checkout("--ours f1")
        git.add("f1")
        status = git.status("--porcelain")
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")
        
        # continue the merge
        ret = grapeMenu.menu().applyMenuChoice("m", ["--continue"])
        self.assertTrue(ret, "m didn't return successfully after conflict resolution")
        os.chdir(self.subproject)

        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master"))
        os.chdir(self.repo)
        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master"))

    def testConflictingNestedSubprojectMerge_MD(self):
        self.setUpConflictingNestedSubprojectMerge()
        os.chdir(self.repo)
        git.checkout(" -b testNestedMerge")
        
        #make sure we're not up to date with master
        os.chdir(self.subproject)
        self.assertFalse(git.branchUpToDateWith("testNestedMerge", "master"), msg=None)
        os.chdir(self.repo)
        # run grape md --am
        try:
            ret = grapeMenu.menu().applyMenuChoice("md", ["--am", "--public=master"], globalArgs=["-v"])
        except SystemExit as e: 
            self.assertTrue(False, "grape md raised exception %s" % e)
        self.assertFalse(ret, "grape md did not return False for conflicting merge.")
        # git status in outer repo should be clean
        status = git.status("--porcelain")
        self.assertFalse(status, "status is not empty in outer repo after conflict in subproject")
        # git status in subproject should not be clean
        os.chdir(self.subproject)
        status = git.status("--porcelain")
        self.assertIn("AA", status, "no conflicts in subproject status")
        
        # resolve the conflict
        git.checkout("--ours f1")
        git.add("f1")
        status = git.status("--porcelain")
        self.assertNotIn("AA", status, "conflict not resolved after staging f1")
        
        # continue the merge
        ret = grapeMenu.menu().applyMenuChoice("md", ["--continue"])
        self.assertTrue(ret, "md didn't return successfully after conflict resolution")
        os.chdir(self.subproject)

        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master"))
        os.chdir(self.repo)
        self.assertTrue(git.branchUpToDateWith("testNestedMerge", "master"))