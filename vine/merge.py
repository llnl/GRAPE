import option, utility

# merge in a local branch into this branch
class Merge(option.Option):
    def __init__(self):
        self._key = "m"
        self._section = "Merge"

    def description(self):
        return "Merge another local branch into your current branch."

    def execute(self):
        otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch")
        return utility.mergeIntoCurrent(".", otherBranch)
