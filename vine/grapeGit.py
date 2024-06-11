"""GRAPE's git utility logic across a single repository."""
import configparser
import io
import logging
import os
import re
import shutil
import tempfile
from posixpath import join as urljoin
from vine import grape_errors
from vine import vine_subprocess


GRAPE_CONFIG = '.grapeconfig'
GIT_VERY_VERBOSE = False
GRAPE_GIT_CONFIG_FLAGS = '-c feature.manyFiles=true -c checkout.workers=16'

def setConfigFlags(flags):
    global GRAPE_GIT_CONFIG_FLAGS
    GRAPE_GIT_CONFIG_FLAGS = flags

# Note that if capture_output is None, the return code and
# any errors are ignored.
def gitcmd(cmd, errmsg, *, execution_path, capture_output=True, debug_log_stdout=True):
    from vine import config_parser_global

    cnfg = config_parser_global.grapeConfig()
    if cnfg.has_section('git') and cnfg.has_option('git', 'executable'):
        _cmd = cnfg.get("git", "executable")
        _cmd += f" {GRAPE_GIT_CONFIG_FLAGS} {cmd}"
    elif os.name == "nt":
        git_path = os.path.join('C:', os.path.sep, 'Program Files',
                                'Git', 'bin', 'git.exe')
        _cmd = f"\"{git_path}\" {GRAPE_GIT_CONFIG_FLAGS} {cmd}"
    else:
        _cmd = f"git {GRAPE_GIT_CONFIG_FLAGS} {cmd}"

    completed_process = vine_subprocess.executeSubProcess(
        _cmd, working_dir=execution_path, capture_output=capture_output, debug_log_stdout=debug_log_stdout)

    if not capture_output:
        return

    stdout_output = completed_process.stdout.decode()
    stderr_output = completed_process.stderr.decode()
    process_output = '\n'.join([stdout_output, stderr_output]).strip()
    if completed_process.returncode != 0:
        raise grape_errors.GrapeGitError(
            f"Error: {errmsg}", completed_process.returncode, process_output,
            _cmd, cwd=execution_path)
    return process_output


def add(filedescription, *, execution_path):
    return gitcmd(f"add {filedescription}",
                  f"Could not add {filedescription}",
                  execution_path=execution_path)

def baseDir(*, execution_path):
    """Returns path in an OS (non-git) format."""
    logging.debug("Locating base directory.")
    git_formatted_path = gitcmd(
        "rev-parse --show-toplevel", "Could not locate base directory",
        execution_path=execution_path)
    os_formatted_path = gitPathToOsPath(git_formatted_path)
    return os_formatted_path

def allBranches(*, execution_path):
    return branch("-a", execution_path=execution_path).replace("*",' ').replace(" ",'').split()

def remoteBranches(*, execution_path):
    # git branch -r only lists branches that are currently being tracked, so we have to use ls-remote instead.
    remotes = gitcmd("ls-remote origin", "ls-remote failed", execution_path=execution_path, debug_log_stdout=GIT_VERY_VERBOSE)
    branches = []
    for entry in remotes.splitlines():
        fields = entry.split()
        if len(fields) == 2 and fields[1].startswith("refs/heads"):
            branch = fields[1].replace("refs/heads","origin",1)
            branches.append(branch)
    return branches

def remote(argstr="", *, execution_path):
    return gitcmd(f"remote {argstr}", "git remote failed", execution_path=execution_path)

def branch(argstr="", *, execution_path):
    # If all the arguments to branch are flags, only display output in very verbose mode
    debug_log_stdout = GIT_VERY_VERBOSE
    if not debug_log_stdout:
       for arg in argstr.strip().split(' '):
          if not arg.startswith('-'):
             debug_log_stdout = True
             break
    return gitcmd(f"branch {argstr}",
                  "Could not execute git branch command",
                  execution_path=execution_path, debug_log_stdout=debug_log_stdout)


def branchPrefix(branchName):
    return branchName.split('/')[0]


