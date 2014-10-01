import os
import subprocess
import utility
import ConfigParser
import grapeConfig


class GrapeGitError(Exception):
    def __init__(self, errmsg, returnCode, gitOutput, gitCommand, quiet=False, cwd=os.getcwd()):
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        self.cwd = cwd
        if not quiet:
            print "When executing %s,Error %d raised with msg: %s \n %s" % (self.gitCommand, self.code, self.msg,
                                                                            self.gitOutput)


def gitcmd(cmd, errmsg, quiet=False):
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
        _cmd = "\"C:\\Program Files (x86)\\Git\\bin\\git.exe\" %s" % cmd
    else:
        _cmd = "git %s" % cmd
    if quiet:
        verbose = 0
    else:
        verbose = 2
    cwd = os.getcwd()
    process = utility.executeSubProcess(_cmd, cwd, subprocess.PIPE, verbose=verbose)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s " % errmsg, process.returncode, process.output, _cmd, quiet=quiet, cwd=cwd)
    return process.output.strip()


def add(filedescription, quiet=False):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription, quiet=quiet)


def baseDir(quiet=True):
    unixStylePath = gitcmd("rev-parse --show-toplevel", "Could not locate base directory", quiet=quiet)
    path = utility.makePathPortable(unixStylePath)
    return path


def branch(argstr="", quiet=False):
    return gitcmd("branch %s" % argstr, "Could not list branches", quiet)


def branchPrefix(branchName):
    return branchName.split('/')[0]


def branchUpToDateWith(branchName, targetBranch, quiet=True):
    allUpToDateBranches = gitcmd("branch -a --contains %s" % targetBranch, "branch contains failed", quiet=quiet)
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


def bundle(argstr, quiet=False):
    return gitcmd("bundle %s" % argstr, "Bundle failed", quiet=quiet)


def checkout(argstr, quiet=False):
    return gitcmd("checkout %s" % argstr, "Checkout failed", quiet=quiet)


def clone(argstr):
    try:
        return gitcmd("clone %s" % argstr, "Clone failed")
    except GrapeGitError as e:
        if e.code == 128:
            print ("GRAPE: WARNING: clone failed due to connectivity issues.")
            return e.gitOutput
        else:
            raise e


def commit(argstr):
    return gitcmd("commit %s" % argstr, "Commit failed")


def commitDescription(committish, quiet=True):
    return gitcmd("log --oneline %s^1..%s" % (committish, committish),
                  "commitDescription failed", quiet=quiet)


def config(argstr, arg2=None, quiet=False):
    if arg2 is not None:
        return gitcmd('config %s "%s"' % (argstr, arg2), "Config failed", quiet=quiet)
    else:
        return gitcmd('config %s ' % argstr, "Config failed", quiet=quiet)


def conflictedFiles(quiet=True):
    fileStr = diff("--name-only --diff-filter=U", quiet=quiet).strip()
    lines = fileStr.split('\n') if fileStr else []
    return lines


def currentBranch(quiet=True):
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch", quiet=quiet)


def describe(argstr="", quiet=False):
    return gitcmd("describe %s" % argstr, "could not describe commit", quiet=quiet)


def diff(argstr, quiet=False):
    return gitcmd("diff %s" % argstr, "could not perform diff", quiet=quiet)


def fetch(repo="", branchArg="", quiet=True):
    try:
        return gitcmd("fetch %s %s" % (repo, branchArg), "Fetch failed", quiet=quiet)
    except GrapeGitError as e:
        if e.code == 128:
            if not quiet:
                print ("GRAPE: WARNING: Fetch failed due to connectivity issues.")
            return e.gitOutput
        else:
            raise e


def getActiveSubmodules(quiet=True):

    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"", quiet)
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"", quiet)
    submoduleList = [] if not submoduleList else submoduleList.split('\n')
    return submoduleList


def getAllSubmodules(quiet=True):
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


def getModifiedSubmodules(branch1="", branch2="", quiet=True):
    cwd = os.getcwd()
    base = baseDir()
    os.chdir(base)
    submodules = getActiveSubmodules(quiet=quiet)
    # if there are no submodules, then return the empty list
    if len(submodules) == 0 or (len(submodules) ==1 and not submodules[0]):
        return [] 
    submodulesString = ' '.join(submodules)
    modifiedSubmodules = diff("--name-only %s %s -- %s" % (branch1, branch2,  submodulesString),
                              quiet=quiet).split('\n')
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
    if os.path.isdir(gitPath):
        return gitPath
    elif os.path.isfile(gitPath):
        with open(gitPath) as f:
            line = f.read()
            words = line.split()
            if words[0] == 'gitdir:':
                relUnixPath = words[1]
                return utility.makePathPortable(relUnixPath)
            else:
                raise GrapeGitError("print .git file does not have gitdir: prefix as expected", 1, "", "grape gitDir()")


