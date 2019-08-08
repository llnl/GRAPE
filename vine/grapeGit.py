"""GRAPE's git utility logic across a single repository."""
from contextlib import contextmanager
import configparser
import io
import logging
import os
import re
import shutil
from vine import grape_errors
from vine import vine_logging
from vine import vine_subprocess


GRAPE_CONFIG = '.grapeconfig'


def gitcmd(cmd, errmsg):
    from vine import config_parser_global

    cnfg = config_parser_global.grapeConfig()
    if cnfg.has_section('git') and cnfg.has_option("executable"):
        _cmd = cnfg.get("git", "executable")
        _cmd += f" {cmd}"
    elif os.name == "nt":
        git_path = os.path.join('C:', os.path.sep, 'Program Files',
                                'Git', 'bin', 'git.exe')
        _cmd = f"\"{git_path}\" {cmd}"
    else:
        _cmd = f"git {cmd}"

    cwd = os.getcwd()
    completed_process = vine_subprocess.executeSubProcess(_cmd,
                                                          workingDirectory=cwd)
    stdout_output = completed_process.stdout.decode()
    stderr_output = completed_process.stderr.decode()
    process_output = '\n'.join([stdout_output, stderr_output]).strip()
    if completed_process.returncode != 0:
        raise grape_errors.GrapeGitError(f"Error: {errmsg}", completed_process.returncode, process_output, _cmd, cwd=cwd)
    return process_output


def add(filedescription):
    return gitcmd(f"add {filedescription}", f"Could not add {filedescription}")


def baseDir():
    """Returns path in an OS (non-git) format."""
    git_formatted_path = gitcmd("rev-parse --show-toplevel", "Could not locate base directory")
    os_formatted_path = gitPathToOsPath(git_formatted_path)
    return os_formatted_path

def allBranches():
    return branch("-a").replace("*",' ').replace(" ",'').split()

def remoteBranches():
    return branch("-r").replace(" ", '').split()

def branch(argstr=""):
    return gitcmd(f"branch {argstr}", "Could not execute git branch command")


def branchPrefix(branchName):
    return branchName.split('/')[0]


def branchUpToDateWith(branchName, targetBranch):
    """Provided branch names should delimited by '/'.

    For Windows portability, see 'join_list_as_git_path()'.
    """
    try:
        allUpToDateBranches = gitcmd(f"branch -a --contains {targetBranch}",
                                     "branch contains failed")
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
    return gitcmd(f"bundle {argstr}", "Bundle failed")


def checkout(argstr):
    return gitcmd(f"checkout {argstr}", "Checkout failed")


def clone(argstr):
    try:
        return gitcmd(f"clone {argstr}", "Clone failed")
    except grape_errors.GrapeGitError as e:
        if "already exists and is not an empty directory" in e.gitOutput:
            raise e
        if e.commError:
            logging.warning("GRAPE: clone failed due to connectivity issues.")
            return e.gitOutput
        else:
            logging.warning("GRAPE: Clone failed. Maybe you ran out of disk space?")
            logging.warning(e.gitOutput)
            raise e


def commit(argstr):
    return gitcmd(f"commit {argstr}", "Commit failed")


def commitDescription(committish):

    try:
        descr = gitcmd(f"log --oneline {committish}^1..{committish}",
                       "commitDescription failed")
    # handle the case when this is called on a 1-commit-long history (occurs mostly in unit testing)
    except grape_errors.GrapeGitError as e:
        if "unknown revision" in e.gitOutput:
            try:
                descr = gitcmd(f"log --oneline {committish}",
                               "commitDescription failed")
            except grape_errors.GrapeGitError as e:
                raise e
    return descr

def config(argstr, arg2=None):
    if arg2 is not None:
        return gitcmd(f'config {argstr} "{arg2}"', "Config failed")
    else:
        return gitcmd(f'config {argstr} ', "Config failed")


def conflictedFiles():
    fileStr = diff("--name-only --diff-filter=U").strip()
    lines = fileStr.split('\n') if fileStr else []
    return lines


