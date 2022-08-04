"""GRAPE's git utility logic across multiple repositories."""
import os
import sys
from docopt.docopt import docopt
from vine import grapeGit as git
if sys.platform == 'linux2':
    import readline


GRAPE_CONFIG = '.grapeconfig'
IS_NON_INTERACTIVE = False


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
        if isinstance(args[key], str) and GRAPE_CONFIG in args[key] and config is not None:
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
    if IS_NON_INTERACTIVE:
        if not default:
            return ""
        elif default.lower() == "y":
            return True
        elif default.lower() == "n":
            return False
        else:
            return default

    if default == "" or default is None:
        return input('==> ').strip()
    value = input(f"(def: {default}) ==> ").strip()
    if value == "":
        value = default
    if default.lower() == "y" or default.lower() == "n":
        if value.lower()[0] == "y":
            return True
        if value.lower()[0] == "n":
            return False
    return value


def isWorkspaceClean(printOutput=False, *, workspace_dir):
    # Imported here to avoid circular dependencies
    from vine import config_parser_user
    isClean = git.isWorkingDirectoryClean(printOutput=printOutput,
                                          execution_path=workspace_dir)
    activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir)
    for sub in activeNestedSubprojects:
        if not isClean:
            return False
        isClean = isClean and git.isWorkingDirectoryClean(
            printOutput=printOutput, execution_path=os.path.join(workspace_dir, sub))
    return isClean


def getModifiedInactiveSubmodules(branch1, branch2, includeAdded=False, *,
                                  workspace_dir):
    modifiedSubs = git.getModifiedSubmodules(workspace_dir, branch1=branch1,
                                             branch2=branch2,
                                             includeAdded=includeAdded)
    activeSubs = git.getActiveSubmodules(execution_path=workspace_dir)
    missing = []
    for sub in modifiedSubs:
        if sub not in activeSubs:
            missing.append(sub)
    return missing


# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec():
    par_dir_name = os.path.dirname(os.path.dirname(__file__))
    grape_path = os.path.join(par_dir_name, "grape_main.py")
    if os.name != "nt":
        return grape_path

    grape_path = win_path_to_linux_path(grape_path)
    python_path = win_path_to_linux_path(sys.executable)
    return f"{python_path} {grape_path}"


def win_path_to_linux_path(path):
    """Convert absolute Windows path to linux path for hooks in Git bash."""
    if os.path.altsep:
       path = path.replace('C:', f'{os.path.altsep}c')
       path = path.replace(os.path.sep, os.path.altsep)
    path = path.replace(' ', f'{os.path.sep} ')
    path = path.replace('(x86)', f'{os.path.sep}(x86{os.path.sep})')
    return path
