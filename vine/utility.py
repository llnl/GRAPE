"""GRAPE's git utility logic across multiple repositories."""
from contextlib import contextmanager
import os
import sys
from grape.docopt.docopt import docopt
from grape.vine import grape_errors
from grape.vine import grapeGit as git


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def grapeDir():
    return os.path.dirname(os.path.join(os.path.realpath(os.path.dirname(__file__))))


def getDefaultName():
    if os.name == "nt":
        return os.getenv("USERNAME")
    else:
        return os.getenv("USER")


def getUserName(defaultName=getDefaultName(), service="LC"):
    return userInput(f"Enter {service} User Name:", defaultName)


def parseArgs(docstr, arguments, config):
    args = docopt(docstr, argv=arguments)
    for key in args:
        if type(args[key]) is str and git.GRAPE_CONFIG in args[key] and config is not None:
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
    print(f"\n{message}")
    if default is "" or default is None:
        return input('==> ').strip()
    else:
        value = input(f"(def: {default}) ==> ").strip()
        if value == "":
            value = default
        if default.lower() == "y" or default.lower() == "n":
            if value.lower()[0] == "y":
                return True
            if value.lower()[0] == "n":
                return False
        return value


# return the path to the base level of the current workspace. (outermost git repo)
def workspaceDir():
    workspace_dir = None
    base_dir = os.getcwd()
    # Go until you're at the root (you don't have a head after splitting)
    while os.path.split(base_dir)[1]:
        if os.path.exists(os.path.join(base_dir, '.git')):
            workspace_dir = base_dir
        base_dir = os.path.dirname(base_dir)
    return workspace_dir


def isWorkspaceClean(printOutput=False):
    # Imported here to avoid circular dependencies
    from grape.vine import config_parser_user
    isClean = git.isWorkingDirectoryClean(printOutput=printOutput)
    activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes()
    base = workspaceDir()
    with git.cd(os.getcwd()):
        for sub in activeNestedSubprojects:
            if not isClean:
                break
            os.chdir(os.path.join(base, sub))
            isClean = isClean and git.isWorkingDirectoryClean(printOutput=printOutput)
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
    par_dir_name = os.path.dirname(os.path.dirname(__file__))
    grape_path = os.path.join(par_dir_name, "grape")
    if os.name != "nt":
        return grape_path

    grape_path = win_path_to_linux_path(grape_path)
    python_path = win_path_to_linux_path(sys.executable)
    return f"{python_path} {grape_path}"


def win_path_to_linux_path(path):
    """Convert absolute Windows path to linux path for hooks in Git bash."""
    path = path.replace('C:', f'{os.path.altsep}c')
    path = path.replace(os.path.sep, os.path.altsep)
    path = path.replace(' ', f'{os.path.sep} ')
    path = path.replace('(x86)', f'{os.path.sep}(x86{os.path.sep})')
    return path


# returns the user's home directory:
def getHomeDirectory():
    if os.name == "nt":
        home = os.environ["USERPROFILE"]
    else:
        home = os.environ["HOME"]
    return home


@contextmanager
def cd_workspace():
    starting_dir = os.getcwd()
    workspace_dir = workspaceDir()
    if starting_dir == workspace_dir:
        yield
        os.chdir(starting_dir)
    else:
        try:
            os.chdir(workspace_dir)
            yield
        except OSError as e:
            print(f"GRAPE WARNING: in {os.getcwd()} : {e}")
        finally:
            os.chdir(starting_dir)


@contextmanager
def cd_workspace_grapeconfig():
    starting_dir = os.getcwd()
    workspace_grapeconfig_dir = os.path.join(workspaceDir(), git.GRAPE_CONFIG)
    if starting_dir == workspace_grapeconfig_dir:
        yield
        os.chdir(starting_dir)
    else:
        try:
            os.chdir(workspace_grapeconfig_dir)
            yield
        except OSError as e:
            print(f"GRAPE WARNING: in {os.getcwd()} : {e}")
        finally:
            os.chdir(starting_dir)
