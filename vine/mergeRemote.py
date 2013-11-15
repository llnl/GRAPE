import option, utility

#merge a remote branch into this branch
class MergeRemote(option.Option):
    key = 'mr'
    section = " MERGE "

    def Description(self):
        return "Merge a remote branch into your current branch."

    def Execute(self):
        otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch",None)
        utility.mergeIntoCurrent("origin",otherBranch)
        return True
