import os, subprocess, sys,string
import grapeMenu, utility

class GrapeGitError(Exception):
    def __init__(self,errmsg,returnCode,gitOutput,gitCommand):
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        print "When executing %s,Error %d raised with msg: %s \n %s" % (self.gitCommand,self.code, self.msg,self.gitOutput)

def gitcmd(cmd,errmsg,quiet=False):
    if os.name == "nt" :
       _cmd = "\"C:\\Program Files (x86)\\Git\\bin\\git.exe\" %s" % cmd
    else :
       _cmd = "git %s" % cmd
    if quiet:
        verbose = 0
    else:
        verbose = 2
    process = utility.executeSubProcess(_cmd, os.getcwd(), subprocess.PIPE,verbose=verbose)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s "% errmsg,process.returncode,process.output,_cmd)
    return process.output.strip()

def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)

def baseDir():
    beQuiet = True
    unixStylePath = gitcmd("rev-parse --show-toplevel", "Could not locate base directory",beQuiet)
    path = utility.makePathPortable(unixStylePath)
    return path

def branch(argstr=""):
    return gitcmd("branch %s" % argstr, "Could not list branches")

def branchUpToDateWith(branch,targetBranch):
    allUpToDateBranches = gitcmd("branch -a --contains %s" % targetBranch, "branch contains failed")
    allUpToDateBranches = allUpToDateBranches.split("\n")
    upToDate = False
    for b in allUpToDateBranches:
        # remove the * prefix from the active branch
        cleanB = b.strip()
        if b[0] is '*': 
            cleanB = b[1:].strip()
        upToDate = cleanB == branch.strip()
        if upToDate:
            break
    return upToDate

def bundle(argstr): 
    return  gitcmd("bundle %s" % argstr, "Bundle failed")

def checkout(argstr): 
    return  gitcmd("checkout %s" % argstr, "Checkout failed")

def clone(argstr):
    return gitcmd("clone %s" % argstr, "Clone failed")

def commit(argstr): 
    return gitcmd("commit %s" % argstr, "Commit failed")

def config(argstr, arg2=None): 
    if not arg2 == None:
        return gitcmd('config %s "%s"' % (argstr,arg2), "Config failed")
    else:
        return gitcmd('config %s ' % argstr, "Config failed")

def currentBranch(quiet = True): 
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch",quiet)

def describe(argstr):
    return gitcmd("describe %s" % argstr, "could not describe commit")

def diff(argstr): 
    return gitcmd("diff %s" % argstr,"could not perform diff")

def dir():
    return baseDir() 

def fetch(repo = "", branch = ""):
    return gitcmd("fetch %s %s" %(repo,branch),"Fetch failed")

def gitDir(): 
    base = baseDir()
    gitPath = os.path.join(base,".git")
    if os.path.isdir(gitPath): 
        return gitPath
    elif os.path.isfile(gitPath): 
        with open(gitPath) as f:
            line = f.read()
            words= line.split()
            if words[0] == 'gitdir:': 
                relUnixPath = words[1]
                return utility.makePathPortable(relUnixPath)
            else:
                raise grapeGitError("print .git file does not have gitdir: prefix as expected",1,"","grape gitDir()")




def isWorkingDirectoryClean():
    statusOutput = status()
    return "nothing to commit, working directory clean" in statusOutput

def log(args=""):
    return gitcmd("log %s" % args,"git log failed")

def merge(args ):
    return gitcmd("merge %s" % args, "merge failed")

def mergeAbort():
    return gitcmd("merge --abort", "Could not determine top level git directory.")

def numberCommitsSince(commit):
    strCount = gitcmd("rev-list --count %s..HEAD" % commit, "Rev-list failed")
    return int(strCount)

def numberCommitsSinceRoot():
    root = gitcmd("rev-list --max-parents=0 HEAD", "rev-list failed")
    return numberCommitsSince(root)
    
def pull(args):
    return gitcmd("pull %s" %args ,"Pull failed")

def push(args):
    return gitcmd("push %s" % args, "Push failed")

def rebase(args):
    return gitcmd("rebase %s" % args, "Rebase failed")

def safeForceBranchToOriginRef(branchToSync): 
    # first, check to see that branch exists
    branchExists = False
    remoteRefExists = False
    branches = branch("-a").split("\n")
    remoteRef = "remotes/origin/%s" % branchToSync
    for b in branches: 
        b = b.replace('*','')
        branchExists = branchExists or b.strip() == branchToSync.strip()
        remoteRefExists = remoteRefExists or b.strip() == remoteRef.strip()
        if (branchExists and remoteRefExists): 
            continue

    if (branchExists and not remoteRefExists): 
        print("origin does not have branch %s" % branchToSync)
        return False
    if (branchExists and remoteRefExists):
        remoteUpToDateWithLocal = branchUpToDateWith(remoteRef,branchToSync)
        localUpToDateWithRemote = branchUpToDateWith(branchToSync,remoteRef)
        if remoteUpToDateWithLocal and not localUpToDateWithRemote: 
            if branchToSync == currentBranch():
                printf("Current branch %s is out of date with origin. Pulling new changes." % branchToSync) 
                pull("origin %s" % branchToSync)
            else:
                branch("-f %s %s" % (branchToSync, remoteRef))
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote: 
            return True
        else: 
            return False
    if (not branchExists and remoteRefExists):
        print("local branch did not exist. Creating %s off of %s now. " % (branchToSync,remoteRef))
        branch("%s %s" % (branchToSync, remoteRef))
        return True
    
def shortSHA(): 
    return gitcmd("rev-parse --short HEAD", "rev-parse of HEAD failed!")

def showRemote():
    return gitcmd("remote show origin","unable to show remote")

def status():
    return gitcmd("status", "git status failed for some reason")

def submodule(argstr):
    return gitcmd("submodule %s" % argstr,"git submodule %s failed" % argstr)

def tag(argstr):
    return gitcmd("tag %s" % argstr, "git tag %s failed" % argstr)

