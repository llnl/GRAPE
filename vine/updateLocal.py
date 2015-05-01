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
        cwd = os.getcwd()
        
        config = grapeConfig.grapeConfig()
        recurseSubmodules = config.getboolean("workspace", "manageSubmodules") or args["--recurse"]
        recurseSubmodules = recurseSubmodules and (not args["--noRecurse"])
        recurseNestedSubprojects = not args["--noRecurse"]

        currentBranch = git.currentBranch().strip()
        publicBranches = [x.strip() for x in args["--public"].split()]

        # fetch branches in outer level repo
        self.fetchLocal(args, wsDir, cwd, publicBranches)

        if recurseNestedSubprojects:
           # fetch branches in nested subprojects
            for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(workspaceDir=wsDir):
                self.fetchLocal(args, os.path.join(wsDir, subproject), cwd, publicBranches)

        if recurseSubmodules:
           # fetch branches in submodules
            os.chdir(wsDir)
            activeSubmodules = git.getActiveSubmodules()
            if len(activeSubmodules) > 0: 
                subBranchMappings = config.getMapping("workspace", "submodulePublicMappings")
                for submodule in activeSubmodules:
                    try:
                        os.chdir(wsDir)
                        # First figure out the SHA for the branch on the submodule.
                        # The output of ls-tree should look like:
                        # 160000 commit <submodule SHA>  <submodule name>
                        gitlinkSHA = git.gitcmd("ls-tree %s %s" % (currentBranch, submodule),
                                                "Failed to execute ls-tree").split()[2]
                        os.chdir(os.path.join(wsDir, submodule))
                        # Check to see if the SHA in submodule matches
                        branchUpdate = True if git.SHA(currentBranch) != gitlinkSHA else False
                    except:
                        # This may fail if the branch does not exist on the submodule, 
                        # in which case we do not want to update it.
                        branchUpdate = False
  
                    # Repeat this for the public branches
                    publicUpdate = []
                    for public in publicBranches:
                        try:
                            submodulePublicBranch = subBranchMappings[public]
                            try:
                                os.chdir(wsDir)
                                gitlinkSHA = git.gitcmd("ls-tree %s %s" % (public, submodule),
                                                        "Failed to execute ls-tree").split()[2]
                                os.chdir(os.path.join(wsDir, submodule))
                                if git.SHA(submodulePublicBranch) != gitlinkSHA:
                                    publicUpdate.append(submodulePublicBranch)
                            except:
                                # This may fail if the branch does not exist on the submodule, 
                                # in which case we do not want to update it.
                                pass
                        except KeyError:
                            # Do nothing if the public branch mapping has not been defined.
                            pass
    
                     # Fetch branches on the submodule only something is not up-to-date
                    if branchUpdate or len(publicUpdate) > 0:
                        self.fetchLocal(args, os.path.join(wsDir, submodule), cwd, publicUpdate)
 
        os.chdir(cwd)
        return True

    @staticmethod
    def fetchLocal(args, workingDir, cwd, branches):
        
        os.chdir(workingDir)
        utility.printMsg("updating %s in %s" % (branches, workingDir))
        git.fetch("--prune")
        git.fetch("--tags")
        fetchArgs = "origin "
        currentBranch = git.currentBranch().strip()
        for pubBranch in branches:
            if currentBranch != pubBranch:
                arg = "%s:%s" % (pubBranch, pubBranch)
                if arg not in fetchArgs: 
                    fetchArgs += arg + " "
        try:
            git.fetch(fetchArgs)
        except git.GrapeGitError as e:
            # let non-fast-forward fetches slide
            if "rejected" in e.gitOutput and "non-fast-forward" in e.gitOutput:
                print e.gitCommand
                print e.gitOutput
                print("GRAPE: WARNING: one or more of your public branches have local commits! "
                      "Did you forget to create a topic branch?")
                pass
            else:
                os.chdir(cwd)
                raise e
        
        try:
            if currentBranch != "HEAD": 
                git.pull("origin %s" % currentBranch)
        except git.GrapeGitError:
            print("GRAPE: Could not pull %s from origin. Maybe you haven't pushed it yet?" % currentBranch)

    def setDefaultConfig(self, config):
        pass
