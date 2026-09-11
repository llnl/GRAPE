# Utilities for the scenario-based workspace tests.
#
# The original version of this module replayed a full list of git and GRAPE
# setup commands for every test case. The current version still exposes the
# same `ResettableProject` abstraction, but it now snapshots the prepared
# workspace once and restores copies of that snapshot for later resets.

import logging
import os
import shutil
import sys
import tempfile
import types
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu
from vine import vine_logging
from vine.workspace_dir_handler import WorkspaceDirHandler


#A grape project in a command list form that has reset capability.
#Another way to make this work would be to take a user generated reset function
#in the constructor and just apply that.
class ResettableProject:
    """A workspace scenario that can be reset to a known prepared state.

    The scenario is defined as a command list. On the first reset we execute
    the commands and save the resulting filesystem tree as a snapshot. Later
    resets restore that snapshot instead of replaying every command.
    """

    def __init__(self, projectDir):

        self.projectPrefix = os.path.realpath(tempfile.mkdtemp())
        self.projectDir = projectDir
        if os.path.exists(projectDir):
            logging.error(f"Path ({projectDir}) already exists, so it " +
                          "cannot be used by a new ResettableProject.")
            sys.exit(1)

        self.vine_logger = vine_logging.GrapeLogger()
        grapeMenu._resetMenu()
        self.menu = grapeMenu.menu(workspace_dir=self.projectPrefix)
        self.apply_menu_choice = self.menu.applyMenuChoice
        self._snapshot_root = None

        #cmdList is a list of 2-tuples containing (function, param) pairs
        #param itself can be a tuple, a single parameter, or a single lambda function that provides arguments
        #  to the cmd.
        #Default commands set up an empty repository and a clone of that repository.
        self.cmdList =  [(os.mkdir, lambda: self.getOriginDir()) ,
                         (git.gitcmd, ("init --bare", "Setup Failed",
                                       lambda: self.getOriginDir())),
                         (git.clone, (lambda: self.getOriginDir(),
                                      lambda: self.getProjectDir(),
                                      lambda: self.getOriginDir()))]

    def getProjectDir(self):
        return os.path.abspath(os.path.join(self.projectPrefix,self.projectDir))

    def getOriginDir(self):
        return os.path.abspath(self.getProjectDir()+".origin")

    def addCommands(self, newCmds):
        self.cmdList.extend(newCmds)

    def reset(self, projectPrefix=None):
        """Restore the scenario into `projectPrefix`.

        Tests call this before each scenario-based assertion so every test gets
        an isolated copy of the prepared workspace.
        """
        self.tearDown()
        if (not projectPrefix is None):
            self.projectPrefix = projectPrefix
        self._restore_snapshot()

    def _restore_snapshot(self):
        """Copy the cached scenario snapshot into the active temp directory."""
        source_root = self._ensure_snapshot_root()
        for entry in os.listdir(source_root):
            src = os.path.join(source_root, entry)
            dst = os.path.join(self.projectPrefix, entry)
            shutil.copytree(src, dst)
            self._rewrite_paths(dst, source_root, self.projectPrefix)

    def _ensure_snapshot_root(self):
        """Build the scenario snapshot once and reuse it on later resets."""
        if self._snapshot_root is not None:
            return self._snapshot_root

        original_prefix = self.projectPrefix
        self._snapshot_root = os.path.realpath(
            tempfile.mkdtemp(prefix=f"grape-scenario-{self.projectDir}-")
        )
        self.projectPrefix = self._snapshot_root
        self._run_cmd_list()
        self.projectPrefix = original_prefix
        return self._snapshot_root

    def _run_cmd_list(self):
        """Execute the scenario's original setup command list."""
        #Run the commands using python's 1st order representations of the functions and tuples
        for (cmd, param) in self.cmdList:
            try:
                # evaluate param if it's a function type
                if isinstance(param, types.FunctionType):
                    param = param()
                if isinstance(param, tuple):
                    if isinstance(cmd, types.BuiltinFunctionType):
                        cmd(*param)     #The * does the magic of unpacking the tuple and using it as the parameter list
                        continue
                    # Always route scenario menu commands through this
                    # project's menu. Scenario definitions retain bound menu
                    # methods while several singleton menus are constructed
                    # during collection.
                    if getattr(cmd, "__name__", None) == "applyMenuChoice":
                        execution_path = self.getProjectDir()
                        self.menu.set_workspace_dir(execution_path)
                        # Menu options are constructed before the scenario's
                        # repository exists. Their workspace setter therefore
                        # may retain the process cwd from construction time.
                        # Pin every workspace-aware option once the scenario
                        # repository has been created.
                        for option in self.menu._options:
                            if isinstance(option, WorkspaceDirHandler):
                                option._workspace_dir = execution_path
                        self.menu.applyMenuChoice(*param)
                        continue

                    execution_path = self.get_execution_path(param)
                    if cmd == git.clone:
                        if len(param) == 2:
                            clone_args = param[0]().split()
                            cmd(clone_args[0],
                                source_repo=clone_args[1],
                                clone_repo=clone_args[2],
                                execution_path=execution_path)
                        else:
                            cmd(source_repo=param[0](),
                                clone_repo=param[1](),
                                execution_path=execution_path)
                    elif os.path.exists(execution_path):
                        param = param[:-1]
                        cmd(*param, execution_path=execution_path)
                    else:
                        raise RuntimeError
                else:
                    cmd(param)
            except grape_errors.GrapeGitError as e:
                logging.error(f"{e.gitCommand} {e.gitOutput}")
                raise e

    def _rewrite_paths(self, root, old_root, new_root):
        """Rewrite the few config files that embed absolute workspace paths."""
        def needs_rewrite(path, filename, current_root):
            if filename in {'.grapeconfig', '.gitmodules'}:
                return True
            if filename != 'config':
                return False
            if os.path.basename(current_root) == '.git':
                return True
            return f"{os.sep}.git{os.sep}" in path

        for current_root, _, files in os.walk(root):
            for filename in files:
                path = os.path.join(current_root, filename)
                if not needs_rewrite(path, filename, current_root):
                    continue
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        contents = handle.read()
                except (UnicodeDecodeError, OSError):
                    continue

                if old_root not in contents:
                    continue

                with open(path, 'w', encoding='utf-8') as handle:
                    handle.write(contents.replace(old_root, new_root))

    def get_execution_path(self, params):
        if not params or not isinstance(params, tuple):
            raise RuntimeError

        execution_path = params[-1]
        if isinstance(execution_path, types.FunctionType):
            execution_path = execution_path()
        if not os.path.exists(execution_path):
            execution_path = os.path.join(self.projectPrefix,
                                          execution_path)
            if not os.path.exists(execution_path):
                raise RuntimeError

        return execution_path

    def tearDown(self):
        if os.path.exists(self.getProjectDir()) and os.path.isdir(self.getProjectDir()):
            shutil.rmtree(self.getProjectDir(), ignore_errors=True)
        originDir = self.getOriginDir()
        if os.path.exists(originDir) and os.path.isdir(originDir):
            shutil.rmtree(originDir, ignore_errors=True)

