import os
import option
import grapeGit as git
import utility
import grapeConfig


class Pull(option.Option):
    """
    grape pull pulls any updates to your current branch into for your outer level repo and all subprojects.
    it uses 'git pull origin <currentBranch>' for the git command.

    Usage: grape-pull [--noRecurse] [--rebase] 

    Options:
    --noRecurse     Don't perform pulls in submodules or subprojects.   
    --rebase        Rebase local changes onto remote changes instead of merging remote changes into local changes.

    """
    def __init__(self):
        super(Pull, self).__init__()
        self._key = "pull"
        self._section = "Workspace"

    def description(self):
        return "Pulls your current branch to origin in all projects in this workspace."

    def execute(self, args):
        baseDir = utility.workspaceDir()

        cwd = os.getcwd()
        os.chdir(baseDir)
        currentBranch = git.currentBranch()
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()

        def pull(currentBranch, proj):
            if args["--rebase"]:
                argStr = "--rebase origin %s" % currentBranch
            else:
                argStr = "origin %s " % currentBranch
            
            utility.printMsg("Pulling %s in %s..." % (currentBranch, proj))
            git.pull(argStr, throwOnFail=True)
            
        submodules = git.getActiveSubmodules()
        

        try:
            pull(currentBranch, baseDir)
            if not args["--noRecurse"]:
                if submodules:
                    utility.printMsg("Performing pulls in all active submodules")
                subPubMap = config.getMapping("workspace", "submodulepublicmappings")
                subbranch = subPubMap[currentBranch] if currentBranch in publicBranches else currentBranch
                for sub in submodules: 
                    os.chdir(os.path.join(baseDir, sub))
                    
                    pull(subbranch, sub)
        
                nestedSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(baseDir)
                if nestedSubprojects:
                    utility.printMsg("Performing pulls in all active subprojects")
                for proj in nestedSubprojects:
                    os.chdir(os.path.join(baseDir, proj))
                    pull(currentBranch, proj)
                    
        except git.GrapeGitError as e:
            utility.printMsg("Failed to pull branch.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False
        finally:
            os.chdir(cwd)
        
        utility.printMsg("Pulled current branch from origin")
        return True
    
    def setDefaultConfig(self, config):
        pass
