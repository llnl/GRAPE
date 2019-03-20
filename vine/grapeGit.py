"""GRAPE's git utility logic across multiple repositories."""
import os
import re
import shutil
import ConfigParser
import StringIO
import grape_errors
import global_state


def gitcmd(cmd, errmsg):
    import config_parser_global

    _cmd = None
    try:
        cnfg = config_parser_global.grapeConfig()
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
    process = global_state.executeSubProcess(_cmd, cwd, verbose=-1)
    if process.returncode != 0:
        raise grape_errors.GrapeGitError("Error: %s " % errmsg, process.returncode, process.output, _cmd, cwd=cwd)
    return process.output.strip()


def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)


def baseDir():
    unixStylePath = gitcmd("rev-parse --show-toplevel", "Could not locate base directory")
    path = makePathPortable(unixStylePath)
    return path

def allBranches():
    return branch("-a").replace("*",' ').replace(" ",'').split()

def remoteBranches():
    return branch("-r").replace(" ", '').split()

def branch(argstr=""):
    return gitcmd("branch %s" % argstr, "Could not execute git branch command")


def branchPrefix(branchName):
    return branchName.split('/')[0]


def branchUpToDateWith(branchName, targetBranch):
    try:
        allUpToDateBranches = gitcmd("branch -a --contains %s" % targetBranch, "branch contains failed")
    except grape_errors.GrapeGitError as e:
        # Don't fail if the only issue is a dangling reference for origin/HEAD.
        allUpToDateBranches = e.gitOutput
        allUpToDateBranches = allUpToDateBranches.replace("error: branch 'origin/HEAD' does not point at a commit\n","")
        allUpToDateBranches = allUpToDateBranches.replace("error: some refs could not be read\n","")
        if "error: " in allUpToDateBranches:
            raise e
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
    except grape_errors.GrapeGitError as e:
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
    except grape_errors.GrapeGitError as e:
        if "unknown revision" in e.gitOutput:
            try:
                descr = gitcmd("log --oneline %s" % committish, "commitDescription failed")
            except grape_errors.GrapeGitError as e:
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
    except grape_errors.GrapeGitError as e:
        if e.commError:
            # fetch can sometimes hang up when it can't find the remote, resulting in
            # a spurious comm error.  Catch that here.
            if "fatal: Couldn't find remote ref" in e.gitOutput:
                raise e
            if warnOnCommError:
                global_state.printMsg("WARNING: could not fetch due to communication error.")
            if raiseOnCommError:
                raise e
            else:
                return e.gitOutput
        else:
            raise e


def getActiveSubmodules(ws_dir):
    cwd = os.getcwd()
    os.chdir(ws_dir)
    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"")
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"")
    submoduleList = [] if not submoduleList else submoduleList.split('\n')
    submoduleList = [x.strip() for x in submoduleList]
    # ignore any submodules that are not in .gitmodules
    submoduleList = [x for x in submoduleList if not x.startswith("fatal: no submodule mapping found in .gitmodules for path")]
    os.chdir(cwd)
    return submoduleList


# Remove any active submodules that are not found in gitmodules
def fixActiveSubmodules(ws_dir, user_input_func):
    cwd = os.getcwd()
    os.chdir(ws_dir)
    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"")
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"")
    submoduleList = [] if not submoduleList else submoduleList.split('\n')
    submoduleList = [x.strip() for x in submoduleList]
    pattern = re.compile("fatal: no submodule mapping found in .gitmodules for path '([^']+)'")
    submoduleFixed = False
    for output in submoduleList:
        match = pattern.match(output)
        if match:
            submoduleFixed = True
            sub = match.group(1)
            # remove from index, if staged
            rm("--ignore-unmatch --cached %s" % sub)
            # remove from repo, if present
            rm("--ignore-unmatch %s" % sub)
            if os.path.exists(os.path.join(ws_dir, sub)):
                delete = user_input_func("%s is no longer part of the workspace.  Would you like to delete it?" % sub , 'y')
#                delete = utility.userInput("%s is no longer part of the workspace.  Would you like to delete it?" % sub , 'y')
                if delete:
                    shutil.rmtree(os.path.join(ws_dir, sub))
    os.chdir(cwd)
    return submoduleFixed

def getAllSubmodules():
    subconfig = ConfigParser.ConfigParser()
    try:
        subconfig.read(os.path.join(baseDir(), ".gitmodules"))
    except ConfigParser.ParsingError:
        # this is guaranteed to happen due to .gitmodules format incompatibility, but it does
        # read section names in successfully, which is all we need
        pass
    sections = subconfig.sections()
    submodules = []
    for s in sections:
        submodules.append(s.split()[1].split('"')[1])
    return submodules

