
import os
import option, utility
import grapeGit as git
# update your custom sparse checkout view
class UpdateView(option.Option):
    def __init__(self):
        self._key = "uv"
        self._section = "Miscellaneous"

    def description(self):
        return "Update the view of your current working tree"

    def execute(self):
        base = git.baseDir()
        if base == "":
            return False
        dotGit = os.path.join(base,".git")
        sparseFile = os.path.join(dotGit,"info","sparse-checkout")
        with open(sparseFile,'w') as f:
            utility.defineView(f)
        checkout = utility.userInput("check out updated view? [y/n]","y")
        if (checkout):
            git.gitcmd("read-tree -mu HEAD","sparse checkout returned with non-zero exit code")
        else:
            print("call 'git read-tree -mu HEAD' when you are ready to update your working tree")

        return True

    def setDefaultConfig(self,config):
        config.add_section("view")
        config.set("view","alldirs","src")
        config.set("view","required","src")
