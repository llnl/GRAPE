import option, utility

# pull and merge in an up-to-date development branch
class MergeDevelop(option.Option):
    key = "md"
    section = " MERGES "

    def Description(self):
        return "Merge latest changes on develop into your current feature branch"

    def Execute(self):
        print("Pulling changes from origin/develop into your repo...")
        utility.mergeIntoCurrent("origin","develop")
        utility.mergeIntoCurrent(".","develop")
        return True