def getAllSubmoduleURLMap():
    subconfig = ConfigParser.ConfigParser()
    fp = StringIO.StringIO('\n'.join(line.strip() for line in open(os.path.join(baseDir(), ".gitmodules"))))
    subconfig.readfp(fp)
    sections = subconfig.sections()
    submodules = {}
    for s in sections:
        submodules[subconfig.get(s,"path")] = subconfig.get(s, "url")
    return submodules


def getModifiedSubmodules(ws_dir, branch1="", branch2="", includeAdded=False):
    cwd = os.getcwd()
    os.chdir(ws_dir)
    submodules = getAllSubmodules()
    # if there are no submodules, then return the empty list
    if len(submodules) == 0 or (len(submodules) ==1 and not submodules[0]):
        return []
    submodulesString = ' '.join(submodules)
    try:
        modifiedSubmodules = diff("--name-status %s %s -- %s" %
                                  (branch1, branch2,  submodulesString)).split('\n')
        if includeAdded:
            modifiedSubmodules = [sub.lstrip('AM \t') for sub in modifiedSubmodules if sub.startswith('M') or sub.startswith('A') ]
        else:
            # only include submodules that are in both branches
            modifiedSubmodules = [sub.lstrip('M \t') for sub in modifiedSubmodules if sub.startswith('M')]
    except grape_errors.GrapeGitError as e:
        if "bad revision" in e.gitOutput:
            global_state.printMsg("getModifiedSubmodules: requested difference between one or more branches that do not exist. Assuming no modifications.")
            return []
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


# Takes a URL and returns a hard path for it
def parseSubprojectRemoteURL(url):
    path = url.strip().split('/')
    if "https:" == path[0] or "ssh:" == path[0] or "" == path[0]:
        return url      #Already a hard path

    # We have a relative path so start the remote origin URL
    originURL = config("--get remote.origin.url").strip().split('/')

    #Now parse path and modify originURL to make a hard path
    for p in path:
        if p == ".." and len(originURL) > 0:
            originURL.pop()
        elif p == ".":
            pass
        else:
            originURL.append(p)
    return '/'.join(originURL)


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
                toReturn = makePathPortable(relUnixPath)
            else:
                raise grape_errors.GrapeGitError("print .git file does not have gitdir: prefix as expected", 1, "", "grape gitDir()")
    return toReturn


def hasBranch(b):
    branches = branch().split()
    return b in branches


def isWorkingDirectoryClean(printOutput=False):
    statusOutput = status("-u --porcelain")
    toRet =  len(statusOutput.strip()) == 0
    if (printOutput and not toRet):
        print os.getcwd()+":"
        print statusOutput
    return toRet



def log(args=""):
    return gitcmd("log %s" % args, "git log failed")


#ensures the path string is windows compatibile if necessary
def makePathPortable(path):
    if os.name == "nt":
        newPath = path.replace("/", "\\")
    else:
        newPath = path
    return newPath


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
    except grape_errors.GrapeGitError as e:
        if e.commError:
            global_state.printMsg("WARNING: Pull failed due to connectivity issues.")
            if throwOnFail:
                raise e
            else:
                return e.gitOutput

        else:
            raise e


def push(args, throwOnFail = False):
    try:
        return gitcmd("push --porcelain %s" % args, "Push failed")
    except grape_errors.GrapeGitError as e:
        if e.commError:
            global_state.printMsg("WARNING: Push failed due to connectivity issues.")
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
        global_state.printMsg("origin does not have branch %s" % branchToSync)
        return False
    if branchExists and remoteRefExists:
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef, branchToSync)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync, remoteRef)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote:
            if branchToSync == currentBranch():
                global_state.printMsg("Current branch %s is out of date with origin. Pulling new changes." % branchToSync)
                try:
                    pull("origin %s" % branchToSync, throwOnFail=True)
                except:
                    global_state.printMsg("Can't pull %s. Aborting...")
                    return False
            else:
                branch("-f %s %s" % (branchToSync, remoteRef))
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote:
            return True
        else:
            return False
    if not branchExists and remoteRefExists:
        global_state.printMsg("local branch did not exist. Creating %s off of %s now. " % (branchToSync, remoteRef))
        branch("%s %s" % (branchToSync, remoteRef))
        return True

def SHA(branchName="HEAD"):
    return gitcmd("rev-parse %s" % branchName, "rev-parse of %s failed!" % branchName)

def shortSHA(branchName="HEAD"):
    return gitcmd("rev-parse --short %s" % branchName, "rev-parse of %s failed!" % branchName)

def show(argStr):
    try:
        return gitcmd("show %s" % argStr, "git show failed with argstr %s" % argStr)
    except grape_errors.GrapeGitError as e:
        if "Path" in e.gitOutput and "does not exist in" in e.gitOutput:
            return ""

def showRemote():

    try:
        return gitcmd("remote show origin", "unable to show remote")
    except grape_errors.GrapeGitError as e:
        if e.code == 128:
            global_state.printMsg("WARNING: %s failed. Ignoring..." % e.gitCommand)
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