def currentBranch():
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch")


def describe(argstr=""):
    return gitcmd(f"describe {argstr}", "could not describe commit")


def diff(argstr):
    return gitcmd(f"diff {argstr}", "could not perform diff")


def fetch(repo="", branchArg="", raiseOnCommError=False, warnOnCommError=False):
    try:
        return gitcmd(f"fetch {repo} {branchArg}", "Fetch failed")
    except grape_errors.GrapeGitError as e:
        if e.commError:
            # fetch can sometimes hang up when it can't find the remote, resulting in
            # a spurious comm error.  Catch that here.
            if "fatal: Couldn't find remote ref" in e.gitOutput:
                raise e
            if warnOnCommError:
                logging.warning("WARNING: could not fetch due to communication error.")
            if raiseOnCommError:
                raise e
            else:
                return e.gitOutput
        else:
            raise e


def getActiveSubmodules(ws_dir):
    with cd(ws_dir):
        if os.name == "nt":
            submoduleList = submodule("foreach --quiet \"echo $path\"")
        else:
            submoduleList = submodule("foreach --quiet \"echo \$path\"")
        submoduleList = [] if not submoduleList else submoduleList.split('\n')
        submoduleList = [x.strip() for x in submoduleList]
        # ignore any submodules that are not in .gitmodules
        submoduleList = [x for x in submoduleList if not x.startswith("fatal: no submodule mapping found in .gitmodules for path")]
    return submoduleList


# Remove any active submodules that are not found in gitmodules
def fixActiveSubmodules(ws_dir, user_input_func):
    with cd(ws_dir):
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
                rm(f"--ignore-unmatch --cached {sub}")
                # remove from repo, if present
                rm(f"--ignore-unmatch {sub}")
                if os.path.exists(os.path.join(ws_dir, sub)):
                    delete = user_input_func(f"{sub} is no longer part of the " +
                                             "workspace.  Would you like to " +
                                             "delete it?", 'y')
                    if delete:
                        shutil.rmtree(os.path.join(ws_dir, sub))
    return submoduleFixed

def getAllSubmodules():
    subconfig = configparser.ConfigParser()
    try:
        subconfig.read(os.path.join(baseDir(), ".gitmodules"))
    except configparser.ParsingError:
        # this is guaranteed to happen due to .gitmodules format incompatibility, but it does
        # read section names in successfully, which is all we need
        pass
    sections = subconfig.sections()
    submodules = []
    for s in sections:
        submodules.append(s.split()[1].split('"')[1])
    return submodules

def getAllSubmoduleURLMap():
    subconfig = configparser.ConfigParser()
    fp = io.StringIO('\n'.join(line.strip() for line in io.open(os.path.join(baseDir(), ".gitmodules"))))
    subconfig.read_file(fp)
    fp.close()
    sections = subconfig.sections()
    submodules = {}
    for s in sections:
        submodules[subconfig.get(s,"path")] = subconfig.get(s, "url")
    return submodules


def getModifiedSubmodules(ws_dir, branch1="", branch2="", includeAdded=False):
    with cd(ws_dir):
        submodules = getAllSubmodules()
        # if there are no submodules, then return the empty list
        if len(submodules) == 0 or (len(submodules) ==1 and not submodules[0]):
            return []
        submodulesString = ' '.join(submodules)
        try:
            modifiedSubmodules = diff(f"--name-status {branch1} {branch2} -- " +
                                      f"{submodulesString}").split('\n')
            if includeAdded:
                modifiedSubmodules = [sub.lstrip('AM \t') for sub in modifiedSubmodules if sub.startswith('M') or sub.startswith('A') ]
            else:
                # only include submodules that are in both branches
                modifiedSubmodules = [sub.lstrip('M \t') for sub in modifiedSubmodules if sub.startswith('M')]
        except grape_errors.GrapeGitError as e:
            if "bad revision" in e.gitOutput:
                logging.warning("getModifiedSubmodules: requested difference between one or more branches that do not exist. Assuming no modifications.")
                return []

        # make sure everything in modifiedSubmodules is in the original list of submodules
        # (this can not be the case if the module existed as a regular directory / subtree in the other branch,
        #  in which case the diff command will list the contents of the directory as opposed to just the submodule)
        verifiedSubmodules = []
        for s in modifiedSubmodules:
            if s in submodules:
                verifiedSubmodules.append(s)

    return verifiedSubmodules


