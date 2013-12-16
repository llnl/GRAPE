import os, subprocess, sys,string
import grapeMenu, utility

class GrapeGitError(Exception):
    def __init__(self,errmsg,returnCode,gitOutput):
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        print "Error %d raised with msg: %s \n %s" % (self.code, self.msg,self.gitOutput)

def gitcmd(cmd,errmsg):
    _cmd = "git %s" % cmd
    process = utility.executeSubProcess(_cmd, os.getcwd(), subprocess.PIPE)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s "% errmsg,process.returncode,process.communicate()[0])
    output = process.communicate()[0]
    print output
    return output.strip()

def add(filedescription):
    return gitcmd("add %s" % filedescription, "Could not add %s" % filedescription)

def baseDir(): 
    return gitcmd("rev-parse --show-toplevel", "Not in a git repo")

def branch():
    return gitcmd("branch", "Could not list branches")

def branchUpToDateWith(branch,targetBranch):
    allUpToDateBranches = gitcmd("branch --contains %s" % targetBranch, "branch contains failed")
    allUpToDateBranches = string.split(allUpToDateBranches,"\n")
    upToDate = False
    for b in allUpToDateBranches:
        # remove the * prefix from the active branch
        cleanB = b
        if b[0] is '*': 
            cleanB = b[1:]
        upToDate = cleanB == b
        if upToDate:
            break
    return upToDate

def checkout(argstr): 
    return  gitcmd("checkout %s" % argstr, "Checkout failed")

def clone(argstr):
    return gitcmd("clone %s" % argstr, "Clone failed")

def commit(argstr): 
    return gitcmd("commit %s" % argstr, "Commit failed")

def config(argstr): 
    return gitcmd("config %s" % argstr, "Config failed")

def currentBranch(): 
    return gitcmd("rev-parse --abbrev-ref HEAD", "could not determine current branch")

def dir():
    return gitcmd("rev-parse --show-toplevel", "Could not determine top level git directory.")

def fetch(repo = "", branch = ""):
    return gitcmd("fetch %s %s" %(repo,branch),"Fetch failed")

def isWorkingDirectoryClean():
    statusOutput = status()
    return "nothing to commit, working directory clean" in statusOutput

def log(args):
    return gitcmd("log %s" % args,"git log failed")

def merge( branch,strategy = ""):
    try:
        gitcmd("merge %s %s" % (branch,strategy), "merge failed")
        return 'q'
    except GrapeGitError as error:
        if error.code == 1:
            choice = utility.userInput("Conflicts generated. Would you like to resolve them now, abort the merge, or quit GRAPE? [resolve/abort/q]", "resolve")
        return choice

def mergeAbort():
    return gitcmd("merge --abort", "Could not determine top level git directory.")

def mergeIntoCurrent(repoName,branchName):
    grapeMenu.menu().getOption('up').execute()
    choice = None
    strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n"+
                         "am: Auto Merge (default) \n"+
                         "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                         "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" % branchName+
                         "ay: Accept Theirs - resolves conflicts by using changes in current branch." ,"am")


    if (strategy == 'am'):
        print("merging using git's default strategy")
        choice = merge(branchName)
    elif (strategy == 'as'):
        # this employs using the custom low-level merge driver "verify" and
        # appending a "* merge=verify" to the .gitattributes file.
        #
        # see http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file for details.
        print("merging forcing conflicts whenever both branches edited the same file...")
        base = utility.gitDir()
        if base == "":
            return False
        attributes = os.path.join(base,".gitattributes")
        tmpattributes = os.path.join(base,".gitattributes.tmp")
        # save original attributes file
        shutil.copyfile(attributes,tmpattributes)
        #append merge driver strategy to the attributes file
        with open(attributes,'a') as f:
            f.write("* merge=verify")

        # perform the merge
        choice = merge(branchName)

        # restore original attributes file
        shutil.copyfile(tmpattributes,attributes)
        os.remove(tmpattributes)

    elif (strategy == 'at'):
        print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
        choice = merge( branchName, "-Xtheirs")

    elif (strategy == 'ay'):
        print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
        choice = merge(branchName, "-Xours")

    if choice == 'q':
        return False
    choice = choice.strip().lower()
    if choice == "abort":
        if not mergeAbort():
            return False
    elif choice:
        return grapeMenu.menu().getOption(choice).execute()

    return True

def numberCommitsSince(commit):
    strCount = gitcmd("rev-list --count %s..HEAD" % commit, "Rev-list failed")
    return int(strCount)

def pull(repo = "", branch = ""):
    return gitcmd("pull %s %s" %(repo,branch),"Fetch failed")

def showRemote():
    return gitcmd("remote show origin","unable to show remote")

def status():
    return gitcmd("status", "git status failed for some reason")
