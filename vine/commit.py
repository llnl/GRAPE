import os
import option
import grapeGit as git

class Commit(option.Option):
    """
    Usage: grape-commit [-v] [-m <message>] [-a | <filetree>]  

    Options:
    -v      Show git commands being issued. 
    -a      Commit modified files that have not been staged. 
    

    Arguments:
    <filetree> The relative path of files to include in this commit. 

    """
    def __init__(self):
        self._key = "commit"
        self._section = "Miscellaneous"

    def description(self):
        return "runs git commit in all projects in this workspace"


    def execute(self,args):
        quiet = not args["-v"]
        commitargs = ""
        if args['-a']: 
            commitargs = commitargs +  " -a"
        elif args["<filetree>"]:
            commitargs = commitargs + " %s"% args["<filetree>"]
        if args['-m']: 
            commitargs = commitargs + " -m \"%s\""%args["<message>"]
         
        baseDir =  git.baseDir()
        os.chdir(baseDir)
        submodules = git.getSubmodules()
        submodulesString = ' '.join(submodules)
        status = git.status("--porcelain %s"%submodulesString).split('\n')
        for l in status: 
            file = l.split()[1]
            if file in submodules: 
                os.chdir(os.path.join(baseDir,file))
                git.commit(commitargs)
        os.chdir(baseDir)
#        git.submodule("foreach \"git commit %s\"" % commitargs,quiet=quiet)
        git.commit(commitargs)
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
