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
    output = process.communicate()[0]
    print output
    return output.strip()

def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)

def baseDir(): 
    return gitcmd("rev-parse --show-toplevel", "Not in a git repo")

def baseDir():
    return gitcmd("rev-parse --show-toplevel", "Could not locate base directory")

def branch(argstr=""):
    return gitcmd("branch %s" % argstr, "Could not list branches")

def branchUpToDateWith(branch,targetBranch):
    allUpToDateBranches = gitcmd("branch --contains %s" % targetBranch, "branch contains failed")
    allUpToDateBranches = string.split(allUpToDateBranches,"\n")
    upToDate = False
    for b in allUpToDateBranches:
        # remove the * prefix from the active branch
        cleanB = b
        if b[0] is '*': 
            cleanB = b[1:].strip()
        upToDate = cleanB == branch
        if upToDate:
            break
    return upToDate

def checkout(argstr): 
    return  gitcmd("checkout %s" % argstr, "Checkout failed")

def clone(argstr):
    return gitcmd("clone %s" % argstr, "Clone failed")

def commit(argstr): 
    return gitcmd("commit %s" % argstr, "Commit failed")

def config(argstr, arg2=""): 
    return gitcmd("config %s %s" % (argstr,arg2), "Config failed")

def currentBranch(): 
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch")

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

def shortSHA(): 
    return gitcmd("rev-parse --short HEAD", "rev-parse of HEAD failed!")

def showRemote():
    return gitcmd("remote show origin","unable to show remote")

def status():
    return gitcmd("status", "git status failed for some reason")

def tag(argstr):
    return gitcmd("tag %s" % argstr, "git tag %s failed" % argstr)

