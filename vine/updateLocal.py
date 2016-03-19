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
                    [--recurse | --noRecurse [--recurseSubprojects]]
                    [--wd=<working dir>]
                    

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    --recurse               Update branches in submodules and nested subprojects.
    --noRecurse             Do not update branches in submodules and nested subprojects.
    --wd=<working dir>      Working directory which should be updated. 
                            Top level workspace will be updated if this is unspecified.
    --recurseSubprojects    Recurse in nested subprojects even if you're not recursing in submodules. 


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
        
        
        recurseNestedSubprojects = not args["--noRecurse"] or args["--recurseSubprojects"]
        currentBranch = git.currentBranch().strip()
        publicBranches = [x.strip() for x in args["--public"].split()]

        launchers = []
        for branch in publicBranches:
            launchers.append(utility.MultiRepoCommandLauncher(fetchLocal,  
                                            runInSubmodules=recurseSubmodules, 
                                            runInSubprojects=recurseNestedSubprojects, 
                                            branch=branch, 
                                            listOfRepoBranchArgTuples=None, 
                                            skipSubmodules=skipSubmodules))
        if len(launchers):
            launcher = launchers[0]
            for l in launchers[1:]:
                launcher.MergeLaunchSet(l)
            launcher.launchFromWorkspaceDir(handleMRE=fetchLocalHandler)
            
        return True


    def setDefaultConfig(self, config):
        pass
   
def fetchLocalHandler(mre):
    for e in mre.exceptions():
        print e.gitOutput
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
        
        if currentBranch:
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
                elif "Refusing to fetch into current branch" in e.gitOutput:
                    git.pull("origin %s" % branch)
                else:
                    raise e
        else:
            try:
                utility.printMsg("Pulling current branch %s in %s" % (branch, repo))
                git.pull("origin %s" % currentBranch)
            except git.GrapeGitError:
                print("GRAPE: Could not pull %s from origin. Maybe you haven't pushed it yet?" % currentBranch)