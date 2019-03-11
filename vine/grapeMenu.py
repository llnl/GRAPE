import os
import sys
import subprocess
import tempfile
import traceback
import types
toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")
if toplevel not in sys.path:
    sys.path.insert(0, toplevel)
from docopt.docopt import docopt
from docopt.docopt import Dict as docoptDict

import addSubproject
import bundle
import branches
import checkout
import clone
import commit
import config
import deleteBranch
import foreach
import grape_errors
import grapeConfig
import grapeGit as git
import hooks
import merge
import mergeDevelop
import mergeRemote
import newFlowBranch
import newWorkingTree
import publish
import pull
import push
import quit
import resolveConflicts
import resumable
import review
import stash
import status
import grapeTest as test
import updateLocal
import updateSubproject
import updateView
import utility
import version
import walkthrough


#################################
# Temporary home for code below #
#################################


global_args = []

globalVerbosity = 1
globalShowProgress = True


CLI =  """
*** GRAPE - Git Replacement for "Awesome" PARSEC Environment **********
Calling grape by itself will pull up the grape menu.
Usage: grape [-v | -q] [--version] [--noProgress] [--np=<numProcs>][<command> <args>...]

Options:
-v           Run in verbose mode. This will print out git output as git commands complete.
-q           Quiet mode. Quiet's all output except for user input prompts.
--noProgress Do not show progress for long-running git subprocesses. This will remove
             a fair amount of process-launch overhead in GRAPE, which can have a speedup of
             about a third.
--np=<int>   The number of processes grape should launch when doing parallel operations.



"""


def setVerbosity(level):
    global globalVerbosity
    globalVerbosity = level

def setShowProgress(val):
    global globalShowProgress
    globalShowProgress = val

def __apply__(args, CLI):
    if type(args) is docoptDict:
        if args["-v"]:
            setVerbosity(2)
        elif args["-q"]:
            setVerbosity(0)
        else:
            setVerbosity(1)
        if args["--noProgress"]:
            setShowProgress(False)
        if args["--np"]:
            MultiRepoCommandLauncher.numProcs = int(args["--np"])
        else:
            setShowProgress(True)
    if type(args) is types.ListType:
        # assume the list has yet to be parsed by docopt into the dict __apply__ expects.
        return __apply__(docopt(CLI,args, options_first=True), CLI)

def applyGlobalArgs(args, CLI=CLI):
    global global_args
    __apply__(args, CLI)
    global_args.append(args)

def popGlobalArgs():
    global global_args
    if len(global_args) > 1:
        global_args.pop()
    __apply__(global_args[-1], CLI)


# thanks to jcollado at stackoverflow for inspiration:
# http://stackoverflow.com/questions/1191374/subprocess-with-timeout
import multiprocessing
import tailer

def runFollowableTarget(followableCmd):
    followableCmd.runTarget()

def followFollowableTarget(followableCmd):
    followableCmd.followTarget()

class FollowableProcess(object):
    def __init__(self, process):
        self.output = ''
        self.returncode = process.returncode
        self.pid = process.pid

class FollowableCommand(object):
    def __init__(self, cmd, wd, outfile, stdin):
        self.cmd = cmd
        self.process = None
        self.wd = wd
        self.outfileName = outfile.name
        self.fileno = outfile.fileno()
        self.stdin = stdin
        self.finishedProcesses = multiprocessing.Queue()
        self.stopFollowing = 0

    def runTarget(self):
        # runs a subprocess and produces a finished subprocess in the finishedProcesses Queue.

        process = subprocess.Popen(self.cmd, stdout=self.fileno, stderr=subprocess.STDOUT, shell=(os.name != "nt"),
                               cwd=self.wd, stdin=sys.stdin, bufsize=1)
        process.wait()
        self.finishedProcesses.put(FollowableProcess(process), block=False)

    def followTarget(self):
        # uses tailer to follow the output of the running process
        if os.name == "nt":
            flags = os.O_RDWR | os.O_TEMPORARY
        else:
            flags = os.O_RDWR

        try:
            f = os.open(self.outfileName, flags)
            fo = os.fdopen(f,'r');
            generator = tailer.follow(fo)
            for l in generator:
                print l
        finally:
            os.close(fo)
            os.close(f)

    def run(self, startStreaming=5):

        # the cmd launch process
        thread = multiprocessing.Process(target=runFollowableTarget,args=[self])
        # the tailer.follow process
        followThread = multiprocessing.Process(target=followFollowableTarget, args=[self])
        thread.start()

        thread.join(startStreaming)
        if thread.is_alive():
            # follow output in the outfile
            print "Executing %s\n\tWorking Directory: %s..." % (self.cmd, self.wd)
            followThread.start()
            # keep going until the subprocess is done
            thread.join()
            followThread.terminate()
            self.stopFollowing = 1


