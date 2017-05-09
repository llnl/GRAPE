#!/usr/bin/env python

import sys
import os
import inspect
import unittest
import StringIO
import shutil
import tempfile

curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if not curPath in sys.path:
    sys.path.insert(0, curPath)
grapePath = os.path.join(curPath, "..")
if grapePath not in sys.path:
    sys.path.insert(0, grapePath)
from vine import grapeGit as git
from vine import grapeConfig
from vine import grapeMenu

str1 = "str1 \n a \n b\n c\n"
str2 = "str2 \n a \n c\n c\n"
str3 = "str3 \n a \n d\n c\n"


def writeFile1(path):
    with open(path, 'w') as f:
        f.write(str1)


def writeFile2(path):
    with open(path, 'w') as f:
        f.write(str2)


def writeFile3(path):
    with open(path, 'w') as f:
        f.write(str3)


class TestGrape(unittest.TestCase):
    def printToScreen(self, str): 
        self.stdout.write(str)
        
    def switchToStdout(self):
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        
    def switchToHiddenOutput(self):
        sys.stdout = self.output
        sys.stderr = self.error
        
    def __init__(self, superArg):
        super(TestGrape, self).__init__(superArg)
        self.defaultWorkingDirectory = tempfile.mkdtemp()

        self.repos = [os.path.join(self.defaultWorkingDirectory, "testRepo"),
                      os.path.join(self.defaultWorkingDirectory, "testRepo2")]
        self.repo = self.repos[0]
        self._debug = False

    def setUpConfig(self):
        grapeMenu._resetMenu()
        grapeMenu.menu()
        config = grapeConfig.grapeConfig()
        config.set("flow", "publicBranches", "master")
        config.set("flow", "topicPrefixMappings", "?:master")
        config.set("workspace", "submoduleTopicPrefixMappings", "?:master")

    def setUp(self):
        # setUp stdout and stderr wrapping to capture
        # messages from the modules that we test
        self.output = StringIO.StringIO()
        self.error = StringIO.StringIO()
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.stdin = sys.stdin
        self.cwd = os.getcwd()
        sys.stdout = self.output
        sys.stderr = self.error

        # create a test repository to operate in.
        try:
            try:
                os.mkdir(self.repo + "-origin")
            except OSError:
                pass

            os.chdir(self.repo + "-origin")
            cwd = os.getcwd()
            git.gitcmd("init --bare", "Setup Failed")
            os.chdir(os.path.join(self.repo+"-origin",".."))
            git.gitcmd("clone %s %s" % (self.repo +"-origin",self.repo), "could not clone test bare repo")
            os.chdir(self.repo)
            fname = os.path.join(self.repo, "testRepoFile")
            writeFile1(fname)
            self.file1 = fname
            git.gitcmd("add %s" % fname, "Add Failed")
            git.gitcmd("commit -m \"initial commit\"", "Commit Failed")
            git.gitcmd("push origin master", "push to master failed")
            # create a develop branch in addition to master by default
            git.branch("develop")
            git.push("origin develop")
            os.chdir(os.path.join(self.repo, ".."))
        except git.GrapeGitError:
            pass
        
        self.menu = grapeMenu.menu()
        
        if self._debug:
            self.switchToStdout()

    def tearDown(self):
        def onError(func, path, exc_info):
            """
            Error handler for ``shutil.rmtree``, primarily for Windows.

            If the error is due to an access error (read only file)
            it attempts to add write permission and then retries.

            If the error is for another reason it re-raises the error.

            Usage : ``shutil.rmtree(path, onerror=onerror)``
            """
            import stat
            if not os.access(path, os.W_OK):
                # Is the error an access error ?
                os.chmod(path, stat.S_IWUSR)
                func(path)
            else:
                raise Exception
        if self._debug:
            self.switchToHiddenOutput()
        os.chdir(os.path.abspath(os.path.join(self.defaultWorkingDirectory,"..")))
        shutil.rmtree(self.defaultWorkingDirectory, False, onError)

        # restore stdout, stdin, and stderr to their original streams
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        sys.stdin = self.stdin
        os.chdir(self.cwd)
        self.output.close()

        # reset grapeConfig and grapeMenu
        grapeConfig.resetGrapeConfig()
        grapeMenu._resetMenu()

    # print the captured standard out
    def printOutput(self):
        for l in self.output:
            self.stdout.write(l)

    # print the captured standard error
    def printError(self):
        for l in self.error:
            self.stderr.write(l)

    # stage user input for methods that expect it
    def queueUserInput(self, inputList):
        self.input = StringIO.StringIO()
        sys.stdin = self.input
        self.input.writelines(inputList)
        self.input.seek(0)

    def assertTrue(self, expr, msg=None):
        if msg is not None:
            msg += "\n%s" % self.output.getvalue()
        super(TestGrape, self).assertTrue(expr, msg=msg)

    def assertFalse(self, expr, msg=None):
        if msg is not None:
            msg += "\n%s" % self.output.getvalue()
        super(TestGrape, self).assertFalse(expr, msg=msg)


def buildSuite(cls, appendTo=None):
    suite = appendTo
    if suite is None:
        suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(cls))
    return suite


def main(argv, debug=False):
   
    import testBranches
    import testClone
    import testConfig
    import testMergeDevelop
    import testGrapeGit
    import testReview
    import testVersion
    import testPublish
    import testCO
    import testNestedSubproject
    import testStatus
    import testUpdateLocal
    import testUtility

    testClasses = {"Branches":testBranches.TestBranches,
                   "Clone":testClone.TestClone,
                   "Config":testConfig.TestConfig,
                   "GrapeGit":testGrapeGit.TestGrapeGit,
                   "MergeDevelop":testMergeDevelop.TestMD,
                   "Review":testReview.TestReview,
                   "Version":testVersion.TestVersion,
                   "Publish":testPublish.TestPublish,
                   "CO":testCO.TestCheckout,
                   "NestedSubproject":testNestedSubproject.TestNestedSubproject, 
                   "Status":testStatus.createStatusTester(),
                   "GrapeUp":testUpdateLocal.createUpTester(),
                   "Utility":testUtility.TestUtility }



    suite = unittest.TestSuite()
    if len(argv) == 0: 
        for cls in testClasses.values():
            suite = buildSuite(cls, suite)
    else:
        if argv[0] == "listSuites":
            print testClasses.keys()
            exit(0)
        for cls in  [testClasses[arg] for arg in argv]:
            suite = buildSuite(cls, suite)
            
    if debug:
        for cls in suite:
            for case in cls:
                print case
                case._debug = True
        suite._tests    
    
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main(sys.argv[1:], debug=False)