# Takes a URL and returns a hard path for it
def parseSubprojectRemoteURL(url):
    URL_PATH_SEP = '/'
    path = url.replace('\\', URL_PATH_SEP)
    path = path.strip().split(URL_PATH_SEP)
    if path[0] in ["https:", "ssh:", "C:", ""]:
        return url      #Already a hard path

    # We have a relative path so start the remote origin URL
    originURL = config("--get remote.origin.url").strip().split(os.path.sep)

    #Now parse path and modify originURL to make a hard path
    for p in path:
        if p == os.path.pardir and len(originURL) > 0:
            originURL.pop()
        elif p == ".":
            pass
        else:
            originURL.append(p)
    return os.path.join(*originURL)


def gitDir():
    base = str(baseDir())
    gitPath = os.path.join(base, ".git")
    toReturn = None
    if os.path.isdir(gitPath):
        toReturn = gitPath
    elif os.path.isfile(gitPath):
        with io.open(gitPath) as f:
            line = f.read()
            words = line.split()
            if words[0] == 'gitdir:':
                relUnixPath = words[1]
                toReturn = gitPathToOsPath(relUnixPath)
            else:
                raise grape_errors.GrapeGitError("print .git file does not have gitdir: prefix as expected", 1, "", "grape gitDir()")
    return toReturn


def hasBranch(b):
    branches = branch().split()
    return b in branches


def isWorkingDirectoryClean(printOutput=False):
    statusOutput = status("-u --porcelain")
    toRet =  len(statusOutput.strip()) == 0
    if printOutput and not toRet:
        logging.info(f"{os.getcwd()}:")
        logging.info(statusOutput)
    return toRet



def log(args=""):
    return gitcmd(f"log {args}", "git log failed")


def mv(args):
    return gitcmd(f"mv {args}", "mv failed")

def mv(args):
    return gitcmd("mv %s" % args, "mv failed")

def join_list_as_git_path(path):
    """Returns a path delimited by '/' as Git would, regardless of OS.

    Use in place of 'os.path.join()' when it is necessary to compare paths
    returned by Git commands. Git paths do not match with Windows OS paths
    by default, hence the Windows path substitution of '/' for '\\'.
    Do not use when passing paths into Git,
    only use when comparing paths output from Git.
    """
    if isinstance(path, list):
        if os.name == "nt":
            return os.path.altsep.join(path)
        return os.path.join(*path)

#ensures the path string is windows compatibile if necessary
def gitPathToOsPath(path):
    """
    Converts Git's default '/' delimited branch paths to an OS based format.
    """
    if os.name == "nt":
        return path.replace(os.path.altsep, os.path.sep)
    return path


def merge(args):
    return gitcmd(f"merge {args}", "merge failed")


def mergeAbort():
    return gitcmd("merge --abort", "Could not determine top level git directory.")


def numberCommitsSince(commitStr):
    strCount = gitcmd(f"rev-list --count {commitStr}..HEAD", "Rev-list failed")
    return int(strCount)


def numberCommitsSinceRoot():
    root = gitcmd("rev-list --max-parents=0 HEAD", "rev-list failed")
    return numberCommitsSince(root)


def pull(args, throwOnFail=False):
    try:
        return gitcmd(f"pull {args}", "Pull failed")
    except grape_errors.GrapeGitError as e:
        if e.commError:
            logging.warning("WARNING: Pull failed due to connectivity issues.")
            if throwOnFail:
                raise e
            else:
                return e.gitOutput

        else:
            raise e


