import multiprocessing
import os
from grape.vine import config_parser_global
from grape.vine import grape_errors
from grape.vine import utility
from grape.vine.option import Option


# Utility function for a MultiRepoCommandLauncher, unpacks a tuple, ensures cwd is the repo to run
# a method in, and launches the method. Needs to be at the file scope for stricter implementations of
# pickle, used by the multiprocess module.
def runCommandOnRepoBranch(task_queue, results_queue):
    while not task_queue.empty():
        repoBranchCommandTuple = task_queue.get()
        curDir = os.getcwd()
        repo = repoBranchCommandTuple[0]
        branch = repoBranchCommandTuple[1]
        f = repoBranchCommandTuple[2]
        args = repoBranchCommandTuple[3]
        os.chdir(repo)
        try:
            result = f(repo=repo, branch=branch, args=args)
            results_queue.put(result)
        except TypeError:
            try:
                result = f(repo=repo, branch=branch)
                results_queue.put(result)
            except TypeError:
                try:
                    result = f()
                    results_queue.put(result)
                except Exception as e:
                    return e
            except Exception as e:
                return e
        except Exception as e:
            return e


# Used for executing Single Lambda Multiple Repository instructions in parallel.
# If runInSubmodules is set to true (default), lambdas will run in active submodules.
# If runInSubprojects is set to true (default), lambdas will run in active nested subprojects.
# If runInOuter is set to true (default), lambdas will also run in the main workspace repository.

class MultiRepoCommandLauncher(object):

    def __init__(self, lambda_, runInSubmodules=False, runInSubprojects=True,
                 runInOuter=True, branch="", globalArgs=None, perRepoArgs=[],
                 listOfRepoBranchArgTuples=None, skipSubmodules=False,
                 outer=""):
        multiprocessing.log_to_stderr()

        self.lambda_ = lambda_
        self.run_submodules = self.should_run_submodules(skipSubmodules,
                                                         runInSubmodules)
        self.run_subprojects = runInSubprojects
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
            self.outer = utility.workspaceDir()

    def should_run_submodules(self, skip_sub_modules, run_in_submodules):
        config = config_parser_global.grapeConfig()
        if config.getboolean(Option.SECTION_WORKSPACE, "manageSubmodules"):
            return not skip_sub_modules
        return run_in_submodules

    def MergeLaunchSet(self, otherMRCL):
        self.initializeCommands()
        otherMRCL.initializeCommands()
        for args in self.perRepoArgs + otherMRCL.perRepoArgs:
            if args:
                print("WARNING: IGNORING PER REPO ARGS, likely badness will happen if needed")
                break

        reducedSet = list(set(zip(self.branches+otherMRCL.branches, self.repos+otherMRCL.repos)))
        self.branches = []
        self.repos = []
        self.perRepoArgs = []
        for t in reducedSet:
            self.branches.append(t[0])
            self.repos.append(t[1])
            self.perRepoArgs.append([])

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


    def initializeCommands(self):
        # don't reinit
        if self.repos:
            return

        # Imported here to delay grapeGit importing.
        from grape.vine import config_parser_user
        from grape.vine import grapeGit as git

        config = config_parser_global.grapeConfig()
        currentBranch = git.currentBranch() if not self.branchArg else self.branchArg
        publicBranches = config.getPublicBranchList()

        if self.launchTuple is not None:
            self.repos = [os.path.abspath(x[0]) for x in self.launchTuple]
            self.branches = [x[1] for x in self.launchTuple]
            self.perRepoArgs = [x[2] for x in self.launchTuple]
        else:
            if self.run_subprojects:
                activeSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes()
                self.repos = self.repos + [os.path.join(utility.workspaceDir(), sub) for sub in activeSubprojects]
                self.branches = self.branches + [currentBranch for x in activeSubprojects]
            if self.run_submodules:
                ws_dir = utility.workspaceDir()
                activeSubmodules = git.getActiveSubmodules(ws_dir)
                self.repos = self.repos + [os.path.join(ws_dir, r) for r in activeSubmodules]
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

    def add_tasks(self):
        task_queue = multiprocessing.SimpleQueue()
        for repo, branch, arg in zip(self.repos, self.branches, self.perRepoArgs):
            task_queue.put((repo, branch, self.lambda_, arg))
        while task_queue.empty():
            pass
        return task_queue

    def launchFromWorkspaceDir(self, handleMRE=None, noPause=False):
        with utility.cd_workspace():
            self.initializeCommands()

            if not self.repos:
                return

            retvals = []
            processes = []

            results_queue = multiprocessing.SimpleQueue()
            task_queue = self.add_tasks()

            for _ in range(len(self.repos)):
                process = multiprocessing.Process(target=runCommandOnRepoBranch,
                                                  args=(task_queue, results_queue))
                processes.append(process)
            for process in processes:
                process.run()

            while not results_queue.empty():
                retvals.append(results_queue.get())

        MRE = grape_errors.MultiRepoException()
        for val in zip(retvals, self.repos, self.branches, self.perRepoArgs):
            if isinstance(val[0], Exception):
                MRE.addException(val[0], val[1], val[2], val[3])
        if MRE.hasException():
            if handleMRE:
                handleMRE(MRE)
            else:
                raise MRE
        return retvals
