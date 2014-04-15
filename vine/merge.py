import os,shutil
import option, utility, grapeMenu
import grapeGit as git
import resumable


# merge in a local branch into this branch
class Merge(resumable.Resumable):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --ay] [--continue]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --continue      Resume your previous merge after resolving conflicts.

    Arguments:
        <branch>        The branch you want to merge in. 
        
    """
    def __init__(self):
        self._key = "m"
        self._section = "Merge"

    def description(self):
        return "Merge another local branch into your current branch."

    def execute(self, args):
        if args["--continue"]:
            self._resume(args)
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like to merge into this branch")
        args["<branch>"] = otherBranch
        return mergeIntoCurrent( otherBranch, args)

    def _resume(self, args):
        status = git.status(quiet=True)
        if "All conflicts fixed but you are still merging." in status or git.isWorkingDirectoryClean():
            git.commit("-m \"GRAPE: merge from %s after conflict resolution.\"" % args["<branch>"])
        else:
            print("Does not appear a merge needs to be continued.")
        return True

    def _saveProgress(self, args):
        super(Merge,self)._saveProgress(args)
        pass


def merge( branch,strategy = ""):
    try:
        git.merge("%s %s" % (branch,strategy))
        return True
    except git.GrapeGitError as error:
        if error.code == 1:
           print("GRAPE: Conflicts generated. Resolve using git mergetool, then continue "
                                       "with grape m --continue. ")
           return False
        else:
            print("Merge failed for unknown reason. Quitting.")
            choice = False
        return choice



def mergeIntoCurrent(branchName,args):




    grapeMenu.menu().applyMenuChoice('up', ['up'])
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
        strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n"+
                                     "am: Auto Merge (default) \n"+
                                     "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                                     "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" % branchName+
                                     "ay: Accept Yours - resolves conflicts by using changes in current branch." ,"am")



    if (strategy == 'am'):
        args["--am"] = True
        print("merging using git's default strategy")
        choice = merge(branchName)
    elif (strategy == 'as'):
        args["--as"] = True
        # this employs using the custom low-level merge driver "verify" and
        # appending a "* merge=verify" to the .gitattributes file.
        #
        # see http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file for details.
        print("merging forcing conflicts whenever both branches edited the same file...")
        base = git.gitDir()
        if base == "":
            return False
        attributes = os.path.join(base,".gitattributes")
        tmpattributes = None
        if os.path.exists(attributes): 
            tmpattributes = os.path.join(base,".gitattributes.tmp")
            # save original attributes file
            shutil.copyfile(attributes,tmpattributes)
            #append merge driver strategy to the attributes file
            with open(attributes,'a') as f:
                f.write("* merge=verify")
        else: 
            with open(attributes,'w') as f:
                f.write("* merge=verify")
                    

        # perform the merge
        choice = merge(branchName)

        # restore original attributes file
        if tmpattributes:
            shutil.copyfile(tmpattributes,attributes)
            os.remove(tmpattributes)
        else:
            os.remove(attributes)
        

    elif (strategy == 'at'):
        args["--at"] = True
        print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
        choice = merge( branchName, "-Xtheirs")

    elif (strategy == 'ay'):
        args["--ay"] = True
        print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
        choice = merge(branchName, "-Xours")

    return choice



