import os
import option
import grapeGit as git
import utility
import config


class Status(option.Option):
    """
    Usage: grape-status [-v] [-u | --uno] [--failIfInconsistent]

    Options:
    -v      Show git commands being issued. 
    --uno    Do not show untracked files
    -u      Show untracked files. 

    """
    def __init__(self):
        super(Status, self).__init__()
        self._key = "status"
        self._section = "Workspace"

    def description(self):
        return "Gives the status for this workspace"

    def execute(self, args):
        utility.printMsg("gathering status on outer level project")
        cwd = utility.workspaceDir() 
        os.chdir(cwd)
        quiet = not args["-v"]
        statusArgs = ""
        if args["-u"]:
            statusArgs += "-u "
        if args["--uno"]:
            statusArgs += "-uno "

        status = git.status("--porcelain %s" % statusArgs, quiet).split('\n')
        if status[0] and status[0][0] != ' ':
            status[0] = ' ' + status[0]

        subprojects = utility.getActiveSubprojects()
        if subprojects:
            utility.printMsg("gathering status on subprojects")
        for sub in subprojects:
            if not sub.strip():
                continue
            os.chdir(sub)
            subStatus = git.status("--porcelain %s" % statusArgs, quiet).split('\n')
            for line in subStatus: 
                strippedL = line.strip()
                if strippedL:
                    tokens = strippedL.split()
                    tokens[0] = tokens[0].strip()
                    if len(tokens[0]) == 1: 
                        tokens[0] = " %s" % tokens[0] 
                    status.append(' '.join([tokens[0], '/'.join([sub, tokens[1]])]))
            os.chdir(cwd)
        
        for line in status: 
            print ' ' + line.strip()
        
        # Sanity check workspace layout
        retval = True
        # Check that all public branches exist locally. 
        cfg = config.grapeConfig.grapeConfig()
        publicBranches = cfg.getList("flow", "publicbranches")
        missingBranches = config.Config.checkIfPublicBranchesExist(cfg, utility.workspaceDir(), 
                                                                   publicBranches)
        
        if (len(missingBranches) >0 ): 
            for mb in missingBranches:
                utility.printMsg("Repository is missing public branch %s" % mb)
            retval=False
        
        # Check that submodule branching is consistent
        
        os.chdir(cwd)
        wsBranch = git.currentBranch()
        subPubMap = cfg.getMapping("workspace", "submodulepublicmappings")
        if wsBranch in publicBranches:
            for sub in git.getActiveSubmodules():
                os.chdir(os.path.join(cwd,sub))
                subbranch = git.currentBranch()
                if subbranch != subPubMap[wsBranch]:
                    retval=False
                    utility.printMsg("Submodule %s on branch %s when grape expects it on %s" %
                                     (sub, subbranch, subPubMap[wsBranch]))
        else:
            for sub in git.getActiveSubmodules():
                os.chdir(os.path.join(cwd,sub))
                subbranch = git.currentBranch()
                if subbranch != wsBranch:
                    retval = False
                    utility.printMsg("Submodule %s on branch %s when grape expects it on %s" % 
                                     (sub, subbranch, subbranch))
                    
        return retval if args["--failIfInconsistent"] else True
    
    def setDefaultConfig(self, config):
        pass
