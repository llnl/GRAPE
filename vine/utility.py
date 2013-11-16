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

def defineView(sparseFile):
    include = {}
    include["src"] = True
    include["scripts"] = True
    alldirs = config.get("view","alldirs")
    directories = alldirs.split(" ")

    accept = userInput("Do you want everything? [y/n]","y")
    text = []
    while not accept:
        accept = userInput("Do you only want the required view? [y/n]","y")
        for d in directories:
            use = False if accept else userInput("Do you want %s? [y/n]" % d,"n")
            if (use):
                include[d] = True
            else:
                include[d] = False

        # build sample text file for display
        text = []
        for key in include:
            if not include[key]:
                text.append("!%s/*\n" %key)
        text.append("/*")

        # display sample text
        print("sample sparse checkout file:")
        for l in text:
            print(l)

        accept = userInput("does this look OK? [y/n]","y")

    #end while
    #write accepted sparse-checkout file
    sparseFile.writelines(text)

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

