import os
import option
import grapeGit as git
import utility

class Status(option.Option):
    """
    Usage: grape-status [-v]

    Options:
    -v      Show git commands being issued. 

    """
    def __init__(self):
        self._key = "status"
        self._section = "Workspace"

    def description(self):
        return "Gives the status for this workspace"


    def execute(self,args):
        print("gathering status on outer level project")
        cwd = utility.workspaceDir() 
        os.chdir(cwd)
        quiet = not args["-v"]
        status = git.status("--porcelain",quiet).split('\n')
        if status[0] and status[0][0] != ' ':
            status[0] = ' ' + status[0]

        submodules = git.getActiveSubmodules()
        if submodules:
            print("gathering status on submodules")
        for sub in submodules:
            if not sub.strip():
                continue
            os.chdir(sub)
            subStatus = git.status("--porcelain",quiet).split('\n')
            for line in subStatus: 
                strippedL = line.strip()
                if strippedL:
                    tokens = strippedL.split()
                    tokens[0] = tokens[0].strip()
                    if len(tokens[0]) == 1: 
                        tokens[0] = " %s" % tokens[0] 
                    status.append(' '.join([tokens[0],'/'.join([sub,tokens[1]])]))
            os.chdir(cwd)
        
        for line in status: 
            print line
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
