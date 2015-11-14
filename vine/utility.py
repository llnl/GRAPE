import os
import subprocess
import sys
import ConfigParser
import types
import tempfile

import grapeGit as git
import grapeMenu
import grapeConfig
 

toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")
if toplevel not in sys.path:
    sys.path.append(toplevel)
from docopt.docopt import docopt
from docopt.docopt import Dict as docoptDict


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


#ensures the path string is windows compatibile if necessary
def makePathPortable(path): 
    if os.name == "nt":
        newPath = path.replace("/", "\\")
    else:
        newPath = path
    return newPath

globalArgs = []

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
    global globalArgs
    __apply__(args, CLI)
    globalArgs.append(args)

def popGlobalArgs():
    global globalArgs
    if len(globalArgs) > 1:
        globalArgs.pop()
    __apply__(globalArgs[-1], CLI)


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

# there is a bug in pickle that causes it to only use a default initializer for GrapeGitError objects,
# this is a wrapper to allow exception capture in runCommandOnRepoBranch. 
class MultiRepoException(Exception):
    def __init__(self):
        self._exceptions = []
        self._repos = []
        self._branches = []
        self._args = []
        
    def addException(self, e, repo, branch, args):
        self._exceptions.append(e)
        self._repos.append(repo)
        self._branches.append(branch)
        self._args.append(args)
    
    def __getitem__(self, pos):
        return self._exceptions[pos]
    
    def exceptions(self):
        return self._exceptions

    def repos(self):
        return self._repos
    
    def branches(self):
        return self._branches
    
    def args(self):
        return self._args
        
    def hasException(self):
        return len(self._exceptions) > 0
        

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
    def __init__(self, lmbda, nProcesses=-1, runInSubmodules=True, runInSubprojects=True, runInOuter=True, branch="",
                 globalArgs=None,perRepoArgs=None, listOfRepoBranchArgTuples=None):
        self.lmbda = lmbda
        self.runSubmodules = runInSubmodules
        self.runSubprojects = runInSubprojects
        self.runOuter = runInOuter
        if nProcesses < 0:
            nProcesses = MultiRepoCommandLauncher.numProcs
        self.pool = MyPool(nProcesses)
        self.branchArg = branch
        self.perRepoArgs = perRepoArgs
        self.globalArgs = globalArgs
        self.launchTuple = listOfRepoBranchArgTuples

        
    def launchFromWorkspaceDir(self, handleMRE=None):
        cwd = os.getcwd()
        os.chdir(workspaceDir())
        repos = []
        branches = []
        argLists = self.perRepoArgs
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()
        currentBranch = git.currentBranch() if not self.branchArg else self.branchArg
        
        if self.launchTuple is not None:
            repos = [os.path.abspath(x[0]) for x in self.launchTuple]
            branches = [x[1] for x in self.launchTuple]
            self.perRepoArgs = [x[2] for x in self.launchTuple]
        else:
            if self.runSubprojects:
                activeSubprojects =  grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
                repos = repos + [os.path.abspath(sub) for sub in activeSubprojects]
                branches = branches + [currentBranch for x in activeSubprojects]
            if self.runSubmodules:
                activeSubmodules = git.getActiveSubmodules()
                repos = repos + [os.path.abspath(r) for r in activeSubmodules]
                subPubMap = config.getMapping("workspace", "submodulepublicmappings")
                submoduleBranch =  subPubMap[currentBranch] if currentBranch in publicBranches else currentBranch
                branches = branches + [ submoduleBranch for x in activeSubmodules ]
            if self.runOuter:
                repos.append(workspaceDir())
                branches.append(currentBranch)
            if not self.perRepoArgs:
                if not self.globalArgs:
                    
                    self.perRepoArgs = [[] for x in repos]
                else:
                    self.perRepoArgs = [self.globalArgs for x in repos]
        
        # run the first entry first so that things like logging in to the project's server happen up front
        retvals = []
        if len(repos) > 0:
            retvals.append(runCommandOnRepoBranch((repos[0], branches[0], self.lmbda, self.perRepoArgs[0])))
        if len(repos) > 1:            
            retvals = retvals + self.pool.map(runCommandOnRepoBranch, [(repo, branch, self.lmbda, arg) for repo, branch, arg in zip(repos[1:], branches[1:], self.perRepoArgs[1:])])
        os.chdir(cwd)
        self.pool.close()
        MRE = MultiRepoException()
        for val in zip(retvals, repos, branches, self.perRepoArgs):
            if isinstance(val[0], Exception):
                MRE.addException(val[0], val[1], val[2], val[3])
        if MRE.hasException():
            if handleMRE:
                handleMRE(MRE)
            else:
                raise MRE
        return retvals 

