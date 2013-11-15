import utility, os, subprocess,sys
if not ".." in sys.path:
    sys.path.append( ".." )
#from grape import Grape

class GrapeGitError(Exception):
    def __init__(self,errmsg,returnCode):
        self.msg = errmsg
        self.code = returnCode

def gitcmd(cmd,errmsg):
    _cmd = "git %s" % cmd
    process = utility.executeSubProcess(_cmd, os.getcwd(), subprocess.PIPE)
    if process.returncode != 0:
        raise GrapeGitError("Error: %s",errmsg,process.returncode)
    output = process.communicate()[0]
    print output
    return output.strip()

def branch():
    return gitcmd("branch", "Could not list branches")

def dir():
    return gitcmd("rev-parse --show-toplevel", "Could not determine top level git directory.")

def fetch(repo = "", branch = ""):
    return gitcmd("fetch %s %s" %(repo,branch),"Fetch failed")

def merge( branch,strategy = ""): 
    try: 
        gitcmd("merge %s %s" % (branch,strategy), "merge failed")
        return 'q'
    except GrapeGitError as error: 
        if error.code == 1: 
            choice = utility.userInput("Conflicts generated. Would you like to resolve them now, abort the merge, or quit GRAPE? [resolve/abort/q]", "resolve")
        return choice



def mergeAbort():  
    return getcmd("merge --abort", "Could not determine top level git directory.")

def mergeIntoCurrent(repoName,branchName):
    from grape import Grape
    grp = Grape()
    grp.getOption('up').execute()
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
        from grape import Grape
        return Grape().getOption(choice).execute()


    return True

def pull(repo = "", branch = ""):
    return gitcmd("pull %s %s" %(repo,branch),"Fetch failed")
