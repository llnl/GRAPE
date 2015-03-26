import os
import option
import grapeGit as git
import utility
import grapeConfig


class Push(option.Option):
    """
    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--noRecurse] 

    Options:
    --noRecurse     Don't perform pushes in submodules.  

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    def execute(self, args):
        baseDir = utility.workspaceDir()

        cwd = os.getcwd()
        os.chdir(baseDir)
        currentBranch = git.currentBranch()
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()

        def push(currentBranch, proj): 
            utility.printMsg("Pushing %s in %s..." % (currentBranch, proj))
            git.push("-u origin %s" % currentBranch, throwOnFail=True)
            
        submodules = git.getActiveSubmodules()
        

        try:
            push(currentBranch, baseDir)
            if not args["--noRecurse"]:
                if submodules:
                    utility.printMsg("Performing pushes in all active submodules")
                subPubMap = config.getMapping("workspace", "submodulepublicmappings")
                subbranch = subPubMap[currentBranch] if currentBranch in publicBranches else currentBranch
                for sub in submodules: 
                    os.chdir(os.path.join(baseDir, sub))
                    push(subbranch, sub)
        
                nestedSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(baseDir)
                if nestedSubprojects:
                    utility.printMsg("Performing pushes in all active subprojects")
                for proj in nestedSubprojects:
                    os.chdir(os.path.join(baseDir, proj))
                    push(currentBranch, proj)
                    
        except git.GrapeGitError as e:
            utility.printMsg("Failed to push branch.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False
        os.chdir(cwd)
        
        utility.printMsg("Pushed current branch to origin")
        return True
    
    def setDefaultConfig(self, config):
        pass
