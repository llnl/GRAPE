#!/bin/sh
"exec" "python" "-B" "$0" "$@"
import os, shutil, subprocess, sys
from vine import grapeConfig, grapeMenu, utility
from vine import grapeGit as git
import StringIO
import stashy.stashy as stashy
import keyring.keyring as keyring
import getpass

#*** GRAPE - Git Replacement for "Awesome" PARSEC Environment **********

#**** GETTING STARTED  ***********************
#init) Clone the  repo and initialize your git config
#config) Initialize a repo you've already cloned without using GRAPE

#**** GITFLOW TASKS ************************

#dev)  Create a new feature development branch (branch off of develop)

#rel)  Create a new Release bugfix branch  (branch off of a Stable Release branch)

#minor) Checkout a minor Release branch (for fixing nightly/ build failures)

#hot)  Create a hotfix branch (for fixing weekly test failures on master)

#help) Display a gitflow diagram to help make a decision

#*** PERFORCE COMPATABILITY ***
#p4import) Import recent p4 changes into a hotfix branch

#p4export) Prepare a feature branch in a p4 maindev client, ready for precommit --TODO

#**** CODE REVIEWS  ****

#w) walkthrough diffs between branches

#review) Prepare current branch for a code review using a Pull Request--TODO

#**** MERGES *********************************
#md) Merge latest changes on develop into your current feature branch
#m)  Merge another local branch into your current branch
#resolve) Resolve conflicts

#*** ADMINISTRATION  ***

#fis) fastFIS recent changes in master and develop --TODO
#offsite)  Create an Offsite Branch --TODO
#test ) Run the grape test suite

# *** You need admin privileges for the Stash repo to do these ***

#release)  Create a new Release Branch -- TODO
#mergeMinor) Merge a minor release branch into master and develop TODO
#mergeHotfix) Merge a hotfix branch into master and develop TODO
#updateStable) Update the Stable pointer to Head of develop TODO



#**** MISCELLANEOUS ***************************
#ce) Create a standard eclipse workspace for this git repo --TODO
#b)  List all of your branches  --TODO
#cv) Create a custom sparse checkout view in a new working tree--TODO
#uv) Update your sparse checkout view in your current working tree--TODO

#*** OTHER ***********************************
#q)  Quit --DONE

# choice                time --------->                                            Branch Type
#____________________________________________________________________________________________________
#
#           [4.20.0] ---- [4.20.1,Release_4_20]                                    Stable Release
#           /       \     /
#rel)      /         []--[]                                                        Release bugfix
#         /                \
#       [4.19.last] --[4.21.1] ------[4.21.2]------[4.21.3] ---- [4.21.4 ]         master
#          \            \             /            /     \       /
#hot)       \            \           /            /       []---[]                  hotfix  (fix weekly)
#            \            \         /            /              \
#minor)       \            \       /       []--- []              \                 minor Release Branch (fix nightly)
#              \            \     /       /        \              \
#               [] --------- []--[] ---- []------- [] ------- [STABLE]----[TEST]   develop (shared history)
#                 \          |   / \     /                       \           /
#                  \          \ /   \   /                         \         /
#rev)               []------ [F1]   []-[F2]                       [] ---- [F3]     feature (new development)
#
#
#  What's going on here? This depicts the flow of commits through various situations.
#  To understand what's going on, let's explore how each of the four 4.21 versions
#  came to be.
#
#  Version 4.21.1:
#  A bug was discovered in 4.20.0 (in the Stable Release Branch). The fix was implemented
#  in a Release bugfix branch. The resulting fix was merged both with the Stable Release
#  Branch and with master, resulting in 4.21.1.  The fix is also merged down to develop.
#
#  Version 4.21.2:
#  A new feature is developed on a feature branch named F1. After 4.21.1 gets merged in (via a
#  git rebase STABLE) and all update tests pass,  F1 is merged into develop using a Pull Request
#  on Stash. The test system determines that nightly tests pass, marks the head of develop
#  as stable and merges the changes to master, where it is versioned as 4.21.2.
#
#  Version 4.21.3:
#  A new feature is developed on a feature branch named F2. Once all update tests pass, F2 is
#  merged into develop using a Pull Request on Stash. The test system determines that one or
#  more nightly tests or builds fail, and creates a minor release Branch for developers to
#  address the issue. A developer checks out the branch using grape minor, and performs necessary
#  fixes in the branch. Once all nightly tests pass, the minor Release branch is merged both back
#  into develop, where it is marked as stable, and into master, where it is versioned as 4.21.3.
#
#  Version 4.21.4:
#  Version 4.21.3 is show to fail weekly and/or class tests. Since this is a bug in the master branch,
#  and the fix is likely small and quick, the fix is performed in a hotfix branch. Depending on the
#  urgency of the issue and complexity of the fix, at least  update and possibly nightly tests are
#  performed before merging the fix back into master, via a Pull Request on Stash, where it is versioned
#  as 4.21.4. It is also merged back into develop, where it is marked as STABLE.
#
#  Feature F3:
#  F3 has just been merged into develop using a Pull Request on Stash. It's marked for nightly testing,
#  but has yet to be marked as stable given the lack of nightly testing results.
#

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
                choice = utility.userInput("Please select an option from the above menu", None)
                done = myMenu.applyMenuChoice(choice,sys.argv[1:])
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
