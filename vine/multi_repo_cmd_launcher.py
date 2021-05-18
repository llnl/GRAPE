import asyncio
import functools
import logging
import os
import socket
import sys
import warnings
from vine import config_parser_global
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine import grape_errors
from vine.vine_logging import log_wrapper
from vine.gendocs import Section

SECTION_CONCURRENCY_CONTROL = "concurrency-control"

def setDefaultConfig(cfg):
    cfg.ensureSection(SECTION_CONCURRENCY_CONTROL)
    cfg.set(SECTION_CONCURRENCY_CONTROL,"sharednodenumtasks", "8")
    cfg.set(SECTION_CONCURRENCY_CONTROL,"exclusivenodenumtasks", "40")
    cfg.set(SECTION_CONCURRENCY_CONTROL,"defaultsharednode", "False")
    cfg.set(SECTION_CONCURRENCY_CONTROL,"exclusivevarlist", "False")


# default level of concurrency (user can control using the --np option to the top level executable)
NUM_TASKS = -1

# using async Semaphore to limit concurrency of the gather
# https://stackoverflow.com/questions/48483348/how-to-limit-concurrency-with-python-asyncio/61478547#61478547
async def gather_with_concurrency(n, *tasks):
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task
    return await asyncio.gather(*(sem_task(task) for task in tasks), return_exceptions=True)

class MultiRepoCommandRunner(WorkspaceDirHandler):

    def __init__(self):
        self.task_queue = []

    def add_cmd_tuple_to_task_queue(self, cmd_tuple):
        """
        Retrofitting the old 'repoBranchCommandTuple' into an asyncio runnable.

        'RuntimeWarning: coroutine was never awaited' is ignored here since
        it will be "awaited" (run in an event loop) during self.run_all().
        """
        if isinstance(cmd_tuple, list):
            while cmd_tuple:
                #important to pop from front to keep result order the same
                inner_tuple = cmd_tuple.pop(0)
                self.add_cmd_tuple_to_task_queue(inner_tuple)
            return

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            runnable_task = self._tuple_task(cmd_tuple)
        self.task_queue.append(runnable_task)

    def run_all(self, concurrency):
        tasks = self.task_queue
        if all(asyncio.iscoroutine(task) for task in tasks):
            return asyncio.run(self._run_commands(tasks, concurrency))

    async def _tuple_task(self, cmd_tuple):
        """
        Retrofitting the old 'repoBranchCommandTuple' into an asyncio runnable.
        """
        loop = asyncio.get_running_loop()
        repo, branch, func, args = cmd_tuple
        if not callable(func):
            exit(['NOT CALLABLE', func])

        if hasattr(func, '__code__') and hasattr(func.__code__, 'co_varnames'):
            varnames = func.__code__.co_varnames
        else:
            return None

        if 'repo' not in varnames or 'branch' not in varnames:
            return await loop.run_in_executor(
                None, functools.partial(func, execution_path=self.workspace_dir))
        elif 'args' in varnames:
            return await loop.run_in_executor(
                None, functools.partial(func, repo=repo, branch=branch,
                                        args=args,
                                        execution_path=self.workspace_dir))
        return await loop.run_in_executor(None, functools.partial(
            func, repo=repo, branch=branch, execution_path=self.workspace_dir))


    async def _run_commands(self, commands, concurrency):
        runnable_coroutines = []
        for command in commands:
            runnable_coroutines.append(command)
        results = await gather_with_concurrency(concurrency, *runnable_coroutines)
        self.task_queue = []
        return results


# Used for executing Single Lambda Multiple Repository instructions in parallel.
# If runInSubmodules is set to true (default), lambdas will run in active submodules.
# If runInSubprojects is set to true (default), lambdas will run in active nested subprojects.
# If runInOuter is set to true (default), lambdas will also run in the main workspace repository.