# This takes a project and various test methods and generates a test method using
# a closure pattern.  It is part of the magic of createGridTestClass.
def generateTest(project, method):
    def test(self):
        if project.debugging():
            project.vine_logger.restore_sys_stdout()
        project.reset(self.defaultWorkingDirectory)
        method(self, project)
        if project.debugging():
            project.vine_logger.redirect_sys_stdout()
    return test


# Beware, this is a wonky piece of metacode.  It takes a length M list of resettable projects, and
# a length N list of tests encapsulated in a unittest.TestCase class.  The test methods must be prefixed with
# "gridtest" instead of test.  It then generates test methods for the M*N cases in that class.
def gridifyTestClass(projectList, testClass, projectNames=None):
    #Digest the class into pieces we can work with namely the method names and the methods pulled out of the class
    testMethodNames = [method for method in dir(testClass)
                       if callable(getattr(testClass, method)) and method.find("gridtest") == 0]
    testMethods = [getattr(testClass, method) for method in testMethodNames]

    #Now add the N*M test methods to the class testClass
    for projecti, project in enumerate(projectList):
        for (name, method) in zip(testMethodNames, testMethods):
            test = generateTest(project, method)
            mangled_name = name[4:] + '_' + projectNames[projecti]
            setattr(testClass, mangled_name, test)
