#!/bin/sh
"exec" "python" "-u" "-B" "$0" "$@"
import os, shutil, subprocess, sys
import tempfile

pythonMajorVersion = sys.version_info[0]
pythonMinorVersion = sys.version_info[1]

if not (pythonMajorVersion == 2 and pythonMinorVersion > 6): 
    print('Grape requires python 2.x, where x is greater than or equal to 7.')
    exit(1)

from vine import grapeMenu, utility
from vine import grapeGit as git
from vine import global_state
from vine import vine_logging

from docopt.docopt import docopt
import StringIO
import stashy.stashy as stashy
import keyring.keyring as keyring
import getpass
import os

import vine
vinePath = os.path.dirname(vine.__file__)


CLI = global_state.CLI

def startup():
    versionOutput = git.version().split()
    versionString = versionOutput.pop()
    while '.' not in versionString:
       versionString = versionOutput.pop()

    versions = versionString.split('.') 
   
    if int(versions[0]) == 1 and int(versions[1]) < 8:
        print('Grape requires at least git version 1.8, currently using %s' % versionString)
        return False

    #TODO - allow addition grape config file to be specified at command line
    #additionalConfigFiles = []
    #grapeConfig.read(additionalConfigFiles)
    with open(os.path.join(vinePath,"VERSION"),'r') as f:
        grapeVersion = f.read().split()[2]   
    args = docopt(CLI,  version=grapeVersion, options_first=True )
    myMenu = grapeMenu.menu()
    global_state.applyGlobalArgs(args)

        
    retval = True
    try:
        logger = vine_logging.GrapeLogger()
        if args["<command>"] is None:
            done = 0
            while not done:
                vine_logging.GrapeLogger.restore_sys_stdout()
                myMenu.presentTextMenu()
                choice = utility.userInput("Please select an option from the above menu", None).split()
                if 'test' not in choice:
                    logger.log_to_stdout()
                done = grapeMenu.menu().applyMenuChoice(choice[0], choice)
        # If they specified a command line argument, then assume that it's
        # a menu option, and bypass the menu
        elif len(sys.argv) > 1:
            vine_logging.GrapeLogger.restore_sys_stdout()
            if 'test' not in sys.argv:
                logger.log_to_stdout()
            retval = grapeMenu.menu().applyMenuChoice(args["<command>"], args["<args>"])
    except KeyboardInterrupt:
        print("GRAPE ERROR: Operation interrupted by user, exiting...")
        retval = False

    # Exit the script
    print("Thank you - good bye")
    return retval
        

## If this file is being run as a script, then run the main menu.
## If it's being imported, then don't
if __name__ == '__main__':
    exit(0 if startup() else 1)
