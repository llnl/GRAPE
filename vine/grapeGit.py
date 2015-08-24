import os
import subprocess
import utility
import ConfigParser
import grapeConfig


class GrapeGitError(Exception):
    # arguments must be kept as keywords to allow pickling
    def __init__(self, errmsg='', returnCode=-1, gitOutput='', gitCommand='', cwd=os.getcwd()):
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        self.commError = True if \
            (self.code == 128 and "fatal: Could not read from remote" in self.gitOutput )  or \
            ("fatal: unable to access" in self.gitOutput) or \
            ("fatal: The remote end hung up unexpectedly" in self.gitOutput) \
            else False
        self.cwd = cwd
        
    def __getinitargs__(self):
        return (self.msg, self.code, self.gitOutput, self.gitCommand, self.cwd)
    
    def __str__(self):
        return "\nWORKING DIR: " + self.cwd +  "\nCODE: " + str(self.code) + '\nCMD: ' + self.gitCommand + '\nOUTPUT: ' + self.gitOutput 
               
        
    def __repr__(self):
        return self.__str__()
        


def gitcmd(cmd, errmsg):
    _cmd = None
    try:
        cnfg = grapeConfig.grapeConfig()
        _cmd = cnfg.get("git", "executable")
    except ConfigParser.NoOptionError:
        pass
    except ConfigParser.NoSectionError:
        pass
    if _cmd:
        _cmd += " %s" % cmd
    elif os.name == "nt":
        _cmd = "\"C:\\Program Files\\Git\\bin\\git.exe\" %s" % cmd
    else:
        _cmd = "git %s" % cmd

    cwd = os.getcwd()
    process = utility.executeSubProcess(_cmd, cwd, verbose=-1)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s " % errmsg, process.returncode, process.output, _cmd, cwd=cwd)
    return process.output.strip()


def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)


def baseDir():
    unixStylePath = gitcmd("rev-parse --show-toplevel", "Could not locate base directory")
    path = utility.makePathPortable(unixStylePath)
    return path

def allBranches():
    return branch("-a").replace("*",' ').replace(" ",'').split()

def branch(argstr=""):
    return gitcmd("branch %s" % argstr, "Could not execute git branch command")


def branchPrefix(branchName):
    return branchName.split('/')[0]


def branchUpToDateWith(branchName, targetBranch):
    allUpToDateBranches = gitcmd("branch -a --contains %s" % targetBranch, "branch contains failed")
    allUpToDateBranches = allUpToDateBranches.split("\n")
    upToDate = False
    for b in allUpToDateBranches:
        # remove the * prefix from the active branch
        cleanB = b.strip()
        if b[0] is '*':
            cleanB = b[1:].strip()
        upToDate = cleanB == branchName.strip()
        if upToDate:
            break
    return upToDate


def bundle(argstr):
    return gitcmd("bundle %s" % argstr, "Bundle failed")


def checkout(argstr):
    return gitcmd("checkout %s" % argstr, "Checkout failed")


def clone(argstr):
    try:
        return gitcmd("clone %s" % argstr, "Clone failed")
    except GrapeGitError as e:
        if "already exists and is not an empty directory" in e.gitOutput:
            raise e
        if e.commError:
            print ("GRAPE: WARNING: clone failed due to connectivity issues.")
            return e.gitOutput
        else:
            print ("GRAPE: Clone failed. Maybe you ran out of disk space?")
            print e.gitOutput
            raise e


def commit(argstr):
    return gitcmd("commit %s" % argstr, "Commit failed")


def commitDescription(committish):

    try:
        descr = gitcmd("log --oneline %s^1..%s" % (committish, committish),
                           "commitDescription failed")
    # handle the case when this is called on a 1-commit-long history (occurs mostly in unit testing)
    except GrapeGitError as e:
        if "unknown revision" in e.gitOutput:
            try:
                descr = gitcmd("log --oneline %s" % committish, "commitDescription failed")
            except GrapeGitError as e:
                raise e
    return descr