def branchUpToDateWith(branchName, targetBranch, *, execution_path):
    """Provided branch names should delimited by '/'.

    For Windows portability, see 'join_list_as_git_path()'.
    """
    try:
        allUpToDateBranches = gitcmd(f"branch -a --contains {targetBranch}",
                                     "branch contains failed",
                                     execution_path=execution_path)
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
        if b[0] == '*':
            cleanB = b[1:].strip()
        upToDate = cleanB == branchName.strip()
        if upToDate:
            break
    return upToDate


def bundle(argstr, *, execution_path):
    return gitcmd(f"bundle {argstr}", "Bundle failed",
                  execution_path=execution_path)


def checkout(argstr, *, execution_path):
    return gitcmd(f"checkout {argstr}", "Checkout failed",
                  execution_path=execution_path)


def clone(argstr='', *, source_repo, clone_repo, execution_path):
    if not os.path.isabs(clone_repo):
        clone_repo = os.path.join(execution_path, clone_repo)
    try:
        return gitcmd(f"clone {argstr} {source_repo} {clone_repo}",
                      "Clone failed",
                      execution_path=execution_path,
                      capture_output=True)
    except grape_errors.GrapeGitError as e:
        if "already exists and is not an empty directory" in e.gitOutput.lower():
            raise e
        if e.commError:
            logging.warning("GRAPE: clone failed due to connectivity issues.")
            return e.gitOutput
        logging.warning("GRAPE: Clone failed. Maybe you ran out of disk space?")
        logging.warning(e.gitOutput)
        raise e


def commit(argstr, *, execution_path):
    return gitcmd(f"commit {argstr}", "Commit failed",
                  execution_path=execution_path)


def commitDescription(committish, *, execution_path):
    try:
        descr = gitcmd(f"log --oneline {committish}^1..{committish}",
                       "commitDescription failed",
                       execution_path=execution_path)
    # handle the case when this is called on a 1-commit-long history (occurs mostly in unit testing)
    except grape_errors.GrapeGitError as e:
        if "unknown revision" in e.gitOutput.lower():
            try:
                descr = gitcmd(f"log --oneline {committish}",
                               "commitDescription failed",
                               execution_path=execution_path)
            except grape_errors.GrapeGitError as e:
                raise e
    return descr

def commitDescriptionShort(committish, *, execution_path):
    try:
        descr = gitcmd(f"log --oneline  --format='%s' {committish}^!",
                       "commitDescription failed",
                       execution_path=execution_path)
    # handle the case when this is called on a 1-commit-long history (occurs mostly in unit testing)
    except grape_errors.GrapeGitError as e:
        if "unknown revision" in e.gitOutput.lower():
            try:
                descr = gitcmd(f"log --oneline --format='%s' {committish}",
                               "commitDescription failed",
                               execution_path=execution_path)
            except grape_errors.GrapeGitError as e:
                raise e
    return descr

def config(argstr, arg2=None, *, execution_path):
    if arg2 is not None:
        return gitcmd(f'config {argstr} "{arg2}"', "Config failed",
                      execution_path=execution_path)
    return gitcmd(f'config {argstr} ', "Config failed",
                  execution_path=execution_path)


def conflictedFiles(*, execution_path):
    fileStr = diff("--name-only --diff-filter=U", execution_path=execution_path).strip()
    lines = fileStr.split('\n') if fileStr else []
    return lines


def currentBranch(*, execution_path):
    return gitcmd(f"rev-parse --abbrev-ref HEAD",
                  "could not determine current branch",
                  execution_path=execution_path)


def describe(argstr="", *, execution_path):
    return gitcmd(f"describe {argstr}", "could not describe commit",
                  execution_path=execution_path)


def diff(argstr, *, execution_path):
    return gitcmd(f"diff {argstr}", "could not perform diff",
                  execution_path=execution_path)


def fetch(repo="", branchArg="", recurseSubmodules="no", raiseOnCommError=False,
          warnOnCommError=False, *, execution_path):
    try:
        return gitcmd(f"fetch --recurse-submodules={recurseSubmodules} {repo} {branchArg}", "Fetch failed",
                      execution_path=execution_path, debug_log_stdout = GIT_VERY_VERBOSE)
    except grape_errors.GrapeGitError as e:
        if e.commError:
            # fetch can sometimes hang up when it can't find the remote, resulting in
            # a spurious comm error.  Catch that here.
            if "fatal: couldn't find remote ref" in e.gitOutput.lower():
                raise e
            if warnOnCommError:
                logging.warning("WARNING: could not fetch due to communication error.")
            if raiseOnCommError:
                raise e
            else:
                return e.gitOutput
        raise e


