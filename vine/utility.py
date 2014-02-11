import os, StringIO, subprocess, sys, tempfile, ConfigParser
import grapeGit as git
import grapeMenu
import grapeConfig
from docopt.docopt import docopt


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
    user = getUserName()
    fullBranch = prefix+"/"+user+"/"+branch
    proceed = userInput("About to create branch "+fullBranch+" off of "+branchPoint+".\nProceed? [y/n]",'y')
    if (proceed):
        git.checkout("-b %s %s " % (fullBranch,branchPoint))
        git.push("-u origin %s" % fullBranch)
    else:
        print("Branch not created")

def defineView(sparseFile):
    include = {}
    requiredDirs = grapeConfig.grapeConfig().get("view","required")
    reqdirs = requiredDirs.split(" ")
    for r in reqdirs:
       include[r] = True
    alldirs = grapeConfig.grapeConfig().get("view","alldirs")
    directories = alldirs.split(" ")
    print directories
    accept = userInput("Do you want everything? [y/n]","y")
    text = []
    while not accept:
        accept = userInput("Do you only want the required view? [y/n]","y")
        for d in directories:
            if d in reqdirs:
               continue
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

#ensures the path string is windows compatibile if necessary
def makePathPortable(path): 
    if os.name == "nt" :
       newPath = path.replace("/","\\")
    else :
       newPath = path
    return newPath


def executeSubProcess(command, workingDirectory=tempfile.gettempdir(), outFileHandle=subprocess.PIPE, verbose=2):
    if verbose > 1:
        print("Executing: " + command + ": Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    process = subprocess.Popen(command, stdout=outFileHandle, stderr=subprocess.STDOUT, shell=True, cwd=workingDirectory)
    output = ""
    for  line in iter(process.stdout.readline, ''): 
        line = line.replace('\r', '').replace('\n', '')
        if verbose > 0: 
            print line
            sys.stdout.flush()
        line = line + "\n"
        output = output+line
    process.wait()
    process.output = output
    if process.returncode != 0:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process

def grapeDir(): 
    return os.path.join(os.path.realpath(os.path.dirname(__file__)),"..")

def GetCurrentBranch():
    output = git.gitcmd("rev-parse --abbrev-ref HEAD", "Error: Could not determine current  branch.")
    return output.strip()


def GetSHA(desc):
    out = StringIO.StringIO()
    git("rev-parse",desc,_out=out)
    toReturn = out.getvalue().strip().encode('ascii')
    out.close()
    return toReturn

def getDefaultName() :
    if (os.name == "nt") :
        return os.getenv("USERNAME")
    else :
        return os.getenv("USER")

def getUserName(defaultName=getDefaultName()):
    return userInput("Enter LC User Name:", defaultName)

def parseArgs(docstr,arguments): 
    args = docopt(docstr,argv=arguments)
    config = grapeConfig.grapeConfig()
    for key in args:
       if type(args[key]) is str and ".grapeconfig." in args[key]:
           tokens = args[key].split('.') 
           args[key] = config.get(tokens[2].strip(),tokens[3].strip())
    return args

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
            value = default
        if default.lower() == "y" or default.lower() == "n":
            if value.lower()[0] == "y":
                return True
            if value.lower()[0] == "n":
                return False
        return value

# writes a config file with default options
def writeDefaultConfig(filename):
   config = ConfigParser.RawConfigParser()
   grapeMenu.menu().setDefaultConfig(config)
   with open(filename,'w') as f:
      config.write(f)

# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec(): 
    return os.path.join(os.path.dirname(__file__),"..","grape")

