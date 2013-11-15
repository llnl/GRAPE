import option, utility

# update your custom sparse checkout view
class UpdateView(option.Option):
    key = 'uv'
    section = " MISCELLANEOUS "

    def Description(self):
        return "Update the view of your current working tree"

    def Execute(self):
        base = utility.gitDir()
        if base == "":
            return False
        dotGit = os.path.join(base,".git")
        sparseFile = os.path.join(dotGit,"info","sparse-checkout")
        with open(sparseFile,'w') as f:
            DefineView(f)
        checkout = utility.userInput("check out updated view? [y/n]","y")
        if (checkout):
            git("read-tree","-mu","HEAD")
        else:
            print("call 'git read-tree -mu HEAD' when you are ready to update your working tree")

        return True

