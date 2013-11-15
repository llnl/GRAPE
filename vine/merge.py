import option, utility

# merge in a local branch into this branch
class Merge(option.Option):
    key = 'm'
    section = " MERGE "

    def Description(self):
        return "Merge another local branch into your current branch."

    def Execute(self):
        otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch",None)
        utility.mergeIntoCurrent(".",otherBranch)
        return True
