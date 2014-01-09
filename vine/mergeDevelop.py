import option,merge 

# pull and merge in an up-to-date development branch
class MergeDevelop(option.Option):
    def __init__(self):
        self._key = "md"
        self._section = "Merge"

    def description(self):
        return "Merge latest changes on develop into your current feature branch"

    def execute(self):
        print("Pulling changes from origin/develop into your repo...")
#       if not merge.mergeIntoCurrent("origin", "develop"):
#           return False
        if not merge.mergeIntoCurrent(".", "origin/develop"):
            return False
        return True
