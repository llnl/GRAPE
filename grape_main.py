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
grape_parent_dir = os.path.dirname(grape_path)
if grape_parent_dir not in sys.path:
    sys.path.insert(0, grape_parent_dir)

from docopt.docopt import docopt
from grape.vine import grapeMenu
from grape.vine import utility
from grape.vine import grapeGit as git
from grape.vine import global_state

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
    grape_path = os.path.dirname(os.path.realpath(__file__))
    vine_path = os.path.join(grape_path, 'vine')
    with open(os.path.join(vine_path, "VERSION"), 'r') as f:
        grapeVersion = f.read().split()[2]   
    args = docopt(CLI,  version=grapeVersion, options_first=True )
    myMenu = grapeMenu.menu()
    global_state.applyGlobalArgs(args)

        
    retval = True
    try:
        if (args["<command>"] is None):
            done = 0
            while not done:
                myMenu.presentTextMenu()
                choice = utility.userInput("Please select an option from the above menu", None).split()
                done = myMenu.applyMenuChoice(choice[0],choice)
        # If they specified a command line argument, then assume that it's
        # a menu option, and bypass the menu
        elif (len(sys.argv) > 1):
            retval = myMenu.applyMenuChoice(args["<command>"],args["<args>"])
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