def getActiveSubmodules(*, execution_path):
    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"", execution_path=execution_path, capture_output=True)
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"", execution_path=execution_path, capture_output=True)
    submoduleList = [] if not submoduleList else submoduleList.split('\n')
    submoduleList = [x.strip() for x in submoduleList]
    # ignore any submodules that are not in .gitmodules
    submoduleList = [x for x in submoduleList if not x.startswith("fatal: no submodule mapping found in .gitmodules for path")]
    return submoduleList


# Remove any active submodules that are not found in gitmodules
def fixActiveSubmodules(ws_dir, user_input_func):
    if os.name == "nt":
        submoduleList = submodule("foreach --quiet \"echo $path\"",
                                  execution_path=ws_dir, capture_output=True)
    else:
        submoduleList = submodule("foreach --quiet \"echo \$path\"",
                                  execution_path=ws_dir, capture_output=True)
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
            rm(f"--ignore-unmatch --cached {sub}", execution_path=ws_dir)
            # remove from repo, if present
            rm(f"--ignore-unmatch {sub}", execution_path=ws_dir)
            if os.path.exists(os.path.join(ws_dir, sub)):
                delete = user_input_func(f"{sub} is no longer part of the " +
                                         "workspace.  Would you like to " +
                                         "delete it?", 'y')
                if delete:
                    shutil.rmtree(os.path.join(ws_dir, sub))
    return submoduleFixed

def getAllSubmodules(*, execution_path):
    subconfig = configparser.ConfigParser()
    try:
        subconfig.read(os.path.join(execution_path, ".gitmodules"))
    except configparser.ParsingError:
        # this is guaranteed to happen due to .gitmodules format incompatibility, but it does
        # read section names in successfully, which is all we need
        pass
    sections = subconfig.sections()
    submodules = []
    for s in sections:
        submodules.append(s.split()[1].split('"')[1])
    return submodules


def getAllSubmoduleURLMap(*, execution_path = None, gitmodules_string=None):
    if (gitmodules_string and execution_path) or (not gitmodules_string and not execution_path):
        logging.warning("WARNING: exactly one of execution_path and gitmodules_string should be set")
        
    if gitmodules_string:
        from vine import config_parser_base
        subconfig = config_parser_base.GrapeConfigParserBase(configString=gitmodules_string)
    else:
        try:
           fp = io.StringIO('\n'.join(line.strip() for line in io.open(os.path.join(execution_path, ".gitmodules"))))
        except FileNotFoundError:
           # No submodules are present
           return {}
        subconfig = configparser.ConfigParser()
        subconfig.read_file(fp)
        fp.close()

    sections = subconfig.sections()
    submodules = {}
    for s in sections:
        submodules[subconfig.get(s,"path")] = subconfig.get(s, "url")
    return submodules


def getInactiveSubmoduleURLMap(*, execution_path):
    all_urls = getAllSubmoduleURLMap(execution_path=execution_path)
    active_submodules = getActiveSubmodules(execution_path=execution_path)
    inactive_urls = {}
    for sub in all_urls:
        if sub not in active_submodules:
            inactive_urls[sub] = all_urls[sub]
    return inactive_urls

def getInactiveSubmoduleURLs(*, execution_path):
    url_map = getInactiveSubmoduleURLMap(execution_path=execution_path)
    return [parseSubprojectRemoteURL(url_map[x], execution_path=execution_path) for x in url_map]


