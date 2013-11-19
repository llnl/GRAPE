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
        self.assertTrue(False)

    def testCheckout(self):
        self.assertTrue(False)

    def testDir(self):
        grapeBaseDir = os.getcwd()
        if not os.path.exists(os.path.join(grapeBaseDir, "grape")):
            grapeBaseDir = os.path.abspath(os.path.join(os.getcwd(), ".."))
        self.assertTrue(os.path.exists(os.path.join(grapeBaseDir, "grape")), "Something went horribly wrong and could not find the base directory of the grape repo")


        self.assertEquals(git.dir(), grapeBaseDir, "Could not determine git directory")

    def testMergeAbort(self):
        self.assertTrue(False)

    def testMerge(self):
        self.assertTrue(False)

    def testFetch(self):
        self.assertTrue(False)

    def testPull(self):
        self.assertTrue(False)

    def testPush(self):
        self.assertTrue(False)

    def testBranch(self):
        self.assertTrue(False)

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
        self.assertTrue(False,"Error %d caught: %s \n %s " % (error.code,error.msg,error.gitOutput))
