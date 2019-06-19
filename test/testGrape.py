#!/usr/bin/env python
from contextlib import contextmanager
import logging
import sys
import os
import inspect
import unittest
import StringIO
import shutil
import tempfile

curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if curPath not in sys.path:
    sys.path.insert(0, curPath)
grapePath = os.path.join(curPath, os.path.pardir)
if grapePath not in sys.path:
    sys.path.insert(0, grapePath)
from vine import grape_errors
from vine import grapeGit as git
from vine import config_parser_global
from vine import grapeMenu
from vine import utility
from vine import vine_logging
from vine.option import Option

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

    def __init__(self, superArg):
        super(TestGrape, self).__init__(superArg)
        # 'realpath' resolves issues caused by symlinks and path assumptions.
        self.defaultWorkingDirectory = os.path.realpath(tempfile.mkdtemp())

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

    def setUpLogging(self):
        logger = vine_logging.GrapeLogger()
        logger.add_logger(__name__)
        if self._debug:
            self.tmp_log_file = os.path.join(os.getcwd(),
                                             self._testMethodName + '.log')
            logger.add_stdout_handler(__name__)
            logger.add_stderr_handler(__name__)
        else:
            logger.redirect_sys_stdout()
            self.tmp_log_file = os.path.join(
                self.defaultWorkingDirectory, self._testMethodName + '.log')
        logger.add_file_handler_to_root(self.tmp_log_file)

    def setUp(self):
        # setUp stdout and stderr wrapping to capture
        # messages from the modules that we test
        self.setUpLogging()
        self.cwd = os.getcwd()

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
        os.chdir(os.path.abspath(os.path.join(self.defaultWorkingDirectory,"..")))
        shutil.rmtree(self.defaultWorkingDirectory, False, onError)

        # restore stdout and stderr to their original streams
        os.chdir(self.cwd)

        # reset grapeConfig and grapeMenu
        config_parser_global.resetGrapeConfig()
        grapeMenu._resetMenu()
        vine_logging.GrapeLogger.restore_sys_stdout()
        if not self._debug and os.path.isfile(self.tmp_log_file):
            os.remove(self.tmp_log_file)

    def get_output(self):
        output = ''
        if os.path.isfile(self.tmp_log_file):
            with open(self.tmp_log_file) as log_file:
                output = log_file.read()
        return output

    @contextmanager
    def queue_user_input(self, user_input_list):
        """
        Temporarily replaces sys.stdin with a text stream holding user input.
        """
        original_stdin = sys.stdin
        input_stream = StringIO.StringIO()
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
            msg += "\n%s" % self.get_output()
        super(TestGrape, self).assertTrue(expr, msg=msg)

    def assertFalse(self, expr, msg=None):
        if msg is not None:
            msg += "\n%s" % self.get_output()
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
   
    import testBranches
    import testBundle
    import testClone
    import testConfig
    import testDeleteBranch
    import testMergeDevelop
    import testGrapeGit
    import testResolveConflicts
    import testReview
    import testStash
    import testUnbundle
    import testVersion
    import testPublish
    import testCO
    import testNestedSubproject
    import testStatus
    import testUpdateLocal

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
            print testClasses.keys()
            exit(0)
        for arg in argv:
            if '.' in arg:
               (cls, sub) = arg.split('.')
               try:
                  cls = testClasses[cls]
               except:
                  print "*** %s is not a valid test suite!\nValid values are:" % cls
                  print testClasses.keys()
                  exit(0)
            else:
               try:
                  cls = testClasses[arg]
               except:
                  print "*** %s is not a valid test suite!\nValid values are:" % arg
                  print testClasses.keys()
                  exit(0)
               sub = None
            suite = buildSuite(cls, suite, sub)
            
    if debug:
        for cls in suite:
            try:
               for case in cls:
                   print case
                   case._debug = True
            except TypeError:
               print cls
               cls._debug = True
        suite._tests    
    
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    main(sys.argv[1:], debug=False)
