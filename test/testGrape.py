#!/usr/bin/env python3
from contextlib import contextmanager
import io
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
        self.menu = grapeMenu.menu(workspace_dir=self.defaultWorkingDirectory)
        self.menu.set_command_path(self.defaultWorkingDirectory)
        self._debug = False
        self.logger = vine_logging.GrapeLogger()

    def setUpConfig(self):
        grapeMenu._resetMenu()
        self.menu = grapeMenu.menu(workspace_dir=self.defaultWorkingDirectory)
        config = config_parser_global.grapeConfig()
        self.menu.set_command_path(self.defaultWorkingDirectory)
        try:
            # Git user name required for publish tests.
            config.ensureSection('user')
            config.get('--get user.name')
        except:
            config.set('user', 'name', 'TEST USER')
        config.set(Option.SECTION_FLOW, "publicBranches", "master")
        config.set(Option.SECTION_FLOW, "topicPrefixMappings", "?:master")
        config.set(Option.SECTION_WORKSPACE, "submoduleTopicPrefixMappings", "?:master")

    def setUpLogging(self):
        if self._debug:
            self.logger.log_to_stderr()
            self.logger.log_to_stdout()
            log_file = os.path.join(os.getcwd(), self._testMethodName + '.log')
        else:
            self.logger.redirect_sys_stdout()
            log_file = os.path.join(self.defaultWorkingDirectory,
                                    self._testMethodName + '.log')
        self.logger.log_to_file(log_file)

    def setUp(self):
        # setUp stdout and stderr wrapping to capture
        # messages from the modules that we test
        self.setUpLogging()

        # create a test repository to operate in.
        bare_repo = self.repo + '-origin'
        os.mkdir(bare_repo)

        git.gitcmd("init --bare", "Setup Failed",
                   execution_path=bare_repo)
        working_dir = os.path.dirname(f"{self.repo}-origin")
        git.clone(source_repo=bare_repo, clone_repo=self.repo,
                  execution_path=self.defaultWorkingDirectory)
        fname = os.path.join(self.repo, "testRepoFile")
        writeFile1(fname)
        self.file1 = fname
        git.add(fname, execution_path=self.repo)
        git.commit("-m \"initial commit\"", execution_path=self.repo)
        git.gitcmd(f"push origin master", "push to master failed",
                   execution_path=self.repo)
        # create a develop branch in addition to master by default
        git.branch("develop", execution_path=self.repo)
        git.push("origin develop", execution_path=self.repo)

        self.menu.set_command_path(self.repo)

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
        shutil.rmtree(self.defaultWorkingDirectory, False, onError)

        # reset grapeConfig and grapeMenu
        config_parser_global.resetGrapeConfig()
        grapeMenu._resetMenu()
        self.logger.restore_sys_stdout()

        if not self._debug and os.path.isfile(self.logger.log_file):
            os.remove(self.logger.log_file)

    def get_output(self):
        return self.logger.get_log_file_contents()

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
            msg += f"\n{self.get_output()}"
        super(TestGrape, self).assertTrue(expr, msg=msg)

    def assertFalse(self, expr, msg=None):
        if msg is not None:
            msg += f"\n{self.get_output()}"
        super(TestGrape, self).assertFalse(expr, msg=msg)


def buildSuite(cls, appendTo, sub=None):
    suite = appendTo
    if sub:
        suite.addTest(cls(sub))
    else:
        suite.addTest(unittest.makeSuite(cls))
    return suite


def main(argv, debug=False):

    from test import testBranches
    from test import testBundle
    from test import testClone
    from test import testConfig
    from test import testDeleteBranch
    from test import testMergeDevelop
    from test import testGrapeGit
    from test import testResolveConflicts
    from test import testReview
    from test import testStash
    from test import testUnbundle
    from test import testVersion
    from test import testPublish
    from test import testCO
    from test import testNestedSubproject
    from test import testStatus
    from test import testUpdateLocal

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
                   "NestedSubproject":testNestedSubproject.TestNestedSubproject}


    suite = unittest.TestSuite()
    if len(argv) == 0:
        testClasses.update({"Status": testStatus.createStatusTester(),
                            "GrapeUp":testUpdateLocal.createUpTester()})
        for cls in testClasses.values():
            suite = buildSuite(cls, suite)
    else:
        if argv[0] == "listSuites":
            print(testClasses.keys())
            exit(0)
        if "Status" in argv:
            testClasses.update({"Status": testStatus.createStatusTester()})
        if "GrapeUp" in argv:
            testClasses.update({"GrapeUp": testUpdateLocal.createUpTester()})
        for arg in argv:
            if '.' in arg:
                (cls, sub) = arg.split('.')
                try:
                    cls = testClasses[cls]
                except:
                    print(f"*** {cls} is not a valid test suite!\n" + \
                          f"Valid values are:\n{testClasses.keys()}")
                    exit(0)
            else:
                try:
                    cls = testClasses[arg]
                except:
                    print(f"*** {arg} is not a valid test suite!\n" + \
                          f"Valid values are:\n{testClasses.keys()}")
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