def getModifiedSubmodules(ws_dir, branch1="", branch2="", includeAdded=False):
    submodules = getAllSubmodules(execution_path=ws_dir)
    # if there are no submodules, then return the empty list
    if len(submodules) == 0 or (len(submodules) == 1 and not submodules[0]):
        return []
    submodulesString = ' '.join(submodules)
    try:
        modifiedSubmodules = diff(f"--name-status {branch1} {branch2} -- " +
                                  f"{submodulesString}", execution_path=ws_dir).split('\n')
        if includeAdded:
            modifiedSubmodules = [sub.lstrip('AM \t') for sub in modifiedSubmodules if sub.startswith('M') or sub.startswith('A') ]
        else:
            # only include submodules that are in both branches
            modifiedSubmodules = [sub.lstrip('M \t') for sub in modifiedSubmodules if sub.startswith('M')]
    except grape_errors.GrapeGitError as e:
        if "bad revision" in e.gitOutput.lower():
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
def parseSubprojectRemoteURL(url, *, execution_path):
    URL_PATH_SEP = '/'
    path = url.replace('\\', URL_PATH_SEP)
    path = path.strip().split(URL_PATH_SEP)
    if path[0] in ["https:", "ssh:", "C:", ""]:
        return url      #Already a hard path

    # We have a relative path so start the remote origin URL
    originURL = config("--get remote.origin.url", execution_path=execution_path).strip().split(URL_PATH_SEP)

    #Now parse path and modify originURL to make a hard path
    for p in path:
        if p == os.path.pardir and len(originURL) > 0:
            originURL.pop()
        elif p == ".":
            pass
        else:
            originURL.append(p)
    if originURL[0] == '' and os.name != 'nt':
        originURL[0] = '/'
    parsed_url = urljoin(*originURL)
    if (parsed_url.startswith('ssh:/') and not parsed_url.startswith('ssh://')) \
            or (parsed_url.startswith('https:/') and not parsed_url.startswith('https://')):
        parsed_url = parsed_url.replace(':/', '://', 1)
    return parsed_url


def gitDir(*, execution_path):
    base = str(baseDir(execution_path=execution_path))
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
                toReturn = os.path.join(execution_path,gitPathToOsPath(relUnixPath))
            else:
                raise grape_errors.GrapeGitError("print .git file does not have gitdir: prefix as expected", 1, "", "grape gitDir()")
    return toReturn


def hasBranch(b, *, execution_path):
    branches = branch(execution_path=execution_path).split()
    return b in branches


def isWorkingDirectoryClean(printOutput=False, *, execution_path):
    statusOutput = status("-u --porcelain", execution_path=execution_path)
    toRet =  len(statusOutput.strip()) == 0
    if printOutput and not toRet:
        logging.info(f"{os.getcwd()}:")
        logging.info(statusOutput)
    return toRet



def log(args="", *, execution_path):
    return gitcmd(f"log {args}", "git log failed",
                  execution_path=execution_path)


def mv(args, *, execution_path):
    return gitcmd(f"mv {args}", "mv failed", execution_path=execution_path)


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

def lsRemote(args, *, execution_path):
    return gitcmd(f"ls-remote {args}", "ls-remote failed",
                  execution_path=execution_path)


def merge(args, *, execution_path):
    return gitcmd(f"merge {args}", "merge failed",
                  execution_path=execution_path)


def mergeAbort(*, execution_path):
    return gitcmd("merge --abort",
                  "Could not determine top level git directory.",
                  execution_path=execution_path)


def mergeBase(args, *, execution_path):
    return gitcmd(f"merge-base {args}", "merge-base failed", execution_path=execution_path)


def numberCommitsSince(commitStr, *, execution_path):
    strCount = gitcmd(f"rev-list --count {commitStr}..HEAD", "Rev-list failed",
                      execution_path=execution_path)
    return int(strCount)


def numberCommitsSinceRoot(*, execution_path):
    root = gitcmd(f"rev-list --max-parents=0 HEAD", "rev-list failed",
                  execution_path=execution_path)
    return numberCommitsSince(root, execution_path=execution_path)


def pull(args, throwOnFail=False, *, execution_path):
    try:
        return gitcmd(f"pull {args}", "Pull failed",
                      execution_path=execution_path,
                      capture_output=True)
    except grape_errors.GrapeGitError as e:
        if e.commError:
            logging.warning("WARNING: Pull failed due to connectivity issues.")
            if throwOnFail:
                raise e
            else:
                return e.gitOutput
        raise e


