import os
import shutil

import utility
import grapeMenu
import grapeGit as git
import grapeConfig
import resumable


# merge in a local branch into this branch
#
# NOTE: any updates to merge's arguments should be reflected in Merge Remote's arguments, or at least given values
# by mergeRemote before the call to merge. 
class Merge(resumable.Resumable):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --aT | --ay | --aY | --askAll] [--continue] [--noRecurse] [--noUpdate] [--squash]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in any file touched by both branches (the branch you're merging from)
        --aT            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in any file touched by both branches (the branch you're currently on)
        --aY            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --askAll        Ask to determine the merge strategy before merging each subproject.
        --noRecurse     Perform the merge in the current repository only. Otherwise, grape md --public=<branch> 
                        will be called to handle submodule and nested project merges.
        --continue      Resume your previous merge after resolving conflicts.
        --noUpdate      Don't perform an update of your local version of <branch> from the remote before attempting
                        the merge.
        --squash        Perform squash merges. 

    Arguments:
        <branch>        The branch you want to merge in. 

    """
    def __init__(self):
        super(Merge, self).__init__()
        self._key = "m"
        self._section = "Merge"

    def description(self):
        return "Merge another local branch into your current branch."

    def execute(self, args):
        # this is necessary due to the unholy relationships between mr, m, and md. 
        if not "<<cmd>>" in args:
            args["<<cmd>>"] = 'm'
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like"
                                                                                  " to merge into this branch")
        args["<branch>"] = otherBranch
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()
        toks = otherBranch.split("origin/")
        if toks[-1] in publicBranches:
            public = toks[-1]
            publicMapping = config.getMapping("workspace", "submodulePublicMappings")
            subpublic = publicMapping[public]
            toks[-1] = subpublic
            subpublic = 'origin/'.join(toks)
        else:
            subpublic = otherBranch
            
        

        mdArgs = {}
        mdArgs["--am"] = args["--am"]
        mdArgs["--as"] = args["--as"]
        mdArgs["--at"] = args["--at"]
        mdArgs["--aT"] = args["--aT"]
        mdArgs["--ay"] = args["--ay"]
        mdArgs["--aY"] = args["--aY"]
        mdArgs["--askAll"] = args["--askAll"]
        mdArgs["--public"] = args["<branch>"]
        mdArgs["--subpublic"] = subpublic
        mdArgs["--recurse"] = not args["--noRecurse"]
        mdArgs["--noRecurse"] = args["--noRecurse"]
        mdArgs["--continue"] = args["--continue"]
        mdArgs["<<cmd>>"] = args["<<cmd>>"]
        mdArgs["--noUpdate"] = args["--noUpdate"]
        mdArgs["--squash"] = args["--squash"]
        
        
        return grapeMenu.menu().getOption("md").execute(mdArgs)

    def _resume(self, args):
        grapeMenu.menu().getOption("md")._resume(args)             
        return True

    def _saveProgress(self, args):
        super(Merge, self)._saveProgress(args)
        pass

    def setDefaultConfig(self, config):
        pass