def grapeDir(): 
    return os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")


def GetCurrentBranch():
    output = git.gitcmd("rev-parse --abbrev-ref HEAD", "Error: Could not determine current  branch.")
    return output.strip()


def getDefaultName():
    if os.name == "nt":
        return os.getenv("USERNAME")
    else:
        return os.getenv("USER")


def getUserName(defaultName=getDefaultName(), service="LC"):
    return userInput("Enter %s User Name:" % service, defaultName)


def parseArgs(docstr, arguments, config):
    args = docopt(docstr, argv=arguments)
    for key in args:
        if type(args[key]) is str and ".grapeconfig." in args[key] and config is not None:
            tokens = args[key].split('.')
            args[key] = config.get(tokens[2].strip(), tokens[3].strip())
    return args


def printMsg(msg):
    global globalVerbosity
    if globalVerbosity > 0:    
        print("GRAPE: %s" % msg)


# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATEMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message, default=None):
    print("\n" + message)
    if default is "" or default is None:
        return raw_input('==> ').strip()
    else:
        value = raw_input("(def: %s) ==> " % default).strip()
        if value == "":
            value = default
        if default.lower() == "y" or default.lower() == "n":
            if value.lower()[0] == "y":
                return True
            if value.lower()[0] == "n":
                return False
        return value


# writes a config file with default options
def writeDefaultConfig(filename):
    config = grapeConfig.GrapeConfigParser()
    grapeMenu.menu().setDefaultConfig(config)
    with open(filename, 'w') as f:
        config.write(f)

class NoWorkspaceDirException(Exception):
    def __init__(self, cwd=''):
        self.cwd = cwd
        if cwd:
            self.message = "No .git found in %s" % cwd
        else:
            self.message = "No .git found"
    

# return the path to the base level of the current workspace. (outermost git repo)
def workspaceDir(warnIfNotFound = True, throwIfNotFound=True): 
    cwd = os.getcwd()
    basedir = None

    # go until you're at the root (you don't have a head after splitting)
    while os.path.split(os.getcwd())[1]:
        if os.path.exists(os.path.join(os.getcwd(), ".git")): 
            basedir = os.getcwd()
        os.chdir(os.path.join(os.getcwd(), ".."))
    if not basedir and warnIfNotFound:
        print("GRAPE WARNING: expected to be in your workspace, no .git found")
    if not basedir and throwIfNotFound:
        raise NoWorkspaceDirException(cwd)
    os.chdir(cwd)
    return basedir

def isWorkspaceClean():
    isClean = git.isWorkingDirectoryClean()
    activeNestedSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
    base = workspaceDir()
    cwd = os.getcwd()
    for sub in activeNestedSubprojects:
        if not isClean:
            break
        os.chdir(os.path.join(base, sub))
        isClean = isClean and git.isWorkingDirectoryClean()
    os.chdir(cwd)
    return isClean

def getActiveSubprojects():
    return git.getActiveSubmodules() + grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()

def getModifiedSubprojects():
    return git.getModifiedSubmodules() + grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes()


# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec(): 
    if os.name == "nt":
        winpath = os.path.join(os.path.dirname(__file__), "..", "grape.py")
        return "c:/Python27/python.exe " + winpath.replace("\\", "/")
    else:
        return os.path.join(os.path.dirname(__file__), "..", "grape")

# Takes a URL and returns a hard path for it
def parseSubprojectRemoteURL(url): 
    path = url.strip().split('/')
    if "https:" == path[0] or "ssh:" == path[0] or "" == path[0]:
        return url      #Already a hard path

    # We have a relative path so start the remote origin URL
    originURL = git.config("--get remote.origin.url").strip().split('/')

    #Now parse path and modify originURL to make a hard path
    for p in path:
        if p == ".." and len(originURL) > 0:
            originURL.pop()
        elif p == ".":
            pass
        else:
            originURL.append(p)

    return '/'.join(originURL)


# returns the user's home directory: 
def getHomeDirectory(): 
    if os.name == "nt":
        home = os.environ["USERPROFILE"]
    else:
        home = os.environ["HOME"]
    return home

from contextlib import contextmanager

@contextmanager
def cd(path): 
    old_dir   =   os.getcwd() 
    os.chdir(path) 
    try: 
        yield 
    finally:
        os.chdir(old_dir)