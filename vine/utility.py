import os
import subprocess
import sys
import ConfigParser

import grapeGit as git
import grapeMenu
import grapeConfig

toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")
if toplevel not in sys.path:
    sys.path.append(toplevel)
from docopt.docopt import docopt


def ensure_dir(f):
    d = os.path.dirname(f)
    print("d:"+d)
    if not os.path.exists(d):
        print("making "+d)
        os.makedirs(d)


#ensures the path string is windows compatibile if necessary
def makePathPortable(path): 
    if os.name == "nt":
        newPath = path.replace("/", "\\")
    else:
        newPath = path
    return newPath


def executeSubProcess(command, workingDirectory=os.getcwd(), outFileHandle=subprocess.PIPE, verbose=2,
                      stdin=sys.stdin):
    if verbose > 1:
        print("Executing: " + command + "\n\t Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    process = subprocess.Popen(command, stdout=outFileHandle, stderr=subprocess.STDOUT, shell=True,
                               cwd=workingDirectory, stdin=stdin)
    output = ""
    for line in iter(process.stdout.readline, ''):
        line = line.replace('\r', '').replace('\n', '')
        if verbose > 0: 
            print line
            sys.stdout.flush()
        line += "\n"
        output = output+line
    process.wait()
    
    #output = process.communicate()[0]
    #if verbose > 0:
    #    print(output.strip())
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


def parseArgs(docstr, arguments):
    args = docopt(docstr, argv=arguments)
    config = grapeConfig.grapeConfig()
    for key in args:
        if type(args[key]) is str and ".grapeconfig." in args[key]:
            tokens = args[key].split('.')
            args[key] = config.get(tokens[2].strip(), tokens[3].strip())
    return args


def printMsg(msg):
    print("\nGRAPE: %s\n" % msg)


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
def workspaceDir(): 
    cwd = os.getcwd()
    basedir = None
    while True: 
        try: 
            basedir = git.baseDir()
            os.chdir(os.path.join(basedir, ".."))
        except git.GrapeGitError:
            break
    if not basedir:
        print("GRAPE WARNING: expected to be in your workspace, no .git found")
    os.chdir(cwd)
    return basedir


# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec(): 
    if os.name == "nt":
        winpath = os.path.join(os.path.dirname(__file__), "..", "grape.py")
        return "c:/Python27/python.exe " + winpath.replace("\\", "/")
    else:
        return os.path.join(os.path.dirname(__file__), "..", "grape")