def push(args, throwOnFail = False):
    try:
        return gitcmd(f"push --porcelain {args}", "Push failed")
    except grape_errors.GrapeGitError as e:
        if e.commError:
            logging.warning("WARNING: Push failed due to connectivity issues.")
            if throwOnFail:
                raise e
            else:
                return e.gitOutput
        else:
            raise e


def rebase(args):
    return gitcmd(f"rebase {args}", "Rebase failed")

def reset(args):
    return gitcmd(f"reset {args}", "Reset failed")

def revert(args):
    return gitcmd(f"revert {args}", "Revert failed")

def rm(args):
    return gitcmd(f"rm {args}", "Remove failed")


def safeForceBranchToOriginRef(branchToSync):
    # first, check to see that branch exists
    branchExists = False
    remoteRefExists = False
    branches = branch("-a").split("\n")
    remoteRef = join_list_as_git_path(['remotes', 'origin', branchToSync])
    for b in branches:
        b = b.replace('*', '')
        branchExists = branchExists or b.strip() == branchToSync.strip()
        remoteRefExists = remoteRefExists or b.strip() == remoteRef.strip()
        if branchExists and remoteRefExists:
            continue

    if branchExists and not remoteRefExists:
        logging.info(f"origin does not have branch {branchToSync}")
        return False
    if branchExists and remoteRefExists:
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef, branchToSync)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync, remoteRef)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote:
            if branchToSync == currentBranch():
                logging.info(f"Current branch {branchToSync} is out of date" +
                             " with origin. Pulling new changes.")
                try:
                    pull(f"origin {branchToSync}", throwOnFail=True)
                except:
                    logging.info(f"Can't pull {branchToSync}. Aborting...")
                    return False
            else:
                branch(f"-f {branchToSync} {remoteRef}")
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote:
            return True
        else:
            return False
    if not branchExists and remoteRefExists:
        logging.info(f"local branch did not exist. Creating {branchToSync} " +
                     f"off of {remoteRef} now. ")
        branch(f"{branchToSync} {remoteRef}")
        return True

def SHA(branchName="HEAD"):
    return gitcmd(f"rev-parse {branchName}",
                  f"rev-parse of {branchName} failed!")

def shortSHA(branchName="HEAD"):
    return gitcmd(f"rev-parse --short {branchName}",
                  f"rev-parse of {branchName} failed!")

def show(argStr):
    try:
        return gitcmd(f"show {argStr}",
                      f"git show failed with argstr {argStr}")
    except grape_errors.GrapeGitError as e:
        if "Path" in e.gitOutput and "does not exist in" in e.gitOutput:
            return ""

def showRemote():

    try:
        return gitcmd("remote show origin", "unable to show remote")
    except grape_errors.GrapeGitError as e:
        if e.code == 128:
            logging.warning(f"WARNING: {e.gitCommand} failed. Ignoring...")
            return e.gitOutput
        else:
            raise e

def stash(argstr=""):
    return gitcmd(f"stash {argstr}", "git stash failed for some reason")

def status(argstr=""):
    return gitcmd(f"status {argstr}", "git status failed for some reason")


def submodule(argstr):
    return gitcmd(f"submodule {argstr}", f"git submodule {argstr} failed")


def subtree(argstr):
    return gitcmd(f"subtree {argstr}",
                  f"git subtree {argstr} failed - maybe subtree" +
                  " isn't installed on your system?")


def tag(argstr):
    return gitcmd(f"tag {argstr}", f"git tag {argstr} failed")


def version():
    return gitcmd("version", "")


@contextmanager
def cd(path):
    starting_dir = os.getcwd()
    if starting_dir == path:
        yield
        os.chdir(starting_dir)
    else:
        try:
            os.chdir(path)
            yield
        except OSError as e:
            print(f"GRAPE WARNING: in {os.getcwd()} : {e}")
            yield
        finally:
            os.chdir(starting_dir)