def config(argstr, arg2=None):
    if arg2 is not None:
        return gitcmd('config %s "%s"' % (argstr, arg2), "Config failed")
    else:
        return gitcmd('config %s ' % argstr, "Config failed")


def conflictedFiles():
    fileStr = diff("--name-only --diff-filter=U").strip()
    lines = fileStr.split('\n') if fileStr else []
    return lines


def currentBranch():
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch")


def describe(argstr=""):
    return gitcmd("describe %s" % argstr, "could not describe commit")


def diff(argstr):
    return gitcmd("diff %s" % argstr, "could not perform diff")


def fetch(repo="", branchArg="", raiseOnCommError=False, warnOnCommError=False):
    try:
        return gitcmd("fetch %s %s" % (repo, branchArg), "Fetch failed")
    except GrapeGitError as e:
        if e.commError:
            if warnOnCommError:
                utility.printMsg("WARNING: could not fetch due to communication error.")
            if raiseOnCommError:
                raise e
            else:
                return e.gitOutput
        else:
            raise e


def getActiveSubmodules():
    cwd = os.getcwd()
    wsDir = utility.workspaceDir()
    os.chdir(wsDir)
    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"")
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"")
    submoduleList = [] if not submoduleList else submoduleList.split('\n')
    submoduleList = [x.strip() for x in submoduleList]
    os.chdir(cwd)
    return submoduleList


def getAllSubmodules():
    subconfig = ConfigParser.ConfigParser()
    try:
        subconfig.read(os.path.join(baseDir(), ".gitmodules"))
    except ConfigParser.ParsingError:
        # this is guaranteed to happen due to .gitmodules format incompatibility, but it does
        # read section names in succussfully, which is all we need
        pass
    sections = subconfig.sections()
    submodules = []
    for s in sections:
        submodules.append(s.split()[1].split('"')[1])
    return submodules


def getModifiedSubmodules(branch1="", branch2=""):
    cwd = os.getcwd()
    wsDir = utility.workspaceDir()
    os.chdir(wsDir)
    submodules = getAllSubmodules()
    # if there are no submodules, then return the empty list
    if len(submodules) == 0 or (len(submodules) ==1 and not submodules[0]):
        return [] 
    submodulesString = ' '.join(submodules)
    modifiedSubmodules = diff("--name-only %s %s -- %s" % 
                              (branch1, branch2,  submodulesString)).split('\n')
    if len(modifiedSubmodules) == 1 and not modifiedSubmodules[0]:
        return []

    # make sure everything in modifiedSubmodules is in the original list of submodules
    # (this can not be the case if the module existed as a regular directory / subtree in the other branch,
    #  in which case the diff command will list the contents of the directory as opposed to just the submodule)
    verifiedSubmodules = []
    for s in modifiedSubmodules:
        if s in submodules:
            verifiedSubmodules.append(s)

    os.chdir(cwd)
    return verifiedSubmodules


def gitDir():
    base = baseDir()
    gitPath = os.path.join(base, ".git")
    toReturn = None
    if os.path.isdir(gitPath):
        toReturn = gitPath
    elif os.path.isfile(gitPath):
        with open(gitPath) as f:
            line = f.read()
            words = line.split()
            if words[0] == 'gitdir:':
                relUnixPath = words[1]
                toReturn = utility.makePathPortable(relUnixPath)   
            else:
                raise GrapeGitError("print .git file does not have gitdir: prefix as expected", 1, "", "grape gitDir()")
    return toReturn


def hasBranch(b):
    branches = branch().split()
    return b in branches


def isWorkingDirectoryClean():
    statusOutput = status("-u")
    return "nothing to commit" in statusOutput and "working directory clean" in statusOutput and\
           "conflict" not in statusOutput


def log(args=""):
    return gitcmd("log %s" % args, "git log failed")


def merge(args):
    return gitcmd("merge %s" % args, "merge failed")