def push(args, throwOnFail=False, *, execution_path):
    try:
        return gitcmd(f"push --porcelain {args}", "Push failed",
                      execution_path=execution_path)
    except grape_errors.GrapeGitError as e:
        if e.commError:
            logging.warning("WARNING: Push failed due to connectivity issues.")
            if throwOnFail:
                raise e
            else:
                return e.gitOutput
        raise e


def rebase(args, *, execution_path):
    return gitcmd(f"rebase {args}", "Rebase failed",
                  execution_path=execution_path)

def reset(args, *, execution_path):
    return gitcmd(f"reset {args}", "Reset failed",
                  execution_path=execution_path)

def revert(args, *, execution_path):
    return gitcmd(f"revert {args}", "Revert failed",
                  execution_path=execution_path)

def rm(args, *, execution_path):
    return gitcmd(f"rm {args}", "Remove failed", execution_path=execution_path)


def safeForceBranchToOriginRef(branchToSync, *, execution_path):
    # first, check to see that branch exists
    branchExists = False
    remoteRefExists = False
    branches = branch("-a", execution_path=execution_path).split("\n")
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
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef, branchToSync,
                                                     execution_path=execution_path)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync, remoteRef,
                                                     execution_path=execution_path)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote:
            onBranch = branchToSync == currentBranch(execution_path=execution_path)
            if onBranch:
                logging.info(f"Current branch {branchToSync} in {execution_path} is out of date" +
                             " with origin. Detaching before forcing sync to origin.")
                checkout("--detach HEAD", execution_path=execution_path)
            branch(f"-f {branchToSync} {remoteRef}", execution_path=execution_path)
            if onBranch:
                checkout(f"{branchToSync}", execution_path=execution_path)
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote:
            return True
        else:
            return False
    if not branchExists and remoteRefExists:
        logging.info(f"local branch did not exist. Creating {branchToSync} " +
                     f"off of {remoteRef} now. ")
        branch(f"{branchToSync} {remoteRef}", execution_path=execution_path)
        return True

def SHA(branchName="HEAD", *, execution_path):
    return gitcmd(f"rev-parse {branchName}",
                  f"rev-parse of {branchName} failed!",
                  execution_path=execution_path)

def shortSHA(branchName="HEAD", *, execution_path):
    return gitcmd(f"rev-parse --short {branchName}",
                  f"rev-parse of {branchName} failed!",
                  execution_path=execution_path)

def parentsOfMergeCommit(mergeCommit, *, execution_path):
    return gitcmd(f"rev-list --parents -n 1 {mergeCommit}", "rev-list failed", execution_path=execution_path).split()[1:]

def show(argStr, *, execution_path):
    try:
        return gitcmd(f"show {argStr}",
                      f"show failed with argstr {argStr}",
                      execution_path=execution_path)
    except grape_errors.GrapeGitError as e:
        if "path" in e.gitOutput.lower() and "does not exist in" in e.gitOutput.lower():
            return ""

def showRemote(*, execution_path):
    try:
        return gitcmd("remote show origin", "unable to show remote",
                      execution_path=execution_path)
    except grape_errors.GrapeGitError as e:
        if e.code == 128:
            logging.warning(f"WARNING: {e.gitCommand} failed. Ignoring...")
            return e.gitOutput
        raise e

def stash(argstr="", *, execution_path):
    return gitcmd(f"stash {argstr}", "stash failed for some reason",
                  execution_path=execution_path)

def status(argstr="", *, execution_path):
    return gitcmd(f"status {argstr}", "status failed for some reason",
                  execution_path=execution_path)


def submodule(argstr, *, execution_path, capture_output=True):
    return gitcmd(f"submodule {argstr}", f"submodule {argstr} failed",
                  execution_path=execution_path,
                  capture_output=capture_output)


def subtree(argstr, *, execution_path):
    return gitcmd(f"subtree {argstr}",
                  f"subtree {argstr} failed - maybe subtree isn't installed" \
                  " on your system?",
                  execution_path=execution_path)


def tag(argstr, *, execution_path):
    return gitcmd(f"tag {argstr}", f"tag {argstr} failed",
                  execution_path=execution_path)


def version(*, execution_path):
    return gitcmd("version", "",
                  execution_path=execution_path)
