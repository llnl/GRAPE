"""GRAPE's git utility logic across a single repository."""
import logging
import os
import sys
from contextlib import contextmanager
import grape_errors
import grapeGit as git


toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), os.path.pardir)
if toplevel not in sys.path:
    sys.path.insert(0, toplevel)
from docopt.docopt import docopt


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def grapeDir():
    return os.path.join(os.path.realpath(os.path.dirname(__file__)), "..")


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


# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATEMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message, default=None):
    print "\n" + message
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


# return the path to the base level of the current workspace. (outermost git repo)
def workspaceDir(warn_if_not_found=True, throw_if_not_found=True):
    workspace_dir = None
    base_dir = os.getcwd()
    # Go until you're at the root (you don't have a head after splitting)
    while os.path.split(base_dir)[1]:
        if os.path.exists(os.path.join(base_dir, '.git')):
            workspace_dir = base_dir
        base_dir = os.path.dirname(base_dir)
    if not workspace_dir and warn_if_not_found:
        logging.warning("GRAPE WARNING: expected to be in your workspace, no .git found")
    if not workspace_dir and throw_if_not_found:
        raise grape_errors.NoWorkspaceDirException(os.getcwd())
    return workspace_dir


def isWorkspaceClean(printOutput=False):
    # Imported here to avoid circular dependencies
    import config_parser_user
    isClean = git.isWorkingDirectoryClean(printOutput=printOutput)
    activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes()
    base = workspaceDir()
    cwd = os.getcwd()
    for sub in activeNestedSubprojects:
        if not isClean:
            break
        os.chdir(os.path.join(base, sub))
        isClean = isClean and git.isWorkingDirectoryClean(printOutput=printOutput)
    os.chdir(cwd)
    return isClean


def getActiveSubprojects():
        return git.getActiveSubmodules(workspaceDir()) + grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()


def getModifiedSubprojects(includeAdded=False):
        return git.getModifiedSubmodules(workspaceDir(), includeAdded) + grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes()


def getModifiedInactiveSubmodules(branch1, branch2, includeAdded=False):
    modifiedSubs = git.getModifiedSubmodules(workspaceDir(), branch1=branch1, branch2=branch2, includeAdded=includeAdded)
    activeSubs = git.getActiveSubmodules(workspaceDir())
    missing = []
    for sub in modifiedSubs:
        if sub not in activeSubs:
            missing.append(sub)
    return missing


# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec():
    if os.name == "nt":
        winpath = os.path.join(os.path.dirname(__file__), "..", "grape.py")
        return "c:/Python27/python.exe " + winpath.replace("\\", "/")
    else:
        return os.path.join(os.path.dirname(__file__), "..", "grape")


# returns the user's home directory:
def getHomeDirectory():
    if os.name == "nt":
        home = os.environ["USERPROFILE"]
    else:
        home = os.environ["HOME"]
    return home


@contextmanager
def cd(path):
    old_dir   =   os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)
