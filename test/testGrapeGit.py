import os, sys, unittest, shutil,subprocess
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from vine import grapeGit as git


str1 = "str1 \n a \n b\n c\n"
str2 = "str2 \n a \n c\n c\n"
str3 = "str3 \n a \n d\n c\n"

def writeFile1(path):
    with open(path,'w') as f:
        f.write(str1)

def writeFile2(path):
    with open(path,'w') as f:
        f.write(str2)

def writeFile3(path):
    with open(path,'w') as f:
        f.write(str3)

class TestGrapeGit(testGrape.TestGrape):
    def __init__(self,superArg):
        super(TestGrapeGit,self).__init__(superArg)
        self.repos = [os.path.join(os.getcwd(),"testGrapeGitRepo"),os.path.join(os.getcwd(),"testGrapeGitRepo2")]
        self.repo = self.repos[0]
        
    def setUp(self):
        super(TestGrapeGit,self).setUp()
        try:
            os.mkdir(self.repo)
            os.chdir(self.repo)
            utility.executeSubProcess("git init",os.getcwd(), subprocess.PIPE)
            fname = os.path.join(self.repo,"testRepoFile")
            writeFile1(fname)
            utility.executeSubProcess("git add %s" % fname,os.getcwd(), subprocess.PIPE)
            utility.executeSubProcess("git commit -m 'initial commit'",os.getcwd(), subprocess.PIPE)
            os.chdir(os.path.join(self.repo,".."))
        except:
            pass

    def tearDown(self):
        os.chdir(os.path.join(self.repo,".."))
        shutil.rmtree(self.repo)
        for repo in self.repos:
            try:
                shutil.rmtree(repo)
            except:
                pass

        super(TestGrapeGit,self).tearDown()


    def testAdd(self):
        try:
            os.chdir(self.repo)
            f1name = os.path.join(self.repo,"f1")
            writeFile1(f1name)
            git.add("f1")
            git.status()
        except git.GrapeGitError as error:
            self.handleGitError(error)

        self.assertTrue("new file:   f1" in self.output.getvalue())
                

    def testCommit(self):
       try:
          os.chdir(self.repo)
          f1name = os.path.join(self.repo,"f1")
          writeFile1(f1name)
          commitStr = "testCommit: added f1"
          git.add("f1")
          git.commit("f1 -m '%s'" % commitStr)
          log = git.log() 
          self.assertTrue(commitStr in log)
       except git.GrapeGitError as error:
          self.handleGitError(error)


    def testCheckout(self):
        try: 
           os.chdir(self.repo)
           git.checkout("-b testCheckout/tmpBranch")
           self.assertTrue(git.currentBranch() == "testCheckout/tmpBranch","checkout of new branch failed")
	   git.checkout("master")
	   self.assertTrue(git.currentBranch() == "master","switching to master did not work")
	   
        except git.GrapeGitError as error:
           self.handleGitError(error)

           

    def testDir(self):
        grapeBaseDir = os.getcwd()
        if not os.path.exists(os.path.join(grapeBaseDir, "grape")):
            grapeBaseDir = os.path.abspath(os.path.join(os.getcwd(), ".."))
        self.assertTrue(os.path.exists(os.path.join(grapeBaseDir, "grape")), "Something went horribly wrong and could not find the base directory of the grape repo")


        self.assertEquals(git.dir(), grapeBaseDir, "Could not determine git directory")


    def testMerge(self):
        # First, test to see if a merge that should work does.
        try:
          os.chdir(self.repo)
          #add a file on the master branch.
          f1name = os.path.join(self.repo, "f1")
          writeFile1(f1name)
          git.add("f1")
          commitStr = "testMerge: added f1"
          git.commit(" -m '%s'" % commitStr)
          # edit it on branch testMerge/tmp1
          git.checkout("-b testMerge/tmp1")
          writeFile2(f1name)
          git.commit("-a -m 'edited f1'")
          # perform same editon master
          git.checkout("master")
          writeFile2(f1name)
          git.commit("-a -m 'edited f1 on master'")
          # switch back to tmp, merge changes from master down
          git.checkout("testMerge/tmp1")
	  output = git.merge("master -m 'merged identical change from master'")
          log = git.log()
          self.assertTrue("identical change from master" in log) 
        except git.GrapeGitError as error:
          self.handleGitError(error)

        # Second, test that a merge that should result in a conflict throws an appropriate GrapeGitError exception. 
        try:
          git.checkout("master")
          f2name = os.path.join(self.repo,"f2")
          writeFile3(f2name)
          git.add(f2name)
          git.commit("-m 'added f2'")
          git.checkout("testMerge/tmp1")
          writeFile2(f2name)
          git.add(f2name)
          git.commit("-m 'added f2 in tmp branch'")
          git.merge("master -m 'merged master branch into testmerge/tmp1'")
          self.assertTrue(False,"Merge did not throw grapeGitError for conflict")
        except git.GrapeGitError as error:
          status = git.status()
          self.assertTrue("conflict" in status, "'conflict' not in status message %s" % status) 

    def testMergeAbort(self):
         try:
           os.chdir(self.repo)
           git.branch("testMergeAbort/tmp1 HEAD")
           #add a file on the master branch.
           f1name = os.path.join(self.repo, "f1")
           writeFile1(f1name)
           git.add("f1")
           commitStr = "testMergeAbort: added f1"
           git.commit(" -m '%s'" % commitStr)
           # also add it on the tmp branch
           git.checkout("testMergeAbort/tmp1")
           writeFile2(f1name)
           git.add("f1")
           git.commit(" -m 'testMergeAbort/tmp1 : added f1'")
           # a merge should generate a conflict
           git.merge("master -m 'merging from master'")
           self.assertTrue(False,"conflict did not throw exception")
         except:
           status = git.status()
           self.assertTrue("conflict" in status, "'conflict' not in status message %s " % status)
           git.mergeAbort()
           status = git.status()
           self.assertFalse("conflict" in status, "conflict not removed by aborting merge")


    def testFetch(self):
        try:
          git.clone("%s %s" %(self.repo,self.repos[1]))
          os.chdir(self.repo)
          f1name = os.path.join(self.repo,"f1")
          writeFile1(f1name)
          git.add("f1")
          commitStr = "testFetch: added f1"
          git.commit(" -m '%s'" % commitStr)
	  os.chdir(self.repos[1])
          log = git.log("--all")
          self.assertFalse(commitStr in log,"commit message in log before it should be")
          git.fetch("origin")
 	  log = git.log("--all")
          self.assertTrue(commitStr in log, "commit message not in log --all affter fetch")

	except git.GrapeGitError as error: 
           self.handleGitError(error)

    def testPull(self):
        try:
          git.clone("%s %s" %(self.repo,self.repos[1]))
          os.chdir(self.repo)
          f1name = os.path.join(self.repo,"f1")
          writeFile1(f1name)
          git.add("f1")
          commitStr = "testPull: added f1"
          git.commit(" -m '%s'" % commitStr)
	  os.chdir(self.repos[1])
          log = git.log("--all")
          self.assertFalse(commitStr in log,"commit message in log before it should be")
          git.pull("origin master")
 	  log = git.log()
          self.assertTrue(commitStr in log, "commit message not in log  affter pull")

        except git.GrapeGitError as error: 
          self.handleGitError(error)

    def testPush(self):
        try:
          os.chdir(self.repo)
          f2name = os.path.join(self.repo, "f2")
          writeFile2(f2name)
          git.add(f2name)
          git.commit(" -m 'initial commit for testPush'")
          git.clone("%s %s" %(self.repo,self.repos[1]))
          git.checkout("-b testPush/tmpBranchToAllowPushesToMaster")
          os.chdir(self.repos[1])
          f1name = os.path.join(self.repos[1],"f1")
          writeFile1(f1name)
          git.add("f1")
          commitStr = "testPush: added f1"
          git.commit(" -m '%s'" % commitStr)
          os.chdir(self.repo)
          log = git.log("--all")
          self.assertFalse(commitStr in log,"commit message in log before it should be")
          os.chdir(self.repos[1])
          pushOutput = git.push("origin master")
          os.chdir(self.repo)
 	  git.checkout("master")
          log = git.log()
          self.assertTrue(commitStr in log, "commit message not in log  affter push")

	except git.GrapeGitError as error: 
          self.handleGitError(error)

    def testBranch(self):
        local = self.repo 
        try:
           os.chdir(local) 
           git.branch("testBranch/newBranch HEAD")
           branches = git.branch()
           self.assertTrue("testBranch/newBranch" in branches, "new branch not in returned string")
           self.assertTrue("testBranch/newBranch" in self.output.getvalue(), "new branch not output")
	except git.GrapeGitError as error: 
           self.handleGitError(error)



    def testCloneAndShowRemote(self):
        localSource = self.repo
        localClone = self.repos[1]
        try: 
            self.assertTrue(git.clone("%s %s" % (localSource,localClone) ))
            os.chdir(localClone)
            self.assertTrue(git.showRemote())
            contents = self.output.getvalue()
        except git.GrapeGitError as error:
            self.handleGitError(error)
        fetchLine = "Fetch URL: %s" % localSource
        
        self.assertTrue(fetchLine in contents,"coud not find %s in output" % fetchLine)
            



    def testRebase(self):
        try:
            os.chdir(self.repo)
        except:
            pass
        self.assertTrue(False)


    def handleGitError(self,error):
        self.assertTrue(False,"When executing \n%s\nError %d caught: %s \n %s " % (error.gitCommand,error.code,error.msg,error.gitOutput))