def executeSubProcess(command, workingDirectory=os.getcwd(), verbose=2,
                      stdin=sys.stdin, stream = False):

    if verbose == -1:
        verbose = globalVerbosity
    if verbose > 1:
        print("Executing: " + command + "\n\t Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    if stream:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=(os.name != "nt"),
                                   cwd=workingDirectory, stdin=stdin, bufsize=1)
        output = ''
        while process.poll() is None:
            out = process.stdout.read(1)
            if verbose > 0:
                sys.stdout.write(out)
                sys.stdout.flush()
            output += out
        process.wait() # should be a noop
        out +=  process.communicate()[0] # also should be a noop
        if verbose > 0:
            sys.stdout.write(out)
            sys.stdout.flush()
        output += out

    # TODO: Followable commands aren't working in Windows right now - initially there were some pickling difficulties,
    # but now we are seeing behaviors that look like multiprocessing subprocesses are being launched in incorrect directories.
    # To be troubleshooted later.
    elif globalShowProgress and os.name == "posix":
        with tempfile.NamedTemporaryFile() as tmpFile:
            launcher = FollowableCommand(command, workingDirectory, tmpFile, stdin)
            launcher.run(startStreaming=3.0)
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1 and launcher.stopFollowing == 0:
                print(output.strip())
            process = launcher.finishedProcesses.get()
    else:
        with tempfile.TemporaryFile() as tmpFile:
            process = subprocess.Popen( command, cwd=workingDirectory, shell=(os.name != "nt"), stdout=tmpFile.fileno(),
                                        stderr=subprocess.STDOUT )
            process.wait()
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1:
                print(output.strip())

    process.output = output
    if process.returncode != 0 and verbose > 1:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process


def printMsg(msg):
    global globalVerbosity
    if globalVerbosity > 0:
        print("GRAPE: %s" % msg)



#######################################################################
#The Menu class - encapsulates menu options and sections.
# Menu Options are the objects that perform git-related or bitbucket-related tasks.
# sections are groupings of menu options that are displayed together.
######################################################################
__menuInstance = None


def menu():
    global __menuInstance
    if __menuInstance is None:
        __menuInstance = _Menu()
        grapeConfig.readDefaults()
        grapeConfig.read()
        __menuInstance.postInit()
    return __menuInstance


def _resetMenu():
    """
    Resets the Singleton Instance. Meant for testing purposes only.

    """
    global __menuInstance
    __menuInstance = None
    grapeConfig.resetGrapeConfig()


class _Menu(object):
    def __init__(self):
        self._options = {}
        #Add menu classes
        self._optionLookup = {}
        #Add/order your menu option here
        self._options = [addSubproject.AddSubproject(), bundle.Bundle(), bundle.Unbundle(), branches.Branches(),
                         status.Status(), stash.Stash(), checkout.Checkout(), push.Push(), pull.Pull(), commit.Commit(), publish.Publish(),
                         clone.Clone(), config.Config(), grapeConfig.WriteConfig(),
                         foreach.ForEach(), merge.Merge(), mergeDevelop.MergeDevelop(), mergeRemote.MergeRemote(),
                         deleteBranch.DeleteBranch(), newWorkingTree.NewWorkingTree(),
                         resolveConflicts.ResolveConflicts(),
                         review.Review(), test.Test(), updateLocal.UpdateLocal(), updateSubproject.UpdateSubproject(),
                         hooks.InstallHooks(), hooks.RunHook(),
                         updateView.UpdateView(), version.Version(), walkthrough.Walkthrough(), quit.Quit()]

        #Add/order the menu sections here
        self._sections = ['Getting Started', 'Code Reviews', 'Workspace',
                          'Merge', 'Gitflow Tasks', 'Hooks', 'Patches', 'Project Management', 'Other']

    def postInit(self):
        # add dynamically generated (dependent on grapeConfig) options here
        self._options = self._options + newFlowBranch.NewBranchOptionFactory().createNewBranchOptions(grapeConfig.
                                                                                                      grapeConfig())
        for currOption in self._options:
            self._optionLookup[currOption.key] = currOption

    #######      MENU STUFF         #########################################################################
    def getOption(self, choice):
        try:
            return self._optionLookup[choice]
        except KeyError:
            print("Unknown option '%s'" % choice)
            return None

    def applyMenuChoice(self, choice, args=None, option_args=None, globalArgs=None):
        chosen_option = self.getOption(choice)
        if chosen_option is None:
            return False
        if args is None or len(args) == 0:
            args = [chosen_option._key]
        #first argument better be the key
        if args[0] != chosen_option._key:
            args = [chosen_option._key]+args

        # use optdoc to parse arguments to the chosen_option.
        # utility.argParse also does the magic of filling in defaults from the config files as appropriate.
        if option_args is None and chosen_option.__doc__:
            try:
                config = chosen_option._config
                if config is None:
                    config = grapeConfig.grapeConfig()
                else:
                    config = grapeConfig.grapeRepoConfig(config)
                option_args = utility.parseArgs(chosen_option.__doc__, args[1:], config)
            except SystemExit as e:
                if len(args) > 1 and "--help" != args[1] and "-h" != args[1]:
                    print("GRAPE PARSING ERROR: could not parse %s\n" % (args[1:]))
                raise e
        if globalArgs is not None:
            applyGlobalArgs(globalArgs)
        try:
            if isinstance(chosen_option, resumable.Resumable):
                if option_args["--continue"]:
                    return chosen_option._resume(option_args)
            return chosen_option.execute(option_args)

        except grape_errors.GrapeGitError as e:
            print traceback.print_exc()
            print ("GRAPE: Uncaught Error %s in grape-%s when executing '%s' in '%s'\n%s" %
                   (e.code, chosen_option._key,  e.gitCommand, e.cwd, e.gitOutput))
            exit(e.code)

        except grape_errors.NoWorkspaceDirException as e:
            print ("GRAPE: grape %s must be run from a grape workspace." % chosen_option.key)
            print ("GRAPE: %s" % e.message)
            exit(1)
        finally:
            if globalArgs is not None:
                popGlobalArgs()

    # Present the main menu
    def presentTextMenu(self):
        width = 60
        print("GRAPE - Git Replacement for \"Awesome\" PARSEC Environment".center(width, '*'))

        longest_key = 0
        for currOption in self._options:
            if len(currOption.key) > longest_key:
                longest_key = len(currOption.key)

        for currSection in self._sections:
            lowered_section = currSection.strip().lower()
            print("\n" + (" %s " % currSection).center(width, '*'))
            for currOption in self._options:
                if currOption.section.strip().lower() != lowered_section:
                    continue
                print("%s: %s" % (currOption.key.ljust(longest_key), currOption.description()))

    # configures a ConfigParser object with all default values and sections needed by our Option objects
    def setDefaultConfig(self, cfg):
        cfg.ensureSection("repo")
        cfg.set("repo", "name", "repo_name_not.yet.configured")
        cfg.set("repo", "url", "https://not.yet.configured/scm/project/unknown.git")
        cfg.set("repo", "httpsbase", "https://not.yet.configured")
        cfg.set("repo", "sshbase", "ssh://git@not.yet.configured")
        for currOption in self._options:
            currOption.setDefaultConfig(cfg)




