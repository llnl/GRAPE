import option, utility

#merge a remote branch into this branch
class MergeRemote(option.Option):
    def __init__(self):
        self._key = "mr"
        self._section = "Merge"

    def description(self):
        return "Merge a remote branch into your current branch."

    def execute(self):
        otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch")
        return utility.mergeIntoCurrent("origin",otherBranch)
