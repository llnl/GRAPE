import sys
import os
import inspect
import StringIO
import shutil
import tempfile
import types

curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if not curPath in sys.path:
    sys.path.insert(0, curPath)
grapePath = os.path.join(curPath, "..")
if grapePath not in sys.path:
    sys.path.insert(0, grapePath)
from vine import grapeConfig, grapeMenu, utility
from vine import grapeGit as git
import testGrape
import unittest


#A grape project in a command list form that has reset capability.
#Another way to make this work would be to take a user generated reset function
#in the constructor and just apply that.  
class ResettableProject(object):
    def __init__(self, projectDir):
        
        self.projectPrefix = tempfile.mkdtemp()
        self.projectDir = projectDir
        if os.path.exists(projectDir):
            print "Path (%s) already exists, so it cannot be used by a new ResettableProject." % projectDir
            sys.exit(1)

        #cmdList is a list of 2-tuples containing (function, param) pairs
        #param itself can be a tuple, a single parameter, or a single lambda function that provides arguments 
        #  to the cmd. 
        #Default commands set up an empty repository and a clone of that repository.
        self.cmdList =  [(os.mkdir, lambda : self.getOriginDir()) ,
                         (os.chdir, lambda : self.getOriginDir()) , 
                         (git.gitcmd, ("init --bare", "Setup Failed")),
                         (git.clone, lambda : "%s %s" % (self.getOriginDir(), self.getProjectDir())),
                         (os.chdir, lambda : self.getProjectDir() )]

    def getProjectDir(self): 
        return os.path.abspath(os.path.join(self.projectPrefix,self.projectDir))
    
    def getOriginDir(self): 
        return os.path.abspath(self.getProjectDir()+".origin")
    
    def cdToProjectDirCmd(self): 
        return (os.chdir, lambda : self.getProjectDir())
    
    def cdToOriginDirCmd(self):
        return (os.chdir, lambda : self.getOriginDir())

    def addCommands(self, newCmds):
        self.cmdList.extend(newCmds)

    def reset(self, projectPrefix=None):
        self.tearDown()
        if (not projectPrefix is None):
                    self.projectPrefix = projectPrefix        

        #Run the commands using python's 1st order representations of the functions and tuples
        for (cmd, param) in self.cmdList:
            try:
                # evaluate param if it's a function type
                if type(param) is types.FunctionType:
                    param = param()                
                if type(param) == types.TupleType:
                    cmd(*param)     #The * does the magic of unpacking the tuple and using it as the parameter list
                else: 
                    cmd(param)
            except git.GrapeGitError as e:
                print e.gitCommand, e.gitOutput
                raise e

    def tearDown(self):
        if os.path.exists(self.getProjectDir()) and os.path.isdir(self.getProjectDir()):
            os.chdir(os.path.abspath(os.path.join(self.getProjectDir(),"..")))
            shutil.rmtree(self.getProjectDir(), ignore_errors=True)
        originDir = self.getOriginDir()
        if os.path.exists(originDir) and os.path.isdir(originDir):
            os.chdir(os.path.abspath(os.path.join(originDir,"..")))
            shutil.rmtree(originDir, ignore_errors=True)

# This takes a project and various test methods and generates a test method using
# a closure pattern.  It is part of the magic of createGridTestClass.
def generateTest(project, method):
    def test(self):
        if project.debugging(): 
            self.switchToStdout()
        project.reset(self.defaultWorkingDirectory)
        method(self, project)
        if project.debugging(): 
            self.switchToHiddenOutput()
    return test


# Beware, this is a wonky piece of metacode.  It takes a length M list of resettable projects, and 
# a length N list of tests encapsulated in a unittest.TestCase class.  The test methods must be prefixed with
# "gridtest" instead of test.  It then generates test methods for the M*N cases in that class.
def gridifyTestClass(projectList, testClass, projectNames=None):
    #Digest the class into pieces we can work with namely the method names and the methods pulled out of the class
    testMethodNames = [method for method in dir(testClass) if callable(getattr(testClass, method)) 
                            and method.find("gridtest") == 0]
    testMethods = [getattr(testClass, method).__func__ for method in testMethodNames] 

    #Now add the N*M test methods to the class testClass
    for projecti in range(len(projectList)):
        project = projectList[projecti]
        for (name, method) in zip(testMethodNames, testMethods):
            test = generateTest(project, method)
            if projectNames is None:
                mangled_name = name[4:] + str(projecti)
            else:
                mangled_name = name[4:] + '_' + projectNames[projecti]
            setattr(testClass, mangled_name, test)
