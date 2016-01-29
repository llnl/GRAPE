import option
import os
import grapeGit as git
import grapeConfig
import utility


# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    """
    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch> ]
                    [--recurse | --noRecurse]
                    [--wd=<working dir>]
                    

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    --recurse               Update branches in submodules and nested subprojects.
    --noRecurse             Do not update branches in submodules and nested subprojects.
    --wd=<working dir>      Working directory which should be updated. 
                            Top level workspace will be updated if this is unspecified.


    """
    def __init__(self):
        super(UpdateLocal, self).__init__()
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    def execute(self, args):
        wsDir = args["--wd"] if args["--wd"] else utility.workspaceDir()
        wsDir = os.path.abspath(wsDir)
        os.chdir(wsDir)
        cwd = os.getcwd()
        
        config = grapeConfig.grapeConfig()
        recurseSubmodules = config.getboolean("workspace", "manageSubmodules") or args["--recurse"]
        skipSubmodules = args["--noRecurse"]
        
        
        recurseNestedSubprojects = not args["--noRecurse"]

        currentBranch = git.currentBranch().strip()
        publicBranches = [x.strip() for x in args["--public"].split()]


        for branch in publicBranches:
            utility.MultiRepoCommandLauncher(fetchLocal,  
                                            runInSubmodules=recurseSubmodules, 
                                            runInSubprojects=recurseNestedSubprojects, 
                                            branch=branch, 
                                            listOfRepoBranchArgTuples=None, 
                                            skipSubmodules=skipSubmodules).launchFromWorkspaceDir(handleMRE=fetchLocalHandler)
            
        return True

        # fetch branches in outer level repo
        fetchLocal( wsDir, cwd, publicBranches)

        if recurseNestedSubprojects:
           # fetch branches in nested subprojects
            for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(workspaceDir=wsDir):
                fetchLocal(os.path.join(wsDir, subproject), cwd, publicBranches)

        if recurseSubmodules:
           # fetch branches in submodules
            
            activeSubmodules = git.getActiveSubmodules()
            if len(activeSubmodules) > 0: 
                subBranchMappings = config.getMapping("workspace", "submodulePublicMappings")
                for submodule in activeSubmodules:
                    try:
                        
                        # First figure out the SHA for the branch on the submodule.
                        # The output of ls-tree should look like:
                        # 160000 commit <submodule SHA>  <submodule name>
                        gitlinkSHA = git.gitcmd("ls-tree %s %s" % (currentBranch, submodule),
                                                "Failed to execute ls-tree").split()[2]
                        with utility.cd(os.path.join(wsDir, submodule)):
                            # Check to see if the SHA in submodule matches
                            branchUpdate = True if git.SHA(currentBranch) != gitlinkSHA else False
                    except:
                        # This may fail if the branch does not exist on the submodule, 
                        # in which case we do not want to update it.
                        branchUpdate = False
  
                    # Repeat this for the public branches
                    publicUpdate = set()
                    for public in publicBranches:
                        try:
                            submodulePublicBranch = subBranchMappings[public]
                            try:
                                with utility.cd(os.path.join(wsDir, submodule)):
                                    # check to make sure the remote ref exists
                                    git.fetch("origin %s " % submodulePublicBranch)                                    
                                    if git.currentBranch() != submodulePublicBranch:
                                        publicUpdate.add(submodulePublicBranch)
                                    else:
                                        utility.printMsg("skipping %s in %s (currently the active branch, use grape pull to update)" % (submodulePublicBranch, submodule))
                            except git.GrapeGitError as e:
                                # This may fail if the branch does not exist on the submodule, 
                                # in which case we do not want to update it.
                                utility.printMsg("skipping %s in %s (does not exist)" % (submodulePublicBranch, submodule))
                                pass
                        except KeyError:
                            # Do nothing if the public branch mapping has not been defined.
                            pass
    
                     # Fetch branches on the submodule only something is not up-to-date
                    if branchUpdate or len(publicUpdate) > 0:
                        fetchLocal( os.path.join(wsDir, submodule), cwd, list(publicUpdate))
 
        return True



    def setDefaultConfig(self, config):
        pass
   
def fetchLocalHandler(mre):
    print mre.exceptions()
    raise mre
   
def fetchLocal(repo='unknown', branch='master'):
    
    with utility.cd(repo):
        try:
            git.fetch("origin %s" % branch)
        except git.GrapeGitError as e:
            utility.printMsg("skipping %s in %s (does not exist)" % (branch, repo))
            return
        
        currentBranch = git.currentBranch()
        if currentBranch == "HEAD" or branch == "HEAD":
            return
        
        if git.currentBranch() != branch:
            utility.printMsg("updating %s in %s" % (branch, repo))            
            git.fetch("--prune --tags")
            fetchArgs = "origin %s:%s" % (branch, branch)
            try:
                git.fetch(fetchArgs)
            except git.GrapeGitError as e:
                # let non-fast-forward fetches slide
                if "rejected" in e.gitOutput and "non-fast-forward" in e.gitOutput:
                    print e.gitCommand
                    print e.gitOutput
                    print("GRAPE: WARNING:  your public branch %s in %s has local commits! "
                          "Did you forget to create a topic branch?" % (branch, repo))
                    pass
                else:
                    raise e
        else:
            try:
                utility.printMsg("Pulling current branch %s in %s" % (branch, repo))
                git.pull("origin %s" % currentBranch)
            except git.GrapeGitError:
                print("GRAPE: Could not pull %s from origin. Maybe you haven't pushed it yet?" % currentBranch)