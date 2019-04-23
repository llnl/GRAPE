#!/usr/bin/env python3
from contextlib import contextmanager
import inspect
import io
import logging
import os
import shutil
import stat
import sys
import tempfile
import unittest

# Assert tests are ran with Python 3.6 or greater.
pythonMajorVersion = sys.version_info[0]
pythonMinorVersion = sys.version_info[1]
if not pythonMajorVersion == 3 and pythonMinorVersion >= 6:
    print('Grape requires Python 3.6 or greater.')
    exit(1)
# Needed if testing GRAPE directly through CLI. (Not through GRAPE's menu).
grape_path = os.path.dirname(os.path.realpath(os.path.dirname(__file__)))
grape_par_dir = os.path.dirname(grape_path)
if grape_par_dir not in sys.path:
    sys.path.insert(0, grape_par_dir)

from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine import config_parser_global
from grape.vine import grapeMenu
from grape.vine import utility
from grape.vine.option import Option

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

# object to allow splitting of output to multiple file-like objects.
# from user shx2: https://stackoverflow.com/questions/616645/how-to-duplicate-sys-stdout-to-a-log-file
class Multifile(object):
    def __init__(self, files):
        self._files = files
    def __getattr__(self, attr, *args):
        return self._wrap(attr, *args)
    def _wrap(self, attr, *args):
        def g(*a, **kw):
            for f in self._files:
                res = getattr(f, attr, *args)(*a, **kw)
            return res
        return g

class TestGrape(unittest.TestCase):
    """
    TODO: output from multiple tests seem to be overlapping.
    Tests inheriting from "TestGrape" are not 100% separated. A simple test
    ran by itself can produce zero output to stdout and asserting stdout is
    empty would succeed. This same test combined with the entire GRAPE suite
    of tests will encounter a non-empty stdout, and fail.
    """

    def switchToStdout(self):
        sys.stdout = Multifile([sys.stdout, self.stdout])
        sys.stderr = Multifile([sys.stderr, self.stderr])

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
        config = config_parser_global.grapeConfig()
        config.set(Option.SECTION_FLOW, "publicBranches", "master")
        config.set(Option.SECTION_FLOW, "topicPrefixMappings", "?:master")
        config.set(Option.SECTION_WORKSPACE, "submoduleTopicPrefixMappings", "?:master")

    def setUp(self):
        # setUp stdout and stderr wrapping to capture
        # messages from the modules that we test
        self.output = io.StringIO()
        self.error = io.StringIO()
        self.stdout = sys.stdout
        self.stderr = sys.stderr
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
        except grape_errors.GrapeGitError:
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

        # restore stdout and stderr to their original streams
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        os.chdir(self.cwd)
        self.output.close()
        self.error.close()

        # reset grapeConfig and grapeMenu
        config_parser_global.resetGrapeConfig()
        grapeMenu._resetMenu()

#    # print the captured standard out
#    def printOutput(self):
#        for l in self.output:
#            self.stdout.write(l)
#
#    # print the captured standard error
#    def printError(self):
#        for l in self.error:
#            self.stderr.write(l)

    def get_output(self):
        return self.output.getvalue()

    @contextmanager
    def queue_user_input(self, user_input_list):
        """
        Temporarily replaces sys.stdin with a text stream holding user input.
        """
        original_stdin = sys.stdin
        input_stream = io.StringIO()
        sys.stdin = input_stream
        input_stream.writelines(user_input_list)
        input_stream.seek(0)
        try:
            yield
        finally:
            input_stream.close()
            sys.stdin = original_stdin

    def assertTrue(self, expr, msg=None):
        if msg is not None:
            msg += "\n" + f"{self.get_output()}"
        super(TestGrape, self).assertTrue(expr, msg=msg)

    def assertFalse(self, expr, msg=None):
        if msg is not None:
            msg += "\n" + f"{self.get_output()}"
        super(TestGrape, self).assertFalse(expr, msg=msg)


def buildSuite(cls, appendTo=None, sub=None):
    suite = appendTo
    if suite is None:
        suite = unittest.TestSuite()
    if sub:
       suite.addTest(cls(sub))
    else:
       suite.addTest(unittest.makeSuite(cls))
    return suite


def main(argv, debug=False):

    from grape.test import testBranches
    from grape.test import testBundle
    from grape.test import testClone
    from grape.test import testConfig
    from grape.test import testDeleteBranch
    from grape.test import testMergeDevelop
    from grape.test import testGrapeGit
    from grape.test import testResolveConflicts
    from grape.test import testReview
    from grape.test import testStash
    from grape.test import testUnbundle
    from grape.test import testVersion
    from grape.test import testPublish
    from grape.test import testCO
    from grape.test import testNestedSubproject
    from grape.test import testStatus
    from grape.test import testUpdateLocal

    testClasses = {"Branches":testBranches.TestBranches,
                   "Bundle":testBundle.TestBundle,
                   "Clone":testClone.TestClone,
                   "Config":testConfig.TestConfig,
                   "DeleteBranch":testDeleteBranch.TestDeleteBranch,
                   "GrapeGit":testGrapeGit.TestGrapeGit,
                   "MergeDevelop":testMergeDevelop.TestMD,
                   "ResolveConflicts":testResolveConflicts.TestResolveConflicts,
                   "Review":testReview.TestReview,
                   "Stash":testStash.TestStash,
                   "Unbundle":testUnbundle.TestUnbundle,
                   "Version":testVersion.TestVersion,
                   "Publish":testPublish.TestPublish,
                   "CO":testCO.TestCheckout,
                   "NestedSubproject":testNestedSubproject.TestNestedSubproject,
                   "Status":testStatus.createStatusTester(),
                   "GrapeUp":testUpdateLocal.createUpTester()}


    suite = unittest.TestSuite()
    if len(argv) == 0: 
        for cls in testClasses.values():
            suite = buildSuite(cls, suite)
    else:
        if argv[0] == "listSuites":
            print(testClasses.keys())
            exit(0)
        nl = "\n"
        for arg in argv:
            if '.' in arg:
               (cls, sub) = arg.split('.')
               try:
                  cls = testClasses[cls]
               except:
                  print(f"*** {cls} is not a valid test suite!{nl}" + \
                        f"Valid values are:{nl}{testClasses.keys()}")
                  exit(0)
            else:
               try:
                  cls = testClasses[arg]
               except:
                  print(f"*** {arg} is not a valid test suite!{nl}" + \
                        f"Valid values are:{nl}{testClasses.keys()}")
                  exit(0)
               sub = None
            suite = buildSuite(cls, suite, sub)

    if debug:
        for cls in suite:
            try:
               for case in cls:
                   print(case)
                   case._debug = True
            except TypeError:
               print(cls)
               cls._debug = True
        suite._tests    
    
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main(sys.argv[1:], debug=False)
