import sys
import os
import inspect
import StringIO
import shutil
curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if not curPath in sys.path:
    sys.path.append(curPath)
grapePath = os.path.join(curPath, "..")
if grapePath not in sys.path:
    sys.path.append(grapePath)
from vine import grapeConfig, grapeMenu, utility
from vine import grapeGit as git
import unittest

#A grape project in a command list form that has reset capability.
#Another way to make work this would be to take a user generated reset function
#in the constructor and just apply that.  
class ResettableProject:
    def __init__(self, projectDir):
        self.projectDir = projectDir

        #cmdList is a list of 2-tuples containing (function, param) pairs
        #param itself can be a tuple or a single parameter
        #Default commands set up an empty repository 
        self.cmdList =  [(os.mkdir, self.projectDir),
                         (os.chdir, (self.projectDir,)),
                         (git.gitcmd, ("init", "Setup Failed"))]

    def addCommands(self, newCmds):
        self.cmdList.append(newCmds)

    def reset(self):
        self.tearDown()

        #Run the commands using python's 1st order reresentations of the functions and tuples
        for (cmd, param) in self.cmdList:
            if type(param) == type(()):
                cmd(*param)     #The * does the magic of unpacking the tuple and using it as the parameter list
            else:
                cmd(param)      #This allows a non-tuple type for param if the user wants it

    def tearDown(self):
        if os.path.exists(self.projectDir) and os.path.isdir(self.projectDir):
            os.chdir(os.path.abspath(os.path.join(self.projectDir,"..")))
            shutil.rmtree(self.projectDir, True)

#This takes a project and various test methods and generates a test method using
#a closure pattern.  It is part of the magic of createGridTestClass.
def generateTest(project, method, testClassSetUp, testClassTearDown):
    def test(self):
        testClassSetUp(self)
        project.reset()
        method(self)
        testClassTearDown(self)
    return test


#Beware, this is a bit of a wonky piece of metacode.  It takes a length M list of resettable projects, and 
#a length N list of tests encapsulated in what would normally be a unittest.TestCase class.  It then 
#pulls the test methods out the TestClass and generates a new GridTest class with M*N test methods in it   
def createGridTestClass(projectList, testClass, gridTestName):
    #Digest the class into pieces we can work with namely the method names and the methods pulled out of the class
    testMethodNames = [method for method in dir(testClass) if callable(getattr(testClass, method)) 
                            and not (method in ["__init__", "setUp", "tearDown"])]
    testMethods = [getattr(testClass, method).__func__ for method in testMethodNames] 

    #If the testClass has setUp and/or tearDown methods we need to grab and apply them
    if hasattr(testClass, "setUp"):
        testClassSetUp = getattr(testClass, "setUp")
    else:
        testClassSetUp = lambda self : None
    
    if hasattr(testClass, "tearDown"):
        testClassTearDown = getattr(testClass, "tearDown")
    else:
        testClassTearDown = lambda self : None

    #Now create a new class with all of the generated TestCase methods
    GridTest = type(gridTestName, (unittest.TestCase, object), {})
    for projecti in range(len(projectList)):
        project = projectList[projecti]
        for (name, method) in zip(testMethodNames, testMethods):
            test = generateTest(project, method, testClassSetUp, testClassTearDown)
            setattr(GridTest, name + str(projecti), test)

    return GridTest


class QuickGridTests:
    def testOneEqOne(self):
        self.assertEqual(1, 1)

    def testOneEqTwo(self):
        self.assertEqual(1, 2)

    def testTwoEqTwo(self):
        self.assertEqual(2, 2)

if __name__ == "__main__":
    projects = [ResettableProject("/g/g13/afisher/wcispace/test/repo1"), 
                ResettableProject("/g/g13/afisher/wcispace/test/repo2"), 
                ResettableProject("/g/g13/afisher/wcispace/test/repo3")]
    
    GridTest = createGridTestClass(projects, QuickGridTests, "myFirstGridTest")
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(GridTest))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
