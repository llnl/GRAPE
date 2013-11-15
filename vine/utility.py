import os, StringIO, subprocess, sys, tempfile
if not ".." in sys.path:
    sys.path.append( ".." )
import git

def cascade(l, op):
    """Apply an operation to a chain of interdependent pairs in a list"""
    ancestor = l[0]
    for descendent in l[1:]:
        exec op # this should be an eval so we can return an 'error' and exit
        ancestor = descendent

def cmerge(l):  # this should return 'success' or an error code
    """Apply a git merge across several branches"""
    Cascade(l, "print 'git checkout', descendent\nprint 'git merge', ancestor\n")

def createBranch(branchPoint, prefix):
    branch = userInput("Enter new branch name")
    user = GetUserName()
    fullBranch = prefix+"/"+user+"/"+branch
    proceed = userInput("About to create branch "+fullBranch+" off of "+branchPoint+".\nProceed? [y/n]",'y')
    if (proceed):
        git.checkout("-b",fullBranch,branchPoint)
    else:
        print("Branch not created")

def ensure_dir(f):
    d = os.path.dirname(f)
    print("d:"+d)
    if not os.path.exists(d):
        print("making "+d)
        os.makedirs(d)

def executeSubProcess(command, workingDirectory=tempfile.gettempdir(), outFileHandle=1, verbose=True):
    if verbose:
        print("Executing: " + command + ": Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    process = subprocess.Popen(command, stdout=outFileHandle, stderr=outFileHandle, shell=True, cwd=workingDirectory)
    process.wait()
    if process.returncode != 0:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process

def GetCurrentBranch():
    process = executeSubProcess("git rev-parse --abbrev-ref HEAD", os.getcwd(), subprocess.PIPE )
    if process.returncode != 0:
        print("Error: Could not determine current  branch.")
        return False
    output = process.communicate()[0]
    return output.strip()


def GetSHA(desc):
    out = StringIO.StringIO()
    git("rev-parse",desc,_out=out)
    toReturn = out.getvalue().strip().encode('ascii')
    out.close()
    return toReturn

def getUserName(defaultName=os.getlogin()):
    return userInput("Enter LC User Name:", defaultName)

def gitMerge(repoName, branchName, option=""):
    choice = None
    if (option != ""):
        pull = git.pull.bake(option)
    else:
        pull = git.pull
    try:
        pull(repoName,branchName)
    except sh.ErrorReturnCode_1 as error:
        choice = utility.userInput("Conflicts generated. Would you like to resolve them now, abort the merge, or quit GRAPE? [resolve/abort/q]", "resolve")
    except sh.ErrorReturnCode as error:
        print("unknown return code during merge")
        print(error)
        return None

    return choice

def gitMergeAbort():
    process = executeSubProcess("git merge --abort", os.getcwd())
    if process.returncode != 0:
        print("Error: Could not determine top level git directory.")
        return False
    return True

def gitDir():
    process = executeSubProcess("git rev-parse --show-toplevel", os.getcwd(), subprocess.PIPE)
    if process.returncode != 0:
        print("Error: Could not determine top level git directory.")
        return ""
    output = process.communicate()[0]
    return output.strip()

def mergeIntoCurrent(repoName,branchName):
    git.fetch(repoName,branchName)
    choice = None
    strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n"+
                         "am: Auto Merge (default) \n"+
                         "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                         "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" % branchName+
                         "ay: Accept Theirs - resolves conflicts by using changes in current branch." ,"am")


    if (strategy == 'am'):
        print("merging using git's default strategy")
        git.pull(repoName,branchName)
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
        choice = gitMerge(repoName, branchName)

        # restore original attributes file
        shutil.copyfile(tmpattributes,attributes)
        os.remove(tmpattributes)

    elif (strategy == 'at'):
        print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
        choice = gitMerge(repoName, branchName, "-Xtheirs")

    elif (strategy == 'ay'):
        print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
        choice = gitMerge(repoName, branchName, "-Xours")

    if choice == None:
        return False
    choice = choice.strip().lower()
    if choice == "abort":
        if not gitMergeAbort():
            return False
    elif choice:
        return options[choice].execute()

    return True

# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATEMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message, default=None):
    print("\n" + message)
    if (default is "" or default is None):
        return raw_input('==> ').strip()
    else:
        value = raw_input("(def: %s) ==> " % (default)).strip()
        if value == "":
            return default
        if default.lower() == "y" or default.lower() == "n":
            if value.lower()[0] == "y":
                return True
            if value.lower()[0] == "n":
                return False
        return value

# writes a config file with default options
def writeDefaultConfig(filename):
    with open(filename,'w') as f:
        f.write("[repo]\n")
        f.write("name:unknown\n")
        f.write("url:unknown\n")

