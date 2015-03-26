import os
import shutil

import utility
import grapeMenu
import grapeGit as git
import resumable


# merge in a local branch into this branch
#
# NOTE: any updates to merge's arguments should be reflected in Merge Remote's arguments, or at least given values
# by mergeRemote before the call to merge. 
class Merge(resumable.Resumable):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --ay] [--continue] [--noRecurse]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --noRecurse     Perform the merge in the current repository only. Otherwise, grape md --public=<branch> 
                        will be called to handle submodule and nested project merges.
        --continue      Resume your previous merge after resolving conflicts.

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
        if args["--continue"]:
            self._resume(args)
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like"
                                                                                  " to merge into this branch")
        args["<branch>"] = otherBranch
        if args["--noRecurse"]:
            return mergeIntoCurrent(otherBranch, args)
        else:
            mdArgs = {}
            mdArgs["--am"] = args["--am"]
            mdArgs["--as"] = args["--as"]
            mdArgs["--at"] = args["--at"]
            mdArgs["--ay"] = args["--ay"]
            mdArgs["--public"] = args["<branch>"]
            mdArgs["--recurse"] = True
            mdArgs["--noRecurse"] = False
            
            
            return grapeMenu.menu().getOption("md").execute(mdArgs)

    def _resume(self, args):
        if not ("inMD" in self.progress and self.progress["inMD"]):
            tmpArgs = {}
            try:
                super(Merge,self)._resume(args, deleteProgressFile=False)
            except IOError as e:
                # going to assume this --continue was called internally before we output a progress file...
                pass
            else:
                if self.progress["inMD"]:
                    return grapeMenu.menu().getOption("md")._resume(args)             
            
        status = git.status()
        if "All conflicts fixed but you are still merging." in status:
            git.commit("-m \"GRAPE: merge from %s after conflict resolution.\"" % args["<branch>"])
        elif git.isWorkingDirectoryClean():
            utility.printMsg("MERGE: no commit necessary, working directory clean.")
            pass
        else:
            utility.printMsg("MERGE: Does not appear a merge is ready to be continued. ")
        self._removeProgressFile()
        return True

    def _saveProgress(self, args):
        super(Merge, self)._saveProgress(args)
        pass

    def setDefaultConfig(self, config):
        pass


def merge(branch, strategy, args):
    try:
        git.merge("%s %s" % (branch, strategy))
        return True
    except git.GrapeGitError as error:
        print error.gitOutput
        if "conflict" in error.gitOutput.lower():
            utility.printMsg("Conflicts generated. Resolve using git mergetool, then continue "
                              "with grape %s --continue. " % args["<<cmd>>"])
        else:
            print("Merge command %s failed. Quitting." % error.gitCommand)
        return False


def mergeIntoCurrent(branchName, args):
    updateArgs = ['up', '--wd=%s' % os.getcwd(), '--noRecurse', '--public=%s' % branchName]
    grapeMenu.menu().applyMenuChoice('up', updateArgs)
    choice = False
    strategy = None
    if args['--am']:
        strategy = 'am'
    elif args['--as']: 
        strategy = 'as' 
    elif args['--at']: 
        strategy = 'at'
    elif args['--ay']: 
        strategy = 'ay'

    if not strategy: 
        strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n" +
                                     "am: Auto Merge (default) \n" +
                                     "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                                     "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" %
                                     branchName + "ay: Accept Yours - resolves conflicts by using changes "
                                                  "in current branch.", "am")

    if strategy == 'am':
        args["--am"] = True
        utility.printMsg("Merging using git's default strategy...")
        choice = merge(branchName, "", args)
    elif strategy == 'as':
        args["--as"] = True
        # this employs using the custom low-level merge driver "verify" and
        # appending a "* merge=verify" to the .gitattributes file.
        #
        # see
        # http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file
        # for details.
        utility.printMsg("Merging forcing conflicts whenever both branches edited the same file...")
        base = git.gitDir()
        if base == "":
            return False
        attributes = os.path.join(base, ".gitattributes")
        tmpattributes = None
        if os.path.exists(attributes): 
            tmpattributes = os.path.join(base, ".gitattributes.tmp")
            # save original attributes file
            shutil.copyfile(attributes, tmpattributes)
            #append merge driver strategy to the attributes file
            with open(attributes, 'a') as f:
                f.write("* merge=verify")
        else: 
            with open(attributes, 'w') as f:
                f.write("* merge=verify")

        # perform the merge
        choice = merge(branchName, "", args)

        # restore original attributes file
        if tmpattributes:
            shutil.copyfile(tmpattributes, attributes)
            os.remove(tmpattributes)
        else:
            os.remove(attributes)

    elif strategy == 'at':
        args["--at"] = True
        utility.printMsg("Merging using recursive strategy, resolving conflicts cleanly with changes in %s..." % branchName)
        choice = merge(branchName, "-Xtheirs", args)

    elif strategy == 'ay':
        args["--ay"] = True
        utility.printMsg("Merging using recursive strategy, resolving conflicts cleanly with current branch's changes...")
        choice = merge(branchName, "-Xours", args)

    return choice
