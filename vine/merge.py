import os,shutil
import option, utility, grapeMenu
import grapeGit as git

# merge in a local branch into this branch
class Merge(option.Option):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --ay]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in the event of a conflict (the branch you're currently on)

    Arguments:
        <branch>        The branch you want to merge in. 
        
    """
    def __init__(self):
        self._key = "m"
        self._section = "Merge"

    def description(self):
        return "Merge another local branch into your current branch."

    def execute(self,args):
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like to merge into this branch")
        strategy = None
        if args['--am']:
            strategy = 'am'
        elif args['--as']: 
            strategy = 'as' 
        elif args['--at']: 
            strategy = 'at'
        elif args['--ay']: 
            strategy = 'ay'
        return mergeIntoCurrent(".", otherBranch, strategy)


def merge( branch,strategy = ""):
    try:
        git.merge("%s %s" % (branch,strategy))
        return 'q'
    except git.GrapeGitError as error:
        if error.code == 1:
            choice = utility.userInput("Conflicts generated. Would you like to resolve them now, abort the merge, or quit GRAPE? [resolve/abort/q]", "resolve")
        else:
            print("Merge failed for unknown reason. Quitting.")
            choice = 'q'
        return choice

def mergeIntoCurrent(repoName,branchName,strategy):
    grapeMenu.menu().getOption('up').execute()
    choice = None
    if not strategy: 
        strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n"+
                             "am: Auto Merge (default) \n"+
                             "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                             "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" % branchName+
                             "ay: Accept Yours - resolves conflicts by using changes in current branch." ,"am")


    if (strategy == 'am'):
        print("merging using git's default strategy")
        choice = merge(branchName)
    elif (strategy == 'as'):
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
        print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
        choice = merge( branchName, "-Xtheirs")

    elif (strategy == 'ay'):
        print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
        choice = merge(branchName, "-Xours")

    if choice:
        choice = choice.strip().lower()
        return grapeMenu.menu().applyMenuChoice(choice,[choice])

    return False


