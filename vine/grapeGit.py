import os, subprocess, sys,string
import grapeMenu, utility

class GrapeGitError(Exception):
    def __init__(self,errmsg,returnCode,gitOutput,gitCommand):
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        print "When executing %s,Error %d raised with msg: %s \n %s" % (self.gitCommand,self.code, self.msg,self.gitOutput)

def gitcmd(cmd,errmsg):
    _cmd = "git %s" % cmd
    process = utility.executeSubProcess(_cmd, os.getcwd(), subprocess.PIPE)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s "% errmsg,process.returncode,process.communicate()[0],_cmd)
    return process.output.strip()

def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)

def baseDir(): 
    return gitcmd("rev-parse --show-toplevel", "Not in a git repo")

def baseDir():
    return gitcmd("rev-parse --show-toplevel", "Could not locate base directory")

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

def currentBranch(): 
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch")

def describe(argstr):
    return gitcmd("describe %s" % argstr, "could not describe commit")

def diff(argstr): 
    return gitcmd("diff %s" % argstr,"could not perform diff")

def dir():
    return gitcmd("rev-parse --show-toplevel", "Could not determine top level git directory.")

def fetch(repo = "", branch = ""):
    return gitcmd("fetch %s %s" %(repo,branch),"Fetch failed")

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
            branch("-f %s %s" % (branchToSync, remoteRef))
            return True
        elif remoteUpToDateWithLocal and localUpToDateWithRemote: 
            return True
        else: 
            return False
    if (not branchExists and remoteRefExists):
        print("local branch did not exist. Creating it now. ")
        branch("%s %s" % (branchToSync, remoteRef))
        return True
    
def shortSHA(): 
    return gitcmd("rev-parse --short HEAD", "rev-parse of HEAD failed!")

def showRemote():
    return gitcmd("remote show origin","unable to show remote")

def status():
    return gitcmd("status", "git status failed for some reason")

def tag(argstr):
    return gitcmd("tag %s" % argstr, "git tag %s failed" % argstr)

