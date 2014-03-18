
import os
import shutil
import option, utility
import grapeGit as git
# update your custom sparse checkout view
class UpdateView(option.Option):
    """
    grape uv  - updates your sparse-checkout file and optionally performs the sparse checkout. 
    Usage: grape-uv [-f <sparsefile>] [--applyView | --noapplyView]

    Options:
        
        -f <sparsefile>         An existing sparse-checkout file to copy into .git/info. 
                                If this is not defined, grape will walk you through whether you 
                                want each top-level directory. (interactive)
        --applyView             Calls git read-tree -mu HEAD after updating .git/info/sparse-checkout
        --noapplyView           Skips the git read-tree call after updating .git/info/sparse-checkout
                                If neither --applyView nor --noapplyView are specified, grape uv
                                will ask you what you want to do. (interactive)

    """
    def __init__(self):
        self._key = "uv"
        self._section = "Workspace"

    def description(self):
        return "Update the view of your current working tree"

    def execute(self,args):
        base = git.baseDir()
        if base == "":
            return False
        dotGit = os.path.join(base,".git")
        sparseFile = os.path.join(dotGit,"info","sparse-checkout")
        sourceSparse = args["-f"]
        if not sourceSparse:
            print "calling utility.defineview"
            with open(sparseFile,'w') as f:
                utility.defineView(f)
        else:
            print "copying sourceSParse to sparse"
            shutil.copyfile(sourceSparse,sparseFile)

        checkout = not args["--noapplyView"] and (args["--applyView"] or utility.userInput("check out updated view? [y/n]","y"))
        if (checkout):
            git.gitcmd("read-tree -mu HEAD","sparse checkout returned with non-zero exit code")
        else:
            print("call 'git read-tree -mu HEAD' when you are ready to update your working tree")

        return True

    def setDefaultConfig(self,config):
        config.add_section("view")
        config.set("view","alldirs","src")
        config.set("view","required","src")