# Utility function for a MultiRepoCommandLauncher, unpacks a tuple, ensures cwd is the repo to run
# a method in, and launches the method. Needs to be at the file scope for stricter implementations of
# pickle, used by the multiprocess module.
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

import multiprocessing.pool
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

        config = grapeConfig.grapeConfig()
        recurseSubmodules = config.getboolean("workspace", "manageSubmodules")
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



    def MergeLaunchSet(self, otherMRCL):
        self.initializeCommands()
        otherMRCL.initializeCommands()
        for args in self.perRepoArgs + otherMRCL.perRepoArgs:
            if args:
                print ("WARNING: IGNORING PER REPO ARGS, likely badness will happen if needed")
                break

        reducedSet = list(set(zip(self.branches+otherMRCL.branches,
                                                                     self.repos+otherMRCL.repos)))
        self.branches = []
        self.repos = []
        self.perRepoArgs = []
        for t in reducedSet:
            self.branches.append(t[0])
            self.repos.append(t[1])
            self.perRepoArgs.append([])

        pass

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

    def printLaunchSet(self):
        for b, r, a in zip(self.branches, self.repos, self.perRepoArgs):
            print "%s,%s,%s" % (b, r, a)


    def initializeCommands(self):
        config = grapeConfig.grapeConfig()
        currentBranch = git.currentBranch() if not self.branchArg else self.branchArg
        publicBranches = config.getPublicBranchList()
        wsDir = dir

        # don't reinit
        if self.repos:
            return
        if self.launchTuple is not None:
            self.repos = [os.path.abspath(x[0]) for x in self.launchTuple]
            self.branches = [x[1] for x in self.launchTuple]
            self.perRepoArgs = [x[2] for x in self.launchTuple]
        else:
            if self.runSubprojects:
                activeSubprojects =  grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
                self.repos = self.repos + [os.path.join(utility.workspaceDir(), sub) for sub in activeSubprojects]
                self.branches = self.branches + [currentBranch for x in activeSubprojects]
            if self.runSubmodules:
                activeSubmodules = git.getActiveSubmodules()
                self.repos = self.repos + [os.path.join(utility.workspaceDir(), r) for r in activeSubmodules]
                subPubMap = config.getMapping("workspace", "submodulepublicmappings")
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

    def launchFromWorkspaceDir(self, handleMRE=None, noPause=False):
        with utility.cd(utility.workspaceDir()):
            argLists = self.perRepoArgs
            config = grapeConfig.grapeConfig()

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
