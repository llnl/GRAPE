#!/usr/bin/env python

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

def printStr(str):
    print str


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



def createGridTestClass(projectList, testClass, gridTestName):
    #Digest the class into pieces we can work with
    testMethodNames = [method for method in dir(testClass) if callable(getattr(testClass, method)) 
                            and not (method in ["__init__", "setUp", "tearDown"])]  #Extract the test methods out of the class
    testMethods = [getattr(testClass, method) for method in testMethodNames] 

    if hasattr(testClass, "setUp"):
        testClassSetUp = getattr(testClass, "setUp")
    else:
        testClassSetUp = lambda : None
    
    if hasattr(testClass, "tearDown"):
        testClassTearDown = getattr(testClass, "tearDown")
    else:
        testClassTearDown = lambda : None

    #Now create a dict with all of the generated TestCase methods
    grid_class_dict = {}
    for projecti in range(len(projectList)):
        project = projectList[projecti]
        for (name, method) in zip(testMethodNames, testMethods):
            def dummy(self):
                testClassSetUp()
                project.reset()
                method()
                testClassTearDown()
            grid_class_dict[name + str(projecti)] = dummy

    #Create and return the GridTest class
    GridTest = type(gridTestName, (unittest.TestCase, object), grid_class_dict)
    return GridTest


class QuickGridTests:
    def oneEqOne(self):
        self.assertEqual(1, 1)

    def oneEqTwo(self):
        self.assertEqual(1, 2)

    def twoEqTwo(self):
        self.assertEqual(2, 2)


def main():
    #tests = QuickTests()
    projects = [ResettableProject("/g/g13/afisher/wcispace/test/repo1"), 
                ResettableProject("/g/g13/afisher/wcispace/test/repo2"), 
                ResettableProject("/g/g13/afisher/wcispace/test/repo3")]
    
    GridTest = createGridTestClass(projects, QuickGridTests, "myFirstGridTest")
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(GridTest))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print GridTest().oneEqTwo1()


if __name__ == "__main__":
    main()