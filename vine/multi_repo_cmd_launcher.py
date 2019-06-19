import logging
import os
import multiprocessing.pool
import config_parser_global
from option import Option
import grape_errors
import utility
from vine_logging import log_wrapper


# Utility function for a MultiRepoCommandLauncher, unpacks a tuple, ensures cwd is the repo to run
# a method in, and launches the method. Needs to be at the file scope for stricter implementations of
# pickle, used by the multiprocess module.
@log_wrapper
def runCommandOnRepoBranch(repoBranchCommandTuple):
    curDir = os.getcwd()
    repo = repoBranchCommandTuple[0]
    branch = repoBranchCommandTuple[1]
    f = repoBranchCommandTuple[2]
    args = repoBranchCommandTuple[3]
    os.chdir(repo)
    try:
        return f(repo=repo, branch=branch, args=args)
    except TypeError:
        try:
            return f(repo=repo, branch=branch)
        except TypeError:
            try:
                return f()
            except Exception as e:
                return e
        except Exception as e:
            return e
    except Exception as e:
        return e

    os.chdir(curDir)

# Thanks to Chris Arndt at http://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
# for this lovely magic.
class NoDaemonProcess(multiprocessing.Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class MyPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


# Used for executing Single Lambda Multiple Repository instructions in parallel.
# If runInSubmodules is set to true (default), lambdas will run in active submodules.
# If runInSubprojects is set to true (default), lambdas will run in active nested subprojects.
# If runInOuter is set to true (default), lambdas will also run in the main workspace repository.

class MultiRepoCommandLauncher(object):
    numProcs = 8
    # lmbda needs to match the signature of f(repo=...) as called in runCommandOnRepoBranch (above)
    def __init__(self, lmbda, nProcesses=-1, runInSubmodules=False, runInSubprojects=True, runInOuter=True, branch="",
                 globalArgs=None,perRepoArgs=[], listOfRepoBranchArgTuples=None, skipSubmodules=False, outer=""):
        self.lmbda = lmbda

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
        if nProcesses < 0:
            nProcesses = MultiRepoCommandLauncher.numProcs
        self.pool = MyPool(nProcesses)
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
        import config_parser_user
        import grapeGit as git

        config = config_parser_global.grapeConfig()
        currentBranch = git.currentBranch() if not self.branchArg else self.branchArg
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
                activeSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes()
                self.repos = self.repos + [os.path.join(utility.workspaceDir(), sub) for sub in activeSubprojects]
                self.branches = self.branches + [currentBranch for x in activeSubprojects]
            if self.runSubmodules:
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

    @log_wrapper
    def launchFromWorkspaceDir(self, handleMRE=None, noPause=False):
        with utility.cd(utility.workspaceDir()):
            argLists = self.perRepoArgs

            self.initializeCommands()

            retvals = []

            if noPause:
                # for purely local operations, run them all at once.
                if len(self.repos) > 0:
                    retvals = self.pool.map(runCommandOnRepoBranch, [(repo, branch, self.lmbda, arg) for repo, branch, arg in zip(self.repos, self.branches, self.perRepoArgs)])
            else:
                # run the first entry first so that things like logging in to the project's server happen up front
                if len(self.repos) > 0:
                    retvals.append(runCommandOnRepoBranch((self.repos[0], self.branches[0], self.lmbda, self.perRepoArgs[0])))
                    if isinstance(retvals[0], Exception):
                        retvals[0] = runCommandOnRepoBranch((self.repos[0], self.branches[0], self.lmbda, self.perRepoArgs[0]))
                if len(self.repos) > 1:
                    retvals = retvals + self.pool.map(runCommandOnRepoBranch, [(repo, branch, self.lmbda, arg) for repo, branch, arg in zip(self.repos[1:], self.branches[1:], self.perRepoArgs[1:])])

        self.pool.close()
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
