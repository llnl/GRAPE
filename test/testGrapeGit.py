import os, sys, unittest, shutil,subprocess
import testGrape
if not ".." in sys.path:
    sys.path.append( ".." )
from vine import utility
from vine import grapeGit as git


str1 = "a \n b\n c\n"
str2 = "a \n c\n c\n"
str3 = "a \n d\n c\n" 

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
        self.repo = os.path.join(os.getcwd(),"testGrapeGitRepo")


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
        super(TestGrapeGit,self).tearDown()

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

    def testShowRemote(self):
        self.assertTrue(False)

    def testCommit(self):
        
        self.assertTrue(False)

    def testCheckout(self):
        self.assertTrue(False)

    def testRebase(self):
        self.assertTrue(False)