def mergeAbort():
    return gitcmd("merge --abort", "Could not determine top level git directory.")


def numberCommitsSince(commitStr):
    strCount = gitcmd("rev-list --count %s..HEAD" % commitStr, "Rev-list failed")
    return int(strCount)


def numberCommitsSinceRoot():
    root = gitcmd("rev-list --max-parents=0 HEAD", "rev-list failed")
    return numberCommitsSince(root)


def pull(args, throwOnFail=False):
    try:
        return gitcmd("pull %s" % args, "Pull failed")
    except GrapeGitError as e:
        if e.commError:
            utility.printMsg("WARNING: Pull failed due to connectivity issues.")
            if throwOnFail: 
                raise e
            else:
                return e.gitOutput
        
        else:
            raise e


def push(args, throwOnFail = False):
    try:
        return gitcmd("push --porcelain %s" % args, "Push failed")
    except GrapeGitError as e:
        if e.commError:
            utility.printMsg("WARNING: Push failed due to connectivity issues.")
            if throwOnFail: 
                raise e
            else:
                return e.gitOutput
        else:
            raise e


def rebase(args):
    return gitcmd("rebase %s" % args, "Rebase failed")

def reset(args):
    return gitcmd("reset %s" % args, "Reset failed") 

def revert(args):
    return gitcmd("revert %s" % args, "Revert failed")

def rm(args):
    return gitcmd("rm %s" % args, "Remove failed")


def safeForceBranchToOriginRef(branchToSync):
    # first, check to see that branch exists
    branchExists = False
    remoteRefExists = False
    branches = branch("-a").split("\n")
    remoteRef = "remotes/origin/%s" % branchToSync
    for b in branches:
        b = b.replace('*', '')
        branchExists = branchExists or b.strip() == branchToSync.strip()
        remoteRefExists = remoteRefExists or b.strip() == remoteRef.strip()
        if branchExists and remoteRefExists:
            continue

    if branchExists and not remoteRefExists:
        utility.printMsg("origin does not have branch %s" % branchToSync)
        return False
    if branchExists and remoteRefExists:
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef, branchToSync)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync, remoteRef)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote:
            if branchToSync == currentBranch():
                utility.printMsg("Current branch %s is out of date with origin. Pulling new changes." % branchToSync)
                try:
                    pull("origin %s" % branchToSync, throwOnFail=True)
                except:
                    utility.printMsg("Can't pull %s. Aborting...")
                    return False
            else:
                branch("-f %s %s" % (branchToSync, remoteRef))
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote:
            return True
        else:
            return False
    if not branchExists and remoteRefExists:
        utility.printMsg("local branch did not exist. Creating %s off of %s now. " % (branchToSync, remoteRef))
        branch("%s %s" % (branchToSync, remoteRef))
        return True


def shortSHA(branchName="HEAD"):
    return gitcmd("rev-parse --short %s" % branchName, "rev-parse of %s failed!" % branchName)


def SHA(branchName="HEAD"):
    return gitcmd("rev-parse %s" % branchName, "rev-parse of %s failed!" % branchName)


def showRemote():

    try:
        return gitcmd("remote show origin", "unable to show remote")
    except GrapeGitError as e:
        if e.code == 128:
            utility.printMsg("WARNING: %s failed. Ignoring..." % e.gitCommand)
            return e.gitOutput
        else:
            raise e
 
def stash(argstr=""):
    return gitcmd("stash %s" % argstr, "git stash failed for some reason")

def status(argstr=""):
    return gitcmd("status %s" % argstr, "git status failed for some reason")


def submodule(argstr):
    return gitcmd("submodule %s" % argstr, "git submodule %s failed" % argstr)


def subtree(argstr):
    return gitcmd("subtree %s" % argstr, "git subtree %s failed - maybe subtree isn't installed on your system?")


def tag(argstr):
    return gitcmd("tag %s" % argstr, "git tag %s failed" % argstr)


def version():
    return gitcmd("version", "")
