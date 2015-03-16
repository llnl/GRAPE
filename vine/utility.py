import os
import subprocess
import sys
import ConfigParser
import types

import grapeGit as git
import grapeMenu
import grapeConfig

toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")
if toplevel not in sys.path:
    sys.path.append(toplevel)
from docopt.docopt import docopt
from docopt.docopt import Dict as docoptDict


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


#ensures the path string is windows compatibile if necessary
def makePathPortable(path): 
    if os.name == "nt":
        newPath = path.replace("/", "\\")
    else:
        newPath = path
    return newPath

globalArgs = []
globalCLI = ""

globalVerbosity = 1
def setVerbosity(level):
    global globalVerbosity
    globalVerbosity = level
    
def applyGlobalArgs(args):
    global globalArgs
    global globalCLI
    def __apply__(args): 
        if type(args) is docoptDict:
            if args["-v"]:
                setVerbosity(2)
            elif args["-q"]:
                setVerbosity(0)
            else:
                setVerbosity(1)
        if type(args) is types.ListType:
            # assume the list has yet to be parsed by docopt into the dict __apply__ expects.
            global globalCLI
            return __apply__(docopt(globalCLI,args, options_first=True))
        
        
    __apply__(args)
    globalArgs.append(args)
    
def popGlobalArgs():
    global globalArgs
    if len(globalArgs) > 1:
        globalArgs.pop()
    applyGlobalArgs.__apply__(globalArgs[-1])
        

def executeSubProcess(command, workingDirectory=os.getcwd(), verbose=2,
                      stdin=sys.stdin, stream = False):
    
    if verbose == -1:
        verbose = globalVerbosity
    if verbose > 1:
        print("Executing: " + command + "\n\t Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=(os.name != "nt"),
                               cwd=workingDirectory, stdin=stdin)
    output = ""
        
    if stream:
        while process.poll() is None:
            out = process.stdout.read(1)
            if verbose > 0:
                sys.stdout.write(out)
                sys.stdout.flush()
            output += out 
    process.wait()
    out = ''
    # this seems to flush out process.stdout even when the subprocess doesn't terminate it with an EOF
    for l in process.stdout:
        out += l
    out +=  process.communicate()[0]
    if verbose > 1 and stream:
        sys.stdout.write(out)
        sys.stdout.flush()
    output += out
    if verbose > 1 and not stream:
        print(output.strip())
    process.output = output
    if process.returncode != 0 and verbose > 0:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process


def grapeDir(): 
    return os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")


def GetCurrentBranch():
    output = git.gitcmd("rev-parse --abbrev-ref HEAD", "Error: Could not determine current  branch.")
    return output.strip()


def getDefaultName():
    if os.name == "nt":
        return os.getenv("USERNAME")
    else:
        return os.getenv("USER")


def getUserName(defaultName=getDefaultName(), service="LC"):
    return userInput("Enter %s User Name:" % service, defaultName)


def parseArgs(docstr, arguments, config):
    args = docopt(docstr, argv=arguments)
    for key in args:
        if type(args[key]) is str and ".grapeconfig." in args[key] and config is not None:
            tokens = args[key].split('.')
            args[key] = config.get(tokens[2].strip(), tokens[3].strip())
    return args


def printMsg(msg):
    global globalVerbosity
    if globalVerbosity > 0:    
        print("GRAPE: %s" % msg)


# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATEMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message, default=None):
    print("\n" + message)
    if default is "" or default is None:
        return raw_input('==> ').strip()
    else:
        value = raw_input("(def: %s) ==> " % default).strip()
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
    config = grapeConfig.GrapeConfigParser()
    grapeMenu.menu().setDefaultConfig(config)
    with open(filename, 'w') as f:
        config.write(f)


# return the path to the base level of the current workspace. (outermost git repo)
def workspaceDir(warnIfNotFound = True): 
    cwd = os.getcwd()
    basedir = None

 # go until you're at the root (you don't have a head after splitting)
    while os.path.split(os.getcwd())[1]:
        if os.path.exists(os.path.join(os.getcwd(), ".git")): 
            basedir = os.getcwd()
        os.chdir(os.path.join(os.getcwd(), ".."))
    if not basedir and warnIfNotFound:
        print("GRAPE WARNING: expected to be in your workspace, no .git found")
    os.chdir(cwd)
    return basedir

def isWorkspaceClean():
    isClean = git.isWorkingDirectoryClean()
    activeNestedSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
    base = workspaceDir()
    cwd = os.getcwd()
    for sub in activeNestedSubprojects:
        if not isClean:
            break
        os.chdir(os.path.join(base, sub))
        isClean = isClean and git.isWorkingDirectoryClean()
    os.chdir(cwd)
    return isClean

def getActiveSubprojects():
    return git.getActiveSubmodules() + grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()

def getModifiedSubprojects():
    return git.getModifiedSubmodules() + grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes()
                                                                                                             
                                                                                                      
# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec(): 
    if os.name == "nt":
        winpath = os.path.join(os.path.dirname(__file__), "..", "grape.py")
        return "c:/Python27/python.exe " + winpath.replace("\\", "/")
    else:
        return os.path.join(os.path.dirname(__file__), "..", "grape")

# Takes a URL and returns a hard path for it
def parseSubprojectRemoteURL(url): 
    path = url.strip().split('/')
    if "https:" == path[0] or "ssh:" == path[0] or "" == path[0]:
        return url      #Already a hard path

    # We have a relative path so start the remote origin URL
    originURL = git.config("--get remote.origin.url").strip().split('/')

    #Now parse path and modify originURL to make a hard path
    for p in path:
        if p == ".." and len(originURL) > 0:
            originURL.pop()
        elif p == ".":
            pass
        else:
            originURL.append(p)

    return '/'.join(originURL)


# returns the user's home directory: 
def getHomeDirectory(): 
    if os.name == "nt":
        home = os.environ["USERPROFILE"]
    else:
        home = os.environ["HOME"]
    return home