def hasBranch(b):
    branches = branch(quiet=True).split()
    return b in branches


def isWorkingDirectoryClean():
    statusOutput = status("-u")
    return "nothing to commit" in statusOutput and "working directory clean" in statusOutput and\
           "conflict" not in statusOutput


def log(args=""):
    return gitcmd("log %s" % args, "git log failed")


def merge(args, quiet=False):
    return gitcmd("merge %s" % args, "merge failed", quiet=quiet)


def mergeAbort():
    return gitcmd("merge --abort", "Could not determine top level git directory.")


def numberCommitsSince(commitStr):
    strCount = gitcmd("rev-list --count %s..HEAD" % commitStr, "Rev-list failed")
    return int(strCount)


def numberCommitsSinceRoot():
    root = gitcmd("rev-list --max-parents=0 HEAD", "rev-list failed")
    return numberCommitsSince(root)


def pull(args, quiet=False):
    try:
        return gitcmd("pull %s" % args, "Pull failed", quiet=quiet)
    except GrapeGitError as e:
        if e.code == 128:
            print ("GRAPE: WARNING: Pull failed due to connectivity issues.")
            return e.gitOutput
        else:
            raise e


def push(args, quiet=False):
    try:
        return gitcmd("push %s" % args, "Push failed", quiet=quiet)
    except GrapeGitError as e:
        if e.code == 128:
            print ("GRAPE: WARNING: Push failed due to connectivity issues.")
            return e.gitOutput
        else:
            raise e


def rebase(args, quiet=False):
    return gitcmd("rebase %s" % args, "Rebase failed", quiet=quiet)


def revert(args, quiet=False):
    return gitcmd("revert %s" % args, "Revert failed", quiet=quiet)


def safeForceBranchToOriginRef(branchToSync, quiet=True):
    # first, check to see that branch exists
    branchExists = False
    remoteRefExists = False
    branches = branch("-a", quiet=quiet).split("\n")
    remoteRef = "remotes/origin/%s" % branchToSync
    for b in branches:
        b = b.replace('*', '')
        branchExists = branchExists or b.strip() == branchToSync.strip()
        remoteRefExists = remoteRefExists or b.strip() == remoteRef.strip()
        if branchExists and remoteRefExists:
            continue

    if branchExists and not remoteRefExists:
        print("origin does not have branch %s" % branchToSync)
        return False
    if branchExists and remoteRefExists:
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef, branchToSync, quiet=quiet)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync, remoteRef, quiet=quiet)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote:
            if branchToSync == currentBranch(quiet=quiet):
                print("Current branch %s is out of date with origin. Pulling new changes." % branchToSync)
                pull("origin %s" % branchToSync)
            else:
                branch("-f %s %s" % (branchToSync, remoteRef))
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote:
            return True
        else:
            return False
    if not branchExists and remoteRefExists:
        print("local branch did not exist. Creating %s off of %s now. " % (branchToSync, remoteRef))
        branch("%s %s" % (branchToSync, remoteRef), quiet=True)
        return True


def shortSHA(branchName="HEAD", quiet=True):
    return gitcmd("rev-parse --short %s" % branchName, "rev-parse of HEAD failed!", quiet=quiet)


def SHA(branchName="HEAD", quiet=True):
    return gitcmd("rev-parse %s" % branchName, "rev-parse of HEAD failed!", quiet=quiet)


def showRemote():

    try:
        return gitcmd("remote show origin", "unable to show remote")
    except GrapeGitError as e:
        if e.code == 128:
            print ("GRAPE: WARNING: git remote failed due to connectivity issues.")
            return e.gitOutput
        else:
            raise e


def status(argstr="", quiet=False):
    return gitcmd("status %s" % argstr, "git status failed for some reason", quiet=quiet)


def submodule(argstr, quiet=False):
    return gitcmd("submodule %s" % argstr, "git submodule %s failed" % argstr, quiet=quiet)


def subtree(argstr, quiet=False):
    return gitcmd("subtree %s" % argstr, "git subtree %s failed - maybe subtree isn't installed on your system?",
                  quiet=quiet)


def tag(argstr):
    return gitcmd("tag %s" % argstr, "git tag %s failed" % argstr)


def version():
    return gitcmd("version", "")
