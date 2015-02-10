#!/bin/sh
"exec" "python" "-u" "-B" "$0" "$@"
import os, shutil, subprocess, sys

pythonMajorVersion = sys.version_info[0]
pythonMinorVersion = sys.version_info[1]

if not (pythonMajorVersion == 2 and pythonMinorVersion > 6): 
    print('Grape requires python 2.x, where x is greater than or equal to 7.')
    exit(1)

from vine import grapeConfig, grapeMenu, utility
from vine import grapeGit as git
import StringIO
import stashy.stashy as stashy
import keyring.keyring as keyring
import getpass

#*** GRAPE - Git Replacement for "Awesome" PARSEC Environment ********** 

def startup():
    #TODO - allow addition grape config file to be specified at command line
    #additionalConfigFiles = []
    #grapeConfig.read(additionalConfigFiles)
    myMenu = grapeMenu.menu()

    try:
        if (len(sys.argv) == 1):
            done = 0
            while not done:
                myMenu.presentTextMenu()
                choice = utility.userInput("Please select an option from the above menu", None).split()
                done = myMenu.applyMenuChoice(choice[0],choice)
        # If they specified a command line argument, then assume that it's
        # a menu option, and bypass the menu
        elif (len(sys.argv) > 1):
            myMenu.applyMenuChoice(sys.argv[1],sys.argv[1:])
    except KeyboardInterrupt:
        print("Operation interrupted by user...")

    # Exit the script
    print("Thank you - good bye")

## If this file is being run as a script, then run the main menu.
## If it's being imported, then don't
if __name__ == '__main__':
    startup()
