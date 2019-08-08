#!/usr/bin/env python3
import os
import sys

pythonMajorVersion = sys.version_info[0]
pythonMinorVersion = sys.version_info[1]

if not pythonMajorVersion > 2 or (pythonMajorVersion == 3 and
                                  pythonMinorVersion < 6):
    print('Grape requires Python 3.6 or greater.')
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


CLI =  """
*** GRAPE - Git Replacement for "Awesome" PARSEC Environment **********
Calling grape by itself will pull up the grape menu.
Usage: grape [-q] [--version] [<command> <args>...]

Options:
-q           Quiet mode. Quiet's all output except for user input prompts.



"""

def startup():
    # Calling GrapeLogger first correctly hides erroneous error msgs from users
    logger = vine_logging.GrapeLogger()

    versionOutput = git.version().split()
    versionString = versionOutput.pop()
    while '.' not in versionString:
       versionString = versionOutput.pop()

    versions = versionString.split('.') 

    #TODO - allow addition grape config file to be specified at command line
    #additionalConfigFiles = []
    #grapeConfig.read(additionalConfigFiles)
    grape_path = os.path.dirname(os.path.realpath(__file__))
    vine_path = os.path.join(grape_path, 'vine')
    with open(os.path.join(vine_path, "VERSION"), 'r') as f:
        grapeVersion = f.read().split()[2]   
    args = docopt(CLI, version=grapeVersion, options_first=True )
    myMenu = grapeMenu.menu()

    retval = True
    try:
        if args["<command>"] is None:
            done = 0
            while not done:
                myMenu.presentTextMenu()
                choice = utility.userInput("Please select an option from the above menu", None).split()
                set_verbosity(logger, choice)
                done = grapeMenu.menu().applyMenuChoice(choice[0], choice)
        # If they specified a command line argument, then assume that it's
        # a menu option, and bypass the menu
        elif len(sys.argv) > 1:
            set_verbosity(logger)
            retval = grapeMenu.menu().applyMenuChoice(args["<command>"], args["<args>"])
    except KeyboardInterrupt:
        print("GRAPE ERROR: Operation interrupted by user, exiting...")
        retval = False

    # Exit the script
    print("Thank you - good bye")
    return retval
        

def set_verbosity(logger, choice=None):
    """
    Message output verbosity determined here.

    Messages are printed to stdout/stderr by default. Messages are otherwise
    silenced during normal testing or if user specifies the 'quiet' flag.
    """
    if '-q' in sys.argv or (choice and 'test' in choice) or 'test' in sys.argv:
        return
    logger.log_to_stderr()
    logger.log_to_stdout()


## If this file is being run as a script, then run the main menu.
## If it's being imported, then don't
if __name__ == '__main__':
    exit(0 if startup() else 1)
