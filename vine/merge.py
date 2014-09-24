import os
import shutil

import utility
import grapeMenu
import grapeGit as git
import resumable


# merge in a local branch into this branch
class Merge(resumable.Resumable):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --ay] [--continue] [-v] [--quiet]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --continue      Resume your previous merge after resolving conflicts.
        -v              Display git commands.
        --quiet         Don't issue messages if conflicts occur.

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
        if args["--continue"]:
            self._resume(args)
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like"
                                                                                  " to merge into this branch")
        args["<branch>"] = otherBranch
        return mergeIntoCurrent(otherBranch, args)

    def _resume(self, args):
        status = git.status(quiet=True)
        if "All conflicts fixed but you are still merging." in status:
            git.commit("-m \"GRAPE: merge from %s after conflict resolution.\"" % args["<branch>"])
        elif git.isWorkingDirectoryClean():
            print("GRAPE MERGE: no commit necessary, working directory clean.")
            pass
        else:
            print("GRAPE: Does not appear a merge is ready to be continued. ")
        return True

    def _saveProgress(self, args):
        super(Merge, self)._saveProgress(args)
        pass

    def setDefaultConfig(self, config):
        pass


def merge(branch, strategy, args):
    try:
        git.merge("%s %s" % (branch, strategy), quiet=not args["-v"])
        return True
    except git.GrapeGitError as error:
        print error.gitOutput
        if "conflict" in error.gitOutput.lower():
            print("GRAPE: Conflicts generated. Resolve using git mergetool, then continue "
                  "with grape m --continue. ")
        else:
            print("Merge command %s failed. Quitting." % error.gitCommand)
        return False


def mergeIntoCurrent(branchName, args):
    quiet = not args["-v"]
    updateArgs = ['up']
    if not quiet:
        updateArgs.append('-v')
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
        if not args["--quiet"]:
            print("GRAPE: merging using git's default strategy")
        choice = merge(branchName, "", args)
    elif strategy == 'as':
        args["--as"] = True
        # this employs using the custom low-level merge driver "verify" and
        # appending a "* merge=verify" to the .gitattributes file.
        #
        # see
        # http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file
        # for details.
        if not args["--quiet"]:
            print("GRAPE: merging forcing conflicts whenever both branches edited the same file...")
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
        if not args["--quiet"]:
            print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
        choice = merge(branchName, "-Xtheirs", args)

    elif strategy == 'ay':
        args["--ay"] = True
        if not args["--quiet"]:
            print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
        choice = merge(branchName, "-Xours", args)

    return choice
