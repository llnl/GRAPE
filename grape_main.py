#!/usr/bin/env python3
from contextlib import contextmanager
#import logging
import os
import sys

sys.dont_write_bytecode = True

pythonMajorVersion = sys.version_info[0]
pythonMinorVersion = sys.version_info[1]

if not pythonMajorVersion > 2 or (pythonMajorVersion == 3 and
                                  pythonMinorVersion < 7):
    print('Grape requires Python 3.7 or greater.')
    exit(1)

# Main GRAPE import path set up. Applies to GRAPE usage via menu.
grape_path = os.path.dirname(os.path.realpath(__file__))
if grape_path not in sys.path:
    sys.path.insert(0, grape_path)

from docopt.docopt import docopt
from vine import grapeMenu
from vine import utility
from vine import grapeGit as git
from vine import vine_logging
from vine import workspace_dir_handler
from vine import version


CLI =  """
*** GRAPE - Git Replacement for "Awesome" PARSEC Environment **********
Calling grape by itself will pull up the grape menu.
Usage: grape [-t] [-v | --vv | -q] [-d] [--np=<numProcs>] [--gc=<configString>]... [<command> <args>...]
       grape [--version]

Options:
-t                   Print time before each logging statement.
-v                   Run in verbose mode. This will print out most git output as git commands complete.
--vv                 Run in very verbose mode. This will print out all git output as git commands complete.
-q                   Quiet mode. Quiet's all output except for user input prompts.
-d                   Defaults proposed by GRAPE used in place of prompting user for input.
                     This non-interactive option is for CI jobs and where users see fit.
--np=<int>           The number of processes grape should use when performing parallel operations. Values
                     less than 1 will use max number of processors available.
                     Default value is configurable via the concurrency-control section in the .grapeconfig:
                       #### default configuration ###
                       [concurrency-control]
                       # number of tasks for non-exclusive nodes.
                       defaultnumtasks = 8

                       # number of tasks for exclusive nodes. Exclusive nodes include all windows and osx
                       # environments and environments with environment variables given in exclusivevarlist.
                       exclusivenodenumtasks = -1

                       # space separated list of environment variables GRAPE should check for to determine if
                       # on an exclusive node in Linux environments. If any if the variables in the list exist,
                       # will use exclusivenodenumtasks, otherwise will use defaultnumtasks.
                       # Note - setting this to the string 'False' will instruct GRAPE not to check for
                       # environment variables, and you will get defaultnumtasks for default behavior in
                       # linux environments.
                       exclusivevarlist = SLURM_NODEID LLNL_COMPUTE_NODES
--gc=<configString>  Git configuration variables to pass to all git commands.
                     Each <configString> should be of the form "<name>=<value>".
--version            Print the GRAPE version and exit




"""

def startup():
    # Calling GrapeLogger first correctly hides erroneous error msgs from users
    logger = vine_logging.GrapeLogger()

    versionOutput = git.version(execution_path=os.getcwd()).split()
    versionString = versionOutput.pop()
    while '.' not in versionString:
        versionString = versionOutput.pop()

    #TODO - allow addition grape config file to be specified at command line
    #additionalConfigFiles = []
    #grapeConfig.read(additionalConfigFiles)
    args = docopt(CLI, version=version.grapeVersion(), options_first=True )

    if args['-t']:
        logger.time_string = '[%(asctime)s]'

    # do not prompt user for input
    if args["-d"]:
        utility.IS_NON_INTERACTIVE = True

    # set the level of concurrency
    if args["--np"]:
        from vine import multi_repo_cmd_launcher
        multi_repo_cmd_launcher.NUM_TASKS = int(args["--np"])

    if args["--gc"]:
        for keyval in args["--gc"]:
            try:
                (key, value) = keyval.split("=")
                git.addGitConfigFlag(f"-c {key}={value}")
            except ValueError:
                print("--gc arguments should be in the form <name>=<value>")
                return False
    try:
        from typing_extensions import Protocol 
    except ModuleNotFoundError:
        print("GRAPE: WARNING: GitLab REST API functions not available.")
        print("GRAPE: WARNING: You may need python 3.8+ and/or the typing_extensions module installed.") 

    retval = True
    try:
        if args["<command>"] is None:
            done = 0
            while not done:
                grapeMenu.menu().presentTextMenu()
                choice = utility.userInput("Please select an option from the above menu", None).split()
                set_verbosity(logger, args, choice)
                done = grapeMenu.menu().applyMenuChoice(choice[0], choice)
        # If they specified a command line argument, then assume that it's
        # a menu option, and bypass the menu
        elif args['<command>']:
            set_verbosity(logger, args)
            # this check needs to be first
            if args['<command>'] == 'clone':
                #print(f"GRAPE: Starting grape clone...")
                retval = clone_from_anywhere(args["<args>"])
            elif not grapeMenu.menu().hasOption(args["<command>"]):
                print()
                print("GRAPE: Unknown option '{}'".format(args["<command>"]))
                print("GRAPE: Please choose option from menu below")
                print()
                grapeMenu.menu().presentTextMenu()
                retVal = False
            else:
                #logging.info(f"Starting grape {args['<command>']}...")
                retval = grapeMenu.menu().applyMenuChoice(args["<command>"], args["<args>"])
    except KeyboardInterrupt:
        print("GRAPE ERROR: Operation interrupted by user, exiting...")
        retval = False

    # Exit the script
    #logging.info("Thank you - good bye")
    return retval
        

def clone_from_anywhere(args_ ):
    wsdir_handler = workspace_dir_handler.WorkspaceDirHandler()
    # The workspace_dir will only be set if it a git repo
    wsdir_handler.workspace_dir = os.getcwd()
    # Access the internal _workspace_dir variable to prevent exit due to not being in git repo
    if wsdir_handler._workspace_dir:
        return grapeMenu.menu().applyMenuChoice('clone', args_)
    else:
        # Create a phony .git directory so we can set the workspace_dir
        with setup_temp_git_dir():
            return grapeMenu.menu().applyMenuChoice('clone', args_)


@contextmanager
def setup_temp_git_dir():
    """Temp git dir created to set a 'workspace_dir', then removed later."""
    TMP_GIT_DIR = os.path.abspath('.git')
    try:
        os.mkdir(TMP_GIT_DIR)
        yield
    finally:
        os.rmdir(TMP_GIT_DIR)


def set_verbosity(logger, args, choice=None):
    """
    Message output verbosity determined here.

    Messages are printed to stdout/stderr by default. Messages are otherwise
    silenced during normal testing or if user specifies the 'quiet' flag.
    """
    if args['-q'] or (choice and 'test' in choice) or (args["<command>"] and 'test' in args["<command>"]):
        return

    logger.log_to_stderr()
    logger.log_to_stdout()
    if args['-v'] or args['--vv']:
        logger.log_to_stdout_debug()
        if args['--vv']:
           git.GIT_VERY_VERBOSE = True


## If this file is being run as a script, then run the main menu.
## If it's being imported, then don't
if __name__ == '__main__':
    exit(0 if startup() else 1)