class MultiRepoCommandLauncher(WorkspaceDirHandler):

    def __init__(self, lmbda, runInSubmodules=False, runInSubprojects=True, runInOuter=True, branch="",
                 globalArgs=None, perRepoArgs=[], listOfRepoBranchArgTuples=None, skipSubmodules=False,
                 outer="", *, execution_path):
        self.cmd_runner = MultiRepoCommandRunner()
        self.lmbda = lmbda
        self.workspace_dir = execution_path

        config = config_parser_global.grapeConfig()
        recurseSubmodules = config.getboolean(Option.SECTION_WORKSPACE, "manageSubmodules")
        if not recurseSubmodules:
            self.runSubmodules = runInSubmodules
        else:
            self.runSubmodules = recurseSubmodules
        # apply the skipSubmodules override
        self.runSubmodules = self.runSubmodules and not skipSubmodules
        self.runSubprojects = runInSubprojects
        self.runOuter = runInOuter
        self.branchArg = branch
        self.perRepoArgs = perRepoArgs
        self.globalArgs = globalArgs
        self.launchTuple = listOfRepoBranchArgTuples

        self.repos = []
        self.branches = []
        if outer:
            self.outer = outer
        else:
            self.outer = self.workspace_dir

    @log_wrapper
    def MergeLaunchSet(self, otherMRCL):
        self.initializeCommands()
        otherMRCL.initializeCommands()
        for args in self.perRepoArgs + otherMRCL.perRepoArgs:
            if args:
                logging.warning("WARNING: IGNORING PER REPO ARGS, likely badness will happen if needed")
                break

        reducedSet = list(set(zip(self.branches+otherMRCL.branches, self.repos+otherMRCL.repos)))
        self.branches = []
        self.repos = []
        self.perRepoArgs = []
        for t in reducedSet:
            self.branches.append(t[0])
            self.repos.append(t[1])
            self.perRepoArgs.append([])

    @log_wrapper
    def collapseLaunchSetBranches(self):
        # ensures we have one launch per repo, turning the branch argument into the list of branches
        # this launcher will use
        self.initializeCommands()
        newBranches = []
        newRepos = []
        newArgs = []
        # this is a terrible N^2 algorithm at the moment
        for b, r, a in zip(self.branches, self.repos, self.perRepoArgs):
            try:
                i = newRepos.index(r)
                newBranches[i].append(b)
            except ValueError:
                newRepos.append(r)
                newBranches.append([b])
                newArgs.append(a)
        self.branches = newBranches
        self.repos = newRepos
        self.perRepoArgs = newArgs

    @log_wrapper
    def initializeCommands(self):
        # Imported here to delay grapeGit importing.
        from vine import config_parser_user
        from vine import grapeGit as git

        if self.branchArg:
            currentBranch = self.branchArg
        else:
            currentBranch = git.currentBranch(execution_path=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()

        # don't reinit
        if self.repos:
            return
        if self.launchTuple is not None:
            self.repos = [os.path.abspath(x[0]) for x in self.launchTuple]
            self.branches = [x[1] for x in self.launchTuple]
            self.perRepoArgs = [x[2] for x in self.launchTuple]
        else:
            if self.runSubprojects:
                activeSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)
                self.repos = self.repos + [os.path.join(self.workspace_dir, sub) for sub in activeSubprojects]
                self.branches = self.branches + [currentBranch for x in activeSubprojects]
            if self.runSubmodules:
                activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
                self.repos = self.repos + [os.path.join(self.workspace_dir, r) for r in activeSubmodules]
                subPubMap = config.getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")
                submoduleBranch =  subPubMap[currentBranch] if currentBranch in publicBranches else currentBranch
                self.branches = self.branches + [ submoduleBranch for x in activeSubmodules ]
            if self.runOuter:
                self.repos.append(self.outer)
                self.branches.append(currentBranch)
            if not self.perRepoArgs:
                if not self.globalArgs:
                    self.perRepoArgs = [[] for x in self.repos]
                else:
                    self.perRepoArgs = [self.globalArgs for x in self.repos]

    @log_wrapper
    def launchFromWorkspaceDir(self, handleMRE=None, noPause=False):
        self.initializeCommands()
        retvals = []

        self.cmd_runner.workspace_dir = self.workspace_dir

        if noPause:
            # for purely local operations, run them all at once.
            if len(self.repos) > 0:
                command_list = [(repo, branch, self.lmbda, arg) for repo, branch, arg in zip(self.repos, self.branches, self.perRepoArgs)]
                self.cmd_runner.add_cmd_tuple_to_task_queue(command_list)
                retvals = self.cmd_runner.run_all(self.concurrency)
        else:
            # run the first entry first so that things like logging in to the project's server happen up front
            if len(self.repos) > 0:
                command_list = (self.repos[0], self.branches[0], self.lmbda, self.perRepoArgs[0])
                self.cmd_runner.add_cmd_tuple_to_task_queue(command_list)
                retvals = self.cmd_runner.run_all(self.concurrency)
            if len(self.repos) > 1:
                command_list = [(repo, branch, self.lmbda, arg) for repo, branch, arg in zip(self.repos[1:], self.branches[1:], self.perRepoArgs[1:])]
                self.cmd_runner.add_cmd_tuple_to_task_queue(command_list)
                retvals = retvals + self.cmd_runner.run_all(self.concurrency)

        MRE = grape_errors.MultiRepoException(workspace_dir=self.workspace_dir)
        for val in zip(retvals, self.repos, self.branches, self.perRepoArgs):
            if isinstance(val[0], Exception):
                MRE.addException(val[0], val[1], val[2], val[3])
        if MRE.hasException():
            if handleMRE:
                handleMRE(MRE)
            else:
                raise MRE
        return retvals

    # determine concurrency based off of whether we are executing on a shared or exclusive resource
    @property
    def concurrency(self):
        # this is set via the command line, which overrides configuration behavior
        if NUM_TASKS > -1:
            n = NUM_TASKS
        else:
            config = config_parser_global.grapeConfig()

            # user needs to opt out of assuming an exlusive node by setting defaultsharednode to True
            is_exclusive_node = not config.getboolean(SECTION_CONCURRENCY_CONTROL, "defaultsharednode")

            # if we are on osx or windows, assume to be a personal machine, therefore an exclusive resource
            if not is_exclusive_node and (os.name == "nt" or sys.platform == "darwin"):
                is_exclusive_node = True

            #if any of these environment variables exist, the user has indicated this signals being on
            #an exclusive resource
            if not is_exclusive_node:
                exclusive_environment_variables = config.get(SECTION_CONCURRENCY_CONTROL, "exclusivevarlist")
                if exclusive_environment_variables != "False":
                    for var in exclusive_environment_variables.split(' '):
                        if var in os.environ:
                            is_exclusive_node = True
                            break

            if is_exclusive_node:
                n = config.getint(SECTION_CONCURRENCY_CONTROL, "exclusivenodenumtasks")
            else:
                n = config.getint(SECTION_CONCURRENCY_CONTROL, "sharednodenumtasks")
        logging.debug(f"concurrency set to {n}")
        return n
